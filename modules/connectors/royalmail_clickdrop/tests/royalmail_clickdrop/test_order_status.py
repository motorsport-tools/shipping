"""Royal Mail Click and Drop carrier order status update tests."""

import logging
import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropOrderStatus(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.OrderStatusRequest = OrderStatusPayload

    def test_create_order_status_request(self):
        request = gateway.mapper.create_order_status_request(self.OrderStatusRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), OrderStatusRequest)

    def test_update_order_status(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            gateway.proxy.update_order_status(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/status",
            )

    def test_parse_order_status_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = OrderStatusResponse

            request = gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            response = gateway.proxy.update_order_status(request)
            parsed_response = list(
                gateway.mapper.parse_order_status_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedOrderStatusResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = OrderStatusErrorResponse

            request = gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            response = gateway.proxy.update_order_status(request)
            parsed_response = list(
                gateway.mapper.parse_order_status_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


OrderStatusPayload = {
    "items": [
        {
            "order_identifier": 12345678,
            "status": "despatched",
        }
    ]
}

OrderStatusRequest = {
    "items": [
        {
            "orderIdentifier": 12345678,
            "status": "despatched",
        }
    ]
}

OrderStatusResponse = """{
  "updatedOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "status": "despatched"
    }
  ],
  "errors": []
}"""

OrderStatusErrorResponse = """[
  {
    "orderIdentifier": 12345678,
    "orderReference": "ORDER-1001",
    "status": "despatched",
    "code": "BadRequest",
    "message": "Invalid status update request"
  }
]"""

ParsedOrderStatusResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "operation": "Update Order Status",
        "success": True,
    },
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Invalid status update request",
            "details": {
                "operation": "update_order_status",
                "order_identifier": 12345678,
                "order_reference": "ORDER-1001",
            },
        }
    ],
]