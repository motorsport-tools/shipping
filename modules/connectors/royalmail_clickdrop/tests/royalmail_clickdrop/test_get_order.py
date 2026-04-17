"""Royal Mail Click and Drop carrier get order helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropGetOrder(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetOrderRequest = GetOrderPayload

    def test_create_get_order_request(self):
        request = gateway.mapper.create_get_order_request(self.GetOrderRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), OrderLookupRequest)

    def test_get_order(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "[]"

            request = gateway.mapper.create_get_order_request(self.GetOrderRequest)
            gateway.proxy.get_order(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678",
            )

    def test_parse_get_order_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetOrderResponse

            request = gateway.mapper.create_get_order_request(self.GetOrderRequest)
            response = gateway.proxy.get_order(request)
            parsed_response = list(gateway.mapper.parse_get_order_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedGetOrderResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetOrderErrorResponse

            request = gateway.mapper.create_get_order_request(self.GetOrderRequest)
            response = gateway.proxy.get_order(request)
            parsed_response = list(gateway.mapper.parse_get_order_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


GetOrderPayload = {
    "order_identifiers": [12345678],
}

OrderLookupRequest = {
    "orderIdentifiers": "12345678",
}

GetOrderResponse = """[
  {
    "orderIdentifier": 12345678,
    "orderReference": "ORDER-1001",
    "createdOn": "2024-01-01T10:00:00Z",
    "orderDate": "2024-01-01T10:00:00Z",
    "printedOn": "2024-01-01T10:01:00Z",
    "manifestedOn": null,
    "shippedOn": null,
    "trackingNumber": "RM123456789GB",
    "packages": [
      {
        "packageNumber": 1,
        "trackingNumber": "RM123456789GB"
      }
    ]
  }
]"""

GetOrderErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  }
]"""

ParsedGetOrderResponse = [
    [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "trackingNumber": "RM123456789GB",
            "packages": [
                {
                    "packageNumber": 1,
                    "trackingNumber": "RM123456789GB",
                }
            ],
        }
    ],
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order not found",
            "details": {
                "operation": "get_order",
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]