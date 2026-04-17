"""Royal Mail Click and Drop carrier return shipment tests."""

import logging
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib

from .fixture import gateway

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropReturnShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnShipmentRequest = models.ShipmentRequest(**ReturnShipmentPayload)

    def test_create_return_shipment_request(self):
        request = gateway.mapper.create_return_shipment_request(
            self.ReturnShipmentRequest
        )

        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), ReturnShipmentRequest)

    def test_create_return_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            gateway.proxy.create_return_shipment(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/returns",
            )

    def test_parse_return_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnShipmentResponse

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = gateway.proxy.create_return_shipment(request)
            parsed_response = list(
                gateway.mapper.parse_return_shipment_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedReturnShipmentResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnShipmentErrorResponse

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = gateway.proxy.create_return_shipment(request)
            parsed_response = list(
                gateway.mapper.parse_return_shipment_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


ReturnShipmentPayload = {
    "shipper": {
        "address_line1": "1 High Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
        "phone_number": "07123456789",
        "email": "john@example.com",
    },
    "recipient": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
        "phone_number": "07111111111",
        "email": "warehouse@example.com",
    },
    "parcels": [
        {
            "weight": 0.5,
            "weight_unit": "KG",
            "length": 10,
            "width": 10,
            "height": 2,
            "dimension_unit": "CM",
        }
    ],
    "service": "tracked_returns_48",
    "reference": "ORDER-1001",
}

ReturnShipmentRequest = {
    "service": {
        "serviceCode": "TSS",
    },
    "shipment": {
        "customerReference": {
            "reference": "ORDER-1001",
        },
        "returnAddress": {
            "addressLine1": "123 Test Street",
            "city": "London",
            "companyName": "Test Warehouse",
            "country": "United Kingdom",
            "countryIsoCode": "GBR",
            "firstName": "Warehouse",
            "lastName": "User",
            "postcode": "SW1A1AA",
        },
        "shippingAddress": {
            "addressLine1": "1 High Street",
            "city": "London",
            "companyName": "Example Ltd",
            "country": "United Kingdom",
            "countryIsoCode": "GBR",
            "firstName": "John",
            "lastName": "Smith",
            "postcode": "SW1A1AA",
        },
    },
}

ReturnShipmentResponse = """{
  "shipment": {
    "trackingNumber": "RM123456789GB",
    "uniqueItemId": "0A12345678901234"
  },
  "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
  "label": "JVBERi0xLjQKJcfs..."
}"""

ReturnShipmentErrorResponse = """{
  "code": "BadRequest",
  "message": "Invalid return request",
  "details": "Service code TSS is not available for this account"
}"""

ParsedReturnShipmentResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "tracking_number": "RM123456789GB",
        "shipment_identifier": "0A12345678901234",
        "label_type": "PDF",
        "docs": {
            "label": "JVBERi0xLjQKJcfs...",
            "pdf_label": "JVBERi0xLjQKJcfs...",
        },
        "meta": {
            "qr_code": "iVBORw0KGgoAAAANSUhEUgAA...",
            "is_return": True,
        },
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
            "message": "Invalid return request",
            "details": {
                "details": "Service code TSS is not available for this account",
            },
        }
    ],
]