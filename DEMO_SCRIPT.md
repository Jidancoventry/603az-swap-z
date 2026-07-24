# E-Swap 6–8 Minute Demonstration Script

## 1. Problem and goal — 30 seconds

“E-Swap addresses electronic waste by enabling users to exchange, sell, donate or recycle unwanted devices. The prototype demonstrates a secure serverless cloud workflow rather than only a static UI.”

## 2. Architecture — 60 seconds

Explain:

- Amplify hosts the React frontend.
- Cognito registers and authenticates users.
- API Gateway exposes public and protected HTTP routes.
- The JWT authorizer verifies tokens.
- Lambda runs validation and ownership rules.
- DynamoDB stores listings and requests.
- S3 stores private images using presigned URLs.
- CloudWatch and X-Ray provide observability.

## 3. User journey — 2 minutes

1. Register and confirm an account, or use a pre-confirmed account.
2. Login.
3. Create an item with an image.
4. Submit.
5. Show My listings.
6. Refresh the browser to prove persistence.
7. Open Browse and Item details.

## 4. Prove AWS persistence — 1 minute

Immediately show:

- The matching record in `ESwapItems-dev` DynamoDB.
- The matching private object in S3.
- The Lambda log event `item_created` in CloudWatch.

## 5. Two-user workflow — 1 minute

- User B sends an Exchange request.
- User A sees it under Requests.
- User A accepts or rejects it.
- Show the request record in DynamoDB.

## 6. Security — 1 minute

Show at least one:

- Protected POST with no JWT returns 401.
- User B attempting to edit User A item returns 403.
- Normal user cannot call the Admin API.

Explain that frontend route hiding is usability only; Lambda enforces ownership and Admin group membership.

## 7. Monitoring and evaluation — 45 seconds

Show CloudWatch API/Lambda logs and state:

- Valid data returns 2xx.
- Missing/invalid data returns 400.
- Missing authentication returns 401.
- Wrong ownership returns 403.
- Missing resource returns 404.

## 8. Limitations — 30 seconds

“Payments and real-time messaging are outside the implemented prototype. Search currently filters a bounded result set and would use OpenSearch at larger scale. A commercial version would add notifications, content scanning, rate limits, WAF, automated CI/CD testing and multi-region recovery.”
