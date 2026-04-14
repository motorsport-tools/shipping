"""Royal Mail Click and Drop carrier shipment tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

from .fixture import gateway, ShipmentPayload, ShipmentResponse, ShipmentErrorResponse


class TestRoyalMailClickandDropShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

        payload = copy.deepcopy(ShipmentPayload)

        # Use strict exact service selector for tests.
        payload["options"]["service_code"] = "TPN24"

        self.payload = payload
        self.ShipmentRequest = models.ShipmentRequest(**payload)

    def test_create_shipment_request(self):
        request = gateway.mapper.create_shipment_request(self.ShipmentRequest)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG create shipment request:", serialized)

        self.assertIn("items", serialized)
        self.assertEqual(len(serialized["items"]), 1)
        self.assertEqual(serialized["items"][0]["orderReference"], "ORDER-1001")
        self.assertEqual(serialized["items"][0]["postageDetails"]["serviceCode"], "TPN24")
        self.assertEqual(
            serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
            "smallParcel",
        )
        self.assertEqual(serialized["items"][0]["subtotal"], 25.0)
        self.assertEqual(serialized["items"][0]["shippingCostCharged"], 3.5)
        self.assertEqual(serialized["items"][0]["total"], 28.5)
        self.assertTrue(serialized["items"][0]["label"]["includeLabelInResponse"])

    def test_package_format_explicit_option_takes_precedence(self):
        payload = copy.deepcopy(self.payload)
        payload["parcels"][0]["packaging_type"] = "envelope"
        payload["options"]["package_format_identifier"] = "small_parcel"

        request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        serialized = lib.to_dict(request.serialize())

        print(
            "DEBUG package format explicit precedence request:",
            serialized,
        )

        self.assertEqual(
            serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
            "smallParcel",
        )

    def test_package_format_uses_packaging_type_when_no_explicit_option(self):
        payload = copy.deepcopy(self.payload)
        payload["parcels"][0]["packaging_type"] = "envelope"
        payload["options"].pop("package_format_identifier", None)

        request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        serialized = lib.to_dict(request.serialize())

        print(
            "DEBUG package format packaging_type request:",
            serialized,
        )

        self.assertEqual(
            serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
            "letter",
        )

    def test_package_format_is_inferred_when_no_explicit_option_or_packaging_type(self):
        payload = copy.deepcopy(self.payload)
        payload["options"].pop("package_format_identifier", None)
        payload["parcels"][0].pop("packaging_type", None)

        payload["parcels"][0]["weight"] = 80
        payload["parcels"][0]["weight_unit"] = "G"
        payload["parcels"][0]["length"] = 20
        payload["parcels"][0]["width"] = 15
        payload["parcels"][0]["height"] = 0.4
        payload["parcels"][0]["dimension_unit"] = "CM"

        request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        serialized = lib.to_dict(request.serialize())

        print(
            "DEBUG package format inferred request:",
            serialized,
        )

        self.assertEqual(
            serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
            "largeLetter",
        )

    def test_create_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.create(self.ShipmentRequest).from_(gateway)

            print("DEBUG create shipment call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders",
            )
            self.assertEqual(mock.call_args[1]["method"], "POST")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )

    def test_parse_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentResponse

            shipment, messages = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed shipment:", lib.to_dict(shipment) if shipment else None)
            print("DEBUG parsed shipment messages:", lib.to_dict(messages))

            self.assertIsNotNone(shipment)
            self.assertEqual(len(messages), 0)
            self.assertEqual(shipment.carrier_id, "royalmail_clickdrop")
            self.assertEqual(shipment.tracking_number, "RM123456789GB")
            self.assertEqual(shipment.shipment_identifier, "12345678")
            self.assertEqual(shipment.label_type, "PDF")
            self.assertEqual(shipment.docs.label, "JVBERi0xLjQKJcfs...")
            self.assertEqual(shipment.meta["order_reference"], "ORDER-1001")

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentErrorResponse

            shipment, messages = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed shipment error shipment:", shipment)
            print("DEBUG parsed shipment error messages:", lib.to_dict(messages))

            self.assertIsNone(shipment)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "BadRequest")
            self.assertEqual(messages[0].message, "The request is invalid")


if __name__ == "__main__":
    unittest.main()
