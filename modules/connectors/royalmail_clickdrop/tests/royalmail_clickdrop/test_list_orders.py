"""Royal Mail Click and Drop carrier list orders helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropListOrders(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ListOrdersRequest = ListOrdersPayload

    def test_create_list_orders_request(self):
        request = gateway.mapper.create_list_orders_request(self.ListOrdersRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), OrdersLookupRequest)

    def test_list_orders(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            gateway.proxy.list_orders(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders"
                "?pageSize=2"
                "&startDateTime=2024-01-01T00%3A00%3A00Z"
                "&endDateTime=2024-01-31T23%3A59%3A59Z"
                "&continuationToken=NEXT123",
            )

    def test_parse_list_orders_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ListOrdersResponse

            request = gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            response = gateway.proxy.list_orders(request)
            parsed_response = list(gateway.mapper.parse_list_orders_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedListOrdersResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ListOrdersErrorResponse

            request = gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            response = gateway.proxy.list_orders(request)
            parsed_response = list(gateway.mapper.parse_list_orders_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


ListOrdersPayload = {
    "page_size": 2,
    "start_date_time": "2024-01-01T00:00:00Z",
    "end_date_time": "2024-01-31T23:59:59Z",
    "continuation_token": "NEXT123",
}

OrdersLookupRequest = {
    "pageSize": 2,
    "startDateTime": "2024-01-01T00:00:00Z",
    "endDateTime": "2024-01-31T23:59:59Z",
    "continuationToken": "NEXT123",
}

ListOrdersResponse = """{
  "orders": [
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
  ],
  "continuationToken": "NEXT456"
}"""

ListOrdersErrorResponse = """{
  "code": "BadRequest",
  "message": "Invalid paging request"
}"""

ParsedListOrdersResponse = [
    {
        "orders": [
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
        "continuationToken": "NEXT456",
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
            "message": "Invalid paging request",
            "details": {
                "operation": "list_orders",
            },
        }
    ],
]