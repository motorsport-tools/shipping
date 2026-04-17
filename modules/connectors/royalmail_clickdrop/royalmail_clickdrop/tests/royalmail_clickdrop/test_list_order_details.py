"""Royal Mail Click and Drop carrier list order details helper tests."""

import unittest
from unittest.mock import patch, ANY

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropListOrderDetails(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ListOrderDetailsRequest = ListOrderDetailsPayload

    def test_create_list_order_details_request(self):
        request = gateway.mapper.create_list_order_details_request(
            self.ListOrderDetailsRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), OrdersLookupRequest)

    def test_list_order_details(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            gateway.proxy.list_order_details(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/full"
                "?pageSize=2"
                "&startDateTime=2024-01-01T00%3A00%3A00Z"
                "&endDateTime=2024-01-31T23%3A59%3A59Z"
                "&continuationToken=NEXT123",
            )

    def test_parse_list_order_details_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ListOrderDetailsResponse

            request = gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            response = gateway.proxy.list_order_details(request)
            parsed_response = list(
                gateway.mapper.parse_list_order_details_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedListOrderDetailsResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ListOrderDetailsErrorResponse

            request = gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            response = gateway.proxy.list_order_details(request)
            parsed_response = list(
                gateway.mapper.parse_list_order_details_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


ListOrderDetailsPayload = {
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

ListOrderDetailsResponse = """{
  "orders": [
    {
      "orderIdentifier": 12345678,
      "orderStatus": "new",
      "createdOn": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "shippedOn": null,
      "postageAppliedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": null,
      "orderDate": "2024-01-01T10:00:00Z",
      "tradingName": "Test Warehouse",
      "department": "Dispatch",
      "orderReference": "ORDER-1001",
      "subtotal": 25.0,
      "shippingCostCharged": 3.5,
      "total": 28.5,
      "weightInGrams": 500,
      "currencyCode": "GBP",
      "shippingDetails": {
        "shippingCost": 3.5,
        "trackingNumber": "RM123456789GB",
        "serviceCode": "TPN24",
        "shippingService": "Royal Mail Tracked 24",
        "shippingCarrier": "Royal Mail",
        "packages": [
          {
            "packageNumber": 1,
            "trackingNumber": "RM123456789GB"
          }
        ]
      },
      "shippingInfo": {
        "firstName": "John",
        "lastName": "Smith",
        "companyName": "Example Ltd",
        "addressLine1": "1 High Street",
        "city": "London",
        "postcode": "SW1A1AA",
        "countryCode": "GB"
      },
      "billingInfo": {
        "firstName": "John",
        "lastName": "Smith",
        "companyName": "Example Ltd",
        "addressLine1": "1 High Street",
        "city": "London",
        "postcode": "SW1A1AA",
        "countryCode": "GB"
      },
      "orderLines": [
        {
          "SKU": "SKU-1",
          "name": "Blue T-Shirt",
          "quantity": 2,
          "unitValue": 12.5,
          "lineTotal": 25.0,
          "customsCode": 610910
        }
      ],
      "tags": [
        {
          "key": "channel",
          "value": "web"
        }
      ]
    }
  ],
  "continuationToken": "NEXT456"
}"""

ListOrderDetailsErrorResponse = """{
  "code": "BadRequest",
  "message": "Invalid order details lookup request"
}"""

ParsedListOrderDetailsResponse = [
    {
        "orders": ANY,
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
            "message": "Invalid order details lookup request",
            "details": {
                "operation": "list_order_details",
            },
        }
    ],
]