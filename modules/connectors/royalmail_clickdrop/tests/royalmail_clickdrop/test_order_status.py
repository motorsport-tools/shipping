"""Royal Mail Click and Drop carrier order status update tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import (
    gateway,
    OrderStatusPayload,
    OrderStatusResponse,
    OrderStatusErrorResponse,
    OrderStatusResetPayload,
    OrderStatusOtherCourierPayload,
)


class TestRoyalMailClickandDropOrderStatus(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.OrderStatusRequest = OrderStatusPayload

    def test_create_order_status_request(self):
        request = gateway.mapper.create_order_status_request(self.OrderStatusRequest)
        serialized = request.serialize()

        print("DEBUG create order status request:", serialized)

        self.assertEqual(
            serialized,
            {
                "items": [
                    {
                        "orderIdentifier": 12345678,
                        "status": "despatched",
                    }
                ]
            },
        )

        reset_request = gateway.mapper.create_order_status_request(OrderStatusResetPayload)
        reset_serialized = reset_request.serialize()

        print("DEBUG create order reset request:", reset_serialized)

        self.assertEqual(
            reset_serialized,
            {
                "items": [
                    {
                        "orderIdentifier": 12345678,
                        "status": "new",
                    }
                ]
            },
        )

        other_request = gateway.mapper.create_order_status_request(OrderStatusOtherCourierPayload)
        other_serialized = other_request.serialize()

        print("DEBUG create order despatchedByOtherCourier request:", other_serialized)

        self.assertEqual(
            other_serialized,
            {
                "items": [
                    {
                        "orderIdentifier": 12345678,
                        "status": "despatchedByOtherCourier",
                        "trackingNumber": "OTHER123456",
                        "despatchDate": "2024-01-01T12:00:00Z",
                        "shippingCarrier": "Other Carrier",
                        "shippingService": "Express",
                    }
                ]
            },
        )

    def test_update_order_status(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_order_status_request(self.OrderStatusRequest)
            gateway.proxy.update_order_status(request)

            print("DEBUG update order status call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/status",
            )
            self.assertEqual(mock.call_args[1]["method"], "PUT")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )

    def test_parse_order_status_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = OrderStatusResponse

            request = gateway.mapper.create_order_status_request(self.OrderStatusRequest)
            response = gateway.proxy.update_order_status(request)
            confirmation, messages = gateway.mapper.parse_order_status_response(response)

            print("DEBUG parsed order status confirmation:", lib.to_dict(confirmation) if confirmation else None)
            print("DEBUG parsed order status messages:", lib.to_dict(messages))

            self.assertIsNotNone(confirmation)
            self.assertEqual(len(messages), 0)
            self.assertTrue(confirmation.success)
            self.assertEqual(confirmation.operation, "Update Order Status")
            self.assertEqual(confirmation.carrier_id, "royalmail_clickdrop")

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = OrderStatusErrorResponse

            request = gateway.mapper.create_order_status_request(self.OrderStatusRequest)
            response = gateway.proxy.update_order_status(request)
            confirmation, messages = gateway.mapper.parse_order_status_response(response)

            print("DEBUG parsed order status error confirmation:", confirmation)
            print("DEBUG parsed order status error messages:", lib.to_dict(messages))

            self.assertIsNone(confirmation)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "BadRequest")
            self.assertEqual(messages[0].message, "Invalid status update request")


if __name__ == "__main__":
    unittest.main()
