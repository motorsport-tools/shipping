"""Royal Mail Click and Drop carrier get order details helper tests."""

import unittest
from unittest.mock import patch, ANY

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropGetOrderDetails(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetOrderDetailsRequest = GetOrderDetailsPayload

    def test_create_get_order_details_request(self):
        request = gateway.mapper.create_get_order_details_request(
            self.GetOrderDetailsRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), OrderLookupRequest)

    def test_get_order_details(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "[]"

            request = gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            gateway.proxy.get_order_details(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678/full",
            )

    def test_parse_get_order_details_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetOrderDetailsResponse

            request = gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            response = gateway.proxy.get_order_details(request)
            parsed_response = list(
                gateway.mapper.parse_get_order_details_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedGetOrderDetailsResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetOrderDetailsErrorResponse

            request = gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            response = gateway.proxy.get_order_details(request)
            parsed_response = list(
                gateway.mapper.parse_get_order_details_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


GetOrderDetailsPayload = {
    "order_identifiers": [12345678],
}

OrderLookupRequest = {
    "orderIdentifiers": "12345678",
}

GetOrderDetailsResponse = """[
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
]"""

GetOrderDetailsErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order details not found"
  }
]"""

ParsedGetOrderDetailsResponse = [
    [
        {
            "orderIdentifier": 12345678,
            "orderStatus": "new",
            "createdOn": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "postageAppliedOn": "2024-01-01T10:01:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "tradingName": "Test Warehouse",
            "department": "Dispatch",
            "orderReference": "ORDER-1001",
            "subtotal": 25.0,
            "shippingCostCharged": 3.5,
            "total": 28.5,
            "weightInGrams": 500,
            "currencyCode": "GBP",
            "shippingDetails": ANY,
            "shippingInfo": ANY,
            "billingInfo": ANY,
            "orderLines": ANY,
            "tags": ANY,
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
            "message": "Order details not found",
            "details": {
                "operation": "get_order_details",
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]