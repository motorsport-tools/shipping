"""Royal Mail Click and Drop order-status validation edge-case tests."""

import unittest

from . import fixture


class TestRoyalMailClickandDropOrderStatusValidations(unittest.TestCase):
    def test_create_order_status_request_reset_status(self):
        """Allow status resets back to `new` without additional dispatch fields."""
        request = fixture.gateway.mapper.create_order_status_request(
            fixture.OrderStatusResetPayload
        )

        self.assertEqual(
            request.serialize(),
            {"items": [{"orderIdentifier": 12345678, "status": "new"}]},
        )

    def test_create_order_status_request_rejects_both_identifier_and_reference(self):
        """Require exactly one of orderIdentifier or orderReference per status item."""
        with self.assertRaisesRegex(
            ValueError,
            "exactly one of `orderIdentifier` or `orderReference`",
        ):
            fixture.gateway.mapper.create_order_status_request(
                {
                    "items": [
                        {
                            "order_identifier": 12345678,
                            "order_reference": "ORDER-1001",
                            "status": "despatched",
                        }
                    ]
                }
            )

    def test_create_order_status_request_rejects_missing_identifier_and_reference(self):
        """Require some item identifier for every status update."""
        with self.assertRaisesRegex(
            ValueError,
            "exactly one of `orderIdentifier` or `orderReference`",
        ):
            fixture.gateway.mapper.create_order_status_request(
                {
                    "items": [
                        {
                            "status": "despatched",
                        }
                    ]
                }
            )

    def test_create_order_status_request_rejects_invalid_status(self):
        """Reject unsupported Royal Mail order statuses before sending the request."""
        with self.assertRaisesRegex(
            ValueError,
            r"`status` must be one of `new`, `despatched`, or `despatchedByOtherCourier`",
        ):
            fixture.gateway.mapper.create_order_status_request(
                {
                    "items": [
                        {
                            "order_identifier": 12345678,
                            "status": "cancelled",
                        }
                    ]
                }
            )

    def test_create_order_status_request_rejects_more_than_100_items(self):
        """Reject status update batches larger than the Royal Mail API maximum."""
        with self.assertRaisesRegex(
            ValueError,
            "maximum of 100 order status items",
        ):
            fixture.gateway.mapper.create_order_status_request(
                {
                    "items": [
                        {"order_identifier": 10000000 + i, "status": "despatched"}
                        for i in range(101)
                    ]
                }
            )