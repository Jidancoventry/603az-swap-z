import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ITEMS_TABLE = os.environ["ITEMS_TABLE"]
REQUESTS_TABLE = os.environ["REQUESTS_TABLE"]
IMAGE_BUCKET = os.environ["IMAGE_BUCKET"]
AUTO_APPROVE = os.getenv("AUTO_APPROVE_LISTINGS", "true").lower() == "true"
IMAGE_URL_TTL = int(os.getenv("IMAGE_URL_TTL_SECONDS", "3600"))
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", "5242880"))

DYNAMODB = boto3.resource("dynamodb")
ITEMS = DYNAMODB.Table(ITEMS_TABLE)
REQUESTS = DYNAMODB.Table(REQUESTS_TABLE)
S3 = boto3.client("s3")

ALLOWED_CATEGORIES = {"Laptop", "Phone", "Tablet", "Console", "Monitor", "Accessory", "Audio", "Other"}
ALLOWED_CONDITIONS = {"Like New", "Good", "Fair", "For Parts"}
ALLOWED_ACTIONS = {"Exchange", "Sell", "Donate", "Recycle"}
ALLOWED_REQUEST_TYPES = {"Exchange", "Purchase", "Donation", "Recycling"}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details or {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_default(value: Any):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def response(status_code: int, body: Any):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body, default=json_default),
    }


def parse_body(event: dict) -> dict:
    raw = event.get("body")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(400, "Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return data


def claims_from(event: dict) -> dict:
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
        or {}
    )


def groups_from(claims: dict) -> list[str]:
    value = claims.get("cognito:groups", [])
    if isinstance(value, list):
        return [str(entry) for entry in value]
    if not value:
        return []
    return [
        entry.strip().strip("'\"")
        for entry in str(value).strip("[]").split(",")
        if entry.strip()
    ]


def identity_from(event: dict) -> dict:
    claims = claims_from(event)
    user_id = claims.get("sub")
    if not user_id:
        raise ApiError(401, "A valid Cognito token is required.")
    groups = groups_from(claims)
    display_name = (
        claims.get("name")
        or claims.get("email")
        or claims.get("cognito:username")
        or claims.get("username")
        or "E-Swap user"
    )
    return {
        "userId": user_id,
        "name": str(display_name)[:100],
        "email": claims.get("email", ""),
        "groups": groups,
        "isAdmin": "Admin" in groups,
    }


def require_admin(event: dict) -> dict:
    identity = identity_from(event)
    if not identity["isAdmin"]:
        raise ApiError(403, "Admin group membership is required.")
    return identity


def clean_text(value: Any, field: str, minimum: int, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) < minimum:
        raise ApiError(400, f"{field} must contain at least {minimum} character(s).")
    if len(text) > maximum:
        raise ApiError(400, f"{field} must not exceed {maximum} characters.")
    return text


def as_non_negative_number(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value or 0))
    except Exception as exc:
        raise ApiError(400, f"{field} must be a number.") from exc
    if number < 0:
        raise ApiError(400, f"{field} must be zero or greater.")
    return number


def validate_listing(body: dict, partial: bool = False) -> dict:
    output: dict[str, Any] = {}

    def has(name: str) -> bool:
        return name in body or not partial

    if has("title"):
        output["title"] = clean_text(body.get("title"), "title", 2, 100)
    if has("description"):
        output["description"] = clean_text(body.get("description"), "description", 10, 1000)
    if has("location"):
        output["location"] = clean_text(body.get("location"), "location", 2, 80)

    if has("category"):
        category = str(body.get("category", ""))
        if category not in ALLOWED_CATEGORIES:
            raise ApiError(400, "Invalid category.")
        output["category"] = category

    if has("condition"):
        condition = str(body.get("condition", ""))
        if condition not in ALLOWED_CONDITIONS:
            raise ApiError(400, "Invalid condition.")
        output["condition"] = condition

    if has("actionType"):
        action = str(body.get("actionType", ""))
        if action not in ALLOWED_ACTIONS:
            raise ApiError(400, "Invalid actionType.")
        output["actionType"] = action

    if has("price"):
        output["price"] = as_non_negative_number(body.get("price", 0), "price")
    if has("tokenValue"):
        output["tokenValue"] = as_non_negative_number(body.get("tokenValue", 0), "tokenValue")

    if not partial and output.get("actionType") == "Sell" and output.get("price", Decimal("0")) <= 0:
        raise ApiError(400, "A selling listing must have a price greater than zero.")

    return output


def image_url(image_key: str | None) -> str:
    if not image_key:
        return ""
    try:
        return S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": IMAGE_BUCKET, "Key": image_key},
            ExpiresIn=IMAGE_URL_TTL,
        )
    except ClientError:
        logger.exception("Could not create image download URL", extra={"imageKey": image_key})
        return ""


def present_item(item: dict) -> dict:
    output = dict(item)
    output["imageUrl"] = image_url(item.get("imageKey"))
    return output


def get_item_or_404(item_id: str) -> dict:
    result = ITEMS.get_item(Key={"itemId": item_id}, ConsistentRead=True)
    item = result.get("Item")
    if not item:
        raise ApiError(404, "Item not found.")
    return item


def query_all(table, **kwargs) -> list[dict]:
    items: list[dict] = []
    while True:
        result = table.query(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key or len(items) >= 200:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items[:200]


def scan_all(table, limit: int = 200) -> list[dict]:
    items: list[dict] = []
    kwargs: dict[str, Any] = {"Limit": min(limit, 100)}
    while True:
        result = table.scan(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items[:limit]


def handle_list_items(event: dict):
    query = event.get("queryStringParameters") or {}
    result = ITEMS.query(
        IndexName="status-createdAt-index",
        KeyConditionExpression=Key("status").eq("Active"),
        ScanIndexForward=False,
        Limit=100,
    )
    items = result.get("Items", [])

    search = str(query.get("search", "")).strip().lower()
    category = str(query.get("category", "")).strip()
    condition = str(query.get("condition", "")).strip()
    action_type = str(query.get("actionType", "")).strip()
    location = str(query.get("location", "")).strip().lower()

    def matches(item: dict) -> bool:
        if search:
            haystack = " ".join(
                str(item.get(key, ""))
                for key in ("title", "description", "category", "location")
            ).lower()
            if search not in haystack:
                return False
        if category and item.get("category") != category:
            return False
        if condition and item.get("condition") != condition:
            return False
        if action_type and item.get("actionType") != action_type:
            return False
        if location and location not in str(item.get("location", "")).lower():
            return False
        return True

    return response(200, [present_item(item) for item in items if matches(item)][:50])


def handle_get_item(event: dict):
    item_id = event.get("pathParameters", {}).get("itemId", "")
    item = get_item_or_404(item_id)
    if item.get("status") != "Active":
        raise ApiError(404, "Item not found.")
    return response(200, present_item(item))


def handle_create_item(event: dict):
    identity = identity_from(event)
    body = parse_body(event)
    listing = validate_listing(body)

    image_key = str(body.get("imageKey", "")).strip()
    if image_key and not image_key.startswith(f"items/{identity['userId']}/"):
        raise ApiError(403, "The image does not belong to the signed-in user.")

    timestamp = now_iso()
    item = {
        "itemId": f"itm-{uuid.uuid4()}",
        "ownerId": identity["userId"],
        "ownerName": identity["name"],
        **listing,
        "imageKey": image_key,
        "status": "Active" if AUTO_APPROVE else "Pending",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    ITEMS.put_item(Item=item, ConditionExpression="attribute_not_exists(itemId)")
    logger.info(json.dumps({"event": "item_created", "itemId": item["itemId"], "ownerId": identity["userId"]}))
    return response(201, present_item(item))


def handle_my_items(event: dict):
    identity = identity_from(event)
    items = query_all(
        ITEMS,
        IndexName="ownerId-createdAt-index",
        KeyConditionExpression=Key("ownerId").eq(identity["userId"]),
        ScanIndexForward=False,
    )
    return response(200, [present_item(item) for item in items])


def handle_update_item(event: dict):
    identity = identity_from(event)
    item_id = event.get("pathParameters", {}).get("itemId", "")
    current = get_item_or_404(item_id)
    if current.get("ownerId") != identity["userId"] and not identity["isAdmin"]:
        raise ApiError(403, "You can update only your own listings.")

    updates = validate_listing(parse_body(event), partial=True)
    if not updates:
        raise ApiError(400, "No editable fields were supplied.")
    updates["updatedAt"] = now_iso()

    names = {f"#{key}": key for key in updates}
    values = {f":{key}": value for key, value in updates.items()}
    expression = "SET " + ", ".join(f"#{key} = :{key}" for key in updates)
    result = ITEMS.update_item(
        Key={"itemId": item_id},
        UpdateExpression=expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    logger.info(json.dumps({"event": "item_updated", "itemId": item_id, "actorId": identity["userId"]}))
    return response(200, present_item(result["Attributes"]))


def handle_delete_item(event: dict):
    identity = identity_from(event)
    item_id = event.get("pathParameters", {}).get("itemId", "")
    current = get_item_or_404(item_id)
    if current.get("ownerId") != identity["userId"] and not identity["isAdmin"]:
        raise ApiError(403, "You can delete only your own listings.")

    ITEMS.delete_item(Key={"itemId": item_id})
    image_key = current.get("imageKey")
    if image_key:
        try:
            S3.delete_object(Bucket=IMAGE_BUCKET, Key=image_key)
        except ClientError:
            logger.exception("Item deleted but image cleanup failed", extra={"itemId": item_id, "imageKey": image_key})
    logger.info(json.dumps({"event": "item_deleted", "itemId": item_id, "actorId": identity["userId"]}))
    return response(200, {"deleted": True, "itemId": item_id})


def handle_presign_upload(event: dict):
    identity = identity_from(event)
    body = parse_body(event)
    content_type = str(body.get("contentType", "")).lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ApiError(400, "Only JPG, PNG and WebP images are allowed.")

    try:
        size = int(body.get("size", 0))
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "Image size must be an integer.") from exc
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise ApiError(400, f"Image size must be between 1 byte and {MAX_IMAGE_BYTES} bytes.")

    original_name = clean_text(body.get("fileName"), "fileName", 1, 200)
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", original_name.rsplit(".", 1)[0]).strip("-")[:50] or "image"
    extension = ALLOWED_IMAGE_TYPES[content_type]
    image_key = f"items/{identity['userId']}/{uuid.uuid4()}-{safe_stem}{extension}"

    upload_url = S3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": IMAGE_BUCKET,
            "Key": image_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,
    )
    return response(200, {"uploadUrl": upload_url, "imageKey": image_key, "expiresIn": 300})


def handle_create_request(event: dict):
    identity = identity_from(event)
    body = parse_body(event)
    item_id = clean_text(body.get("itemId"), "itemId", 1, 100)
    request_type = str(body.get("requestType", ""))
    if request_type not in ALLOWED_REQUEST_TYPES:
        raise ApiError(400, "Invalid requestType.")
    message = clean_text(body.get("message"), "message", 2, 500)

    item = get_item_or_404(item_id)
    if item.get("status") != "Active":
        raise ApiError(409, "This listing is not currently active.")
    if item.get("ownerId") == identity["userId"]:
        raise ApiError(400, "You cannot send a request for your own listing.")

    timestamp = now_iso()
    request_item = {
        "requestId": f"req-{uuid.uuid4()}",
        "itemId": item_id,
        "itemTitle": item.get("title", "Item"),
        "requesterId": identity["userId"],
        "requesterName": identity["name"],
        "ownerId": item["ownerId"],
        "requestType": request_type,
        "message": message,
        "status": "Pending",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    REQUESTS.put_item(Item=request_item, ConditionExpression="attribute_not_exists(requestId)")
    logger.info(json.dumps({"event": "request_created", "requestId": request_item["requestId"], "itemId": item_id}))
    return response(201, request_item)


def handle_my_requests(event: dict):
    identity = identity_from(event)
    sent = query_all(
        REQUESTS,
        IndexName="requesterId-createdAt-index",
        KeyConditionExpression=Key("requesterId").eq(identity["userId"]),
        ScanIndexForward=False,
    )
    received = query_all(
        REQUESTS,
        IndexName="ownerId-createdAt-index",
        KeyConditionExpression=Key("ownerId").eq(identity["userId"]),
        ScanIndexForward=False,
    )
    combined = {entry["requestId"]: entry for entry in sent + received}
    ordered = sorted(combined.values(), key=lambda entry: entry.get("createdAt", ""), reverse=True)
    return response(200, ordered)


def handle_update_request(event: dict):
    identity = identity_from(event)
    request_id = event.get("pathParameters", {}).get("requestId", "")
    result = REQUESTS.get_item(Key={"requestId": request_id}, ConsistentRead=True)
    request_item = result.get("Item")
    if not request_item:
        raise ApiError(404, "Request not found.")

    status = str(parse_body(event).get("status", ""))
    owner_statuses = {"Accepted", "Rejected", "Completed"}
    requester_statuses = {"Cancelled"}
    allowed = False
    if identity["isAdmin"]:
        allowed = status in owner_statuses | requester_statuses | {"Pending"}
    elif request_item.get("ownerId") == identity["userId"]:
        allowed = status in owner_statuses
    elif request_item.get("requesterId") == identity["userId"]:
        allowed = status in requester_statuses

    if not allowed:
        raise ApiError(403, "You are not allowed to apply that request status.")
    if request_item.get("status") != "Pending" and status != "Completed":
        raise ApiError(409, "Only pending requests can be changed.")

    update_result = REQUESTS.update_item(
        Key={"requestId": request_id},
        UpdateExpression="SET #status = :status, updatedAt = :updatedAt",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": status, ":updatedAt": now_iso()},
        ReturnValues="ALL_NEW",
    )
    logger.info(json.dumps({"event": "request_updated", "requestId": request_id, "status": status}))
    return response(200, update_result["Attributes"])


def handle_admin_items(event: dict):
    require_admin(event)
    items = sorted(scan_all(ITEMS), key=lambda entry: entry.get("createdAt", ""), reverse=True)
    return response(200, [present_item(item) for item in items])


def handle_moderate_item(event: dict):
    identity = require_admin(event)
    item_id = event.get("pathParameters", {}).get("itemId", "")
    get_item_or_404(item_id)
    status = str(parse_body(event).get("status", ""))
    if status not in {"Active", "Pending", "Removed"}:
        raise ApiError(400, "Admin status must be Active, Pending or Removed.")
    result = ITEMS.update_item(
        Key={"itemId": item_id},
        UpdateExpression="SET #status = :status, updatedAt = :updatedAt",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": status, ":updatedAt": now_iso()},
        ReturnValues="ALL_NEW",
    )
    logger.info(json.dumps({"event": "item_moderated", "itemId": item_id, "status": status, "adminId": identity["userId"]}))
    return response(200, present_item(result["Attributes"]))


ROUTES = {
    "GET /items": handle_list_items,
    "GET /items/{itemId}": handle_get_item,
    "POST /items": handle_create_item,
    "GET /my-items": handle_my_items,
    "PATCH /items/{itemId}": handle_update_item,
    "DELETE /items/{itemId}": handle_delete_item,
    "POST /uploads/presign": handle_presign_upload,
    "POST /requests": handle_create_request,
    "GET /my-requests": handle_my_requests,
    "PATCH /requests/{requestId}": handle_update_request,
    "GET /admin/items": handle_admin_items,
    "PATCH /admin/items/{itemId}": handle_moderate_item,
}


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "local")
    route_key = event.get("routeKey", "")
    logger.info(json.dumps({"event": "request_received", "requestId": request_id, "routeKey": route_key}))

    if route_key == "GET /health":
        return response(200, {"status": "ok", "service": "e-swap-api", "time": now_iso()})

    handler = ROUTES.get(route_key)
    if not handler:
        return response(404, {"message": "Route not found."})

    try:
        result = handler(event)
        logger.info(json.dumps({"event": "request_completed", "requestId": request_id, "routeKey": route_key, "statusCode": result["statusCode"]}))
        return result
    except ApiError as exc:
        logger.warning(json.dumps({"event": "request_rejected", "requestId": request_id, "routeKey": route_key, "statusCode": exc.status_code, "message": exc.message}))
        payload = {"message": exc.message}
        if exc.details:
            payload["details"] = exc.details
        return response(exc.status_code, payload)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        logger.exception("AWS service call failed", extra={"requestId": request_id, "routeKey": route_key, "awsErrorCode": error_code})
        return response(500, {"message": "An AWS service operation failed.", "code": error_code})
    except Exception:
        logger.exception("Unhandled request failure", extra={"requestId": request_id, "routeKey": route_key})
        return response(500, {"message": "An unexpected server error occurred."})
