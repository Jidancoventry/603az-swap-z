import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

# Set environment variables before importing the Lambda module.
os.environ.setdefault("ITEMS_TABLE", "items-test")
os.environ.setdefault("REQUESTS_TABLE", "requests-test")
os.environ.setdefault("IMAGE_BUCKET", "images-test")

# Avoid real AWS metadata/credential lookup during local tests.
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app  # noqa: E402


class ValidationTests(unittest.TestCase):
    def test_valid_listing(self):
        result = app.validate_listing({
            "title": "Dell laptop",
            "description": "Working laptop with charger.",
            "location": "Coventry",
            "category": "Laptop",
            "condition": "Good",
            "actionType": "Sell",
            "price": 120,
            "tokenValue": 50,
        })
        self.assertEqual(result["price"], Decimal("120"))

    def test_sell_requires_price(self):
        with self.assertRaises(app.ApiError) as context:
            app.validate_listing({
                "title": "Dell laptop",
                "description": "Working laptop with charger.",
                "location": "Coventry",
                "category": "Laptop",
                "condition": "Good",
                "actionType": "Sell",
                "price": 0,
                "tokenValue": 50,
            })
        self.assertEqual(context.exception.status_code, 400)

    def test_invalid_category_rejected(self):
        with self.assertRaises(app.ApiError):
            app.validate_listing({
                "title": "Device",
                "description": "A valid long description.",
                "location": "London",
                "category": "Spaceship",
                "condition": "Good",
                "actionType": "Donate",
                "price": 0,
                "tokenValue": 10,
            })


if __name__ == "__main__":
    unittest.main()
