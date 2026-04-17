"""Royal Mail Click and Drop carrier shipment tests."""

import unittest
from unittest.mock import patch, ANY
from .fixture import gateway
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentRequest = models.ShipmentRequest(**ShipmentPayload)

    def test_create_shipment_request(self):
        request = gateway.mapper.create_shipment_request(self.ShipmentRequest)
        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), ShipmentRequest)

    def test_create_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.create(self.ShipmentRequest).from_(gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders",
            )

    def test_parse_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), ParsedShipmentResponse)

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ErrorResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), ParsedErrorResponse)


if __name__ == "__main__":
    unittest.main()


ShipmentPayload = {
    "shipper": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
    },
    "recipient": {
        "address_line1": "1 High Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
    },
    "parcels": [
        {
            "weight": 500,
            "weight_unit": "G",
            "length": 25,
            "width": 18,
            "height": 5,
            "dimension_unit": "CM",
            "items": [
                {
                    "sku": "SKU-1",
                    "description": "Blue T-Shirt",
                    "quantity": 2,
                    "value_amount": 12.5,
                    "weight": 150,
                    "hs_code": "610910",
                    "origin_country": "GB",
                    "metadata": {
                        "customs_declaration_category": "saleOfGoods",
                        "requires_export_licence": False,
                        "stock_location": "A1",
                        "use_origin_preference": True,
                        "supplementary_units": 1,
                    },
                }
            ],
        }
    ],
    "service": "tracked_24",
    "reference": "ORDER-1001",
    "options": {
        "package_format_identifier": "small_parcel",
        "order_reference": "ORDER-1001",
        "order_date": "2024-01-01T10:00:00Z",
        "carrier_name": "Royal Mail OBA",
        "subtotal": 25.0,
        "shipping_cost_charged": 3.5,
        "order_tax": 0.0,
        "total": 28.5,
        "receive_email_notification": True,
        "receive_sms_notification": False,
        "include_label_in_response": True,
        "tags": [{"key": "channel", "value": "web"}],
    },
}

ShipmentRequest = {
    "items": [
        {
            "orderReference": "ORDER-1001",
            "recipient": {
                "address": {
                    "fullName": "John Smith",
                    "companyName": "Example Ltd",
                    "addressLine1": "1 High Street",
                    "city": "London",
                    "postcode": "SW1A1AA",
                    "countryCode": "GB",
                }
            },
            "sender": {
                "tradingName": "Test Warehouse",
            },
            "packages": [
                {
                    "weightInGrams": 500,
                    "packageFormatIdentifier": "smallParcel",
                    "dimensions": {
                        "heightInMms": 50,
                        "widthInMms": 180,
                        "depthInMms": 250,
                    },
                    "contents": [
                        {
                            "SKU": "SKU-1",
                            "name": "Blue T-Shirt",
                            "quantity": 2,
                            "unitValue": 12.5,
                            "unitWeightInGrams": 150,
                            "customsDescription": "Blue T-Shirt",
                            "extendedCustomsDescription": "Blue T-Shirt",
                            "customsCode": "610910",
                            "originCountryCode": "GB",
                            "customsDeclarationCategory": "saleOfGoods",
                            "requiresExportLicence": False,
                            "stockLocation": "A1",
                            "useOriginPreference": True,
                            "supplementaryUnits": "1",
                        }
                    ],
                }
            ],
            "orderDate": "2024-01-01T10:00:00Z",
            "subtotal": 25.0,
            "shippingCostCharged": 3.5,
            "total": 28.5,
            "currencyCode": "GBP",
            "postageDetails": {
                "serviceCode": "TPN24",
                "carrierName": "Royal Mail OBA",
                "receiveEmailNotification": True,
                "receiveSmsNotification": False,
            },
            "tags": [
                {
                    "key": "channel",
                    "value": "web",
                }
            ],
            "label": {
                "includeLabelInResponse": True,
            },
            "orderTax": 0.0,
        }
    ]
}

ShipmentResponse = """{
  "successCount": 1,
  "errorsCount": 0,
  "createdOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "createdOn": "2024-01-01T10:00:00Z",
      "orderDate": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": "2024-01-01T11:00:00Z",
      "shippedOn": "2024-01-01T12:00:00Z",
      "trackingNumber": "RM123456789GB",
      "packages": [
        {
          "packageNumber": 1,
          "trackingNumber": "RM123456789GB"
        }
      ],
      "label": "JVBERi0xLjQKJcfs...",
      "labelErrors": [],
      "generatedDocuments": ["label"]
    }
  ],
  "failedOrders": []
}"""

ErrorResponse = """{
  "code": "BadRequest",
  "message": "The request is invalid",
  "details": "One or more validation errors occurred"
}"""

ParsedShipmentResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "tracking_number": "RM123456789GB",
        "shipment_identifier": "12345678",
        "label_type": "PDF",
        "docs": ANY,
        "meta": {
            "order_identifier": 12345678,
            "order_reference": "ORDER-1001",
            "created_on": "2024-01-01T10:00:00Z",
            "order_date": "2024-01-01T10:00:00Z",
            "printed_on": "2024-01-01T10:01:00Z",
            "manifested_on": "2024-01-01T11:00:00Z",
            "shipped_on": "2024-01-01T12:00:00Z",
            "tracking_numbers": ["RM123456789GB"],
            "shipment_identifiers": ["12345678", "ORDER-1001"],
            "package_tracking_numbers": ["RM123456789GB"],
            "generated_documents": ["label"],
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
            "message": "The request is invalid",
            "details": {
                "operation": "create_shipment",
                "details": "One or more validation errors occurred",
            },
        }
    ],
]