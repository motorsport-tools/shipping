"""Royal Mail Click and Drop carrier return shipment tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib
import karrio.core.models as models

from .fixture import gateway


class TestRoyalMailClickandDropReturnShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnShipmentRequest = models.ShipmentRequest(**ReturnShipmentPayload)

    def test_create_return_shipment_request(self):
        request = gateway.mapper.create_return_shipment_request(self.ReturnShipmentRequest)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG create return shipment request:", serialized)

        self.assertEqual(
            serialized,
            ReturnShipmentRequest,
        )

    def test_create_return_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            gateway.proxy.create_return_shipment(request)

            print("DEBUG create return shipment call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/returns",
            )
            self.assertEqual(mock.call_args[1]["method"], "POST")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )
            self.assertEqual(
                mock.call_args[1]["headers"]["Content-Type"],
                "application/json",
            )
            self.assertEqual(
                mock.call_args[1]["headers"]["Accept"],
                "application/json",
            )

    def test_parse_return_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnShipmentResponse

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = gateway.proxy.create_return_shipment(request)
            shipment, messages = gateway.mapper.parse_return_shipment_response(response)

            print(
                "DEBUG parsed return shipment:",
                lib.to_dict(shipment) if shipment else None,
            )
            print(
                "DEBUG parsed return shipment messages:",
                lib.to_dict(messages),
            )

            self.assertIsNotNone(shipment)
            self.assertEqual(len(messages), 0)
            self.assertEqual(shipment.carrier_id, "royalmail_clickdrop")
            self.assertEqual(shipment.carrier_name, "royalmail_clickdrop")
            self.assertEqual(shipment.tracking_number, "RM123456789GB")
            self.assertEqual(shipment.shipment_identifier, "0A12345678901234")
            self.assertEqual(shipment.label_type, "PDF")
            self.assertEqual(shipment.docs.label, "JVBERi0xLjQKJcfs...")
            self.assertEqual(shipment.meta["qr_code"], "iVBORw0KGgoAAAANSUhEUgAA...")
            self.assertTrue(shipment.meta["is_return"])

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnShipmentErrorResponse

            request = gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = gateway.proxy.create_return_shipment(request)
            shipment, messages = gateway.mapper.parse_return_shipment_response(response)

            print("DEBUG parsed return shipment error shipment:", shipment)
            print(
                "DEBUG parsed return shipment error messages:",
                lib.to_dict(messages),
            )

            self.assertIsNone(shipment)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "BadRequest")
            self.assertEqual(messages[0].message, "Invalid return request")


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
        "serviceCode": "TSS"
    },
    "shipment": {
        "customerReference": {
            "reference": "ORDER-1001"
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
        }
    }
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
