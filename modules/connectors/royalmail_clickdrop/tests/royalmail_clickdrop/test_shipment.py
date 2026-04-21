 
"""Royal Mail Click and Drop carrier shipment tests."""

import unittest
from unittest.mock import patch, ANY
from . import fixture

import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)




class TestRoyalMailClickandDropShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentRequest = models.ShipmentRequest(**fixture.ShipmentPayload)

    def test_create_shipment_request(self):
        """Serialize a normalized Karrio shipment into the Royal Mail create-order payload."""
        request = fixture.gateway.mapper.create_shipment_request(self.ShipmentRequest)
        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), fixture.ShipmentRequest)

    def test_create_shipment(self):
        """Verify the proxy sends the shipment creation request to POST /orders."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.create(self.ShipmentRequest).from_(fixture.gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders",
            )

    def test_create_shipment_request_with_billing_missing_postcode(self):
        shipment = models.ShipmentRequest(
            **fixture.ShipmentPayloadMissingBillingPostcode
        )

        with self.assertRaisesRegex(
            ValueError,
            r"options\.billing\.address\.postcode"
        ):
            fixture.gateway.mapper.create_shipment_request(shipment)

    def test_parse_shipment_response(self):
        """Parse a successful order creation response into Karrio shipment details and documents."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedShipmentResponse)

    def test_parse_error_response(self):
        """Normalize Royal Mail shipment creation errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentErrorResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedShipmentErrorResponse)

    def test_create_shipment_request_with_billing(self):
        """Ensure billing details are included in the request when explicitly provided."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadRichBase)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertIn("billing", serialized["items"][0])
        self.assertEqual(
            serialized["items"][0]["billing"]["address"]["postcode"],
            "EC1A1AA",
        )


    def test_create_shipment_request_without_billing(self):
        """Ensure billing is omitted from the request when no billing data is provided."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadWithoutBilling)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertNotIn("billing", serialized["items"][0])

    def test_create_shipment_request_with_tags(self):
        """Ensure order tags are serialized into the outbound Royal Mail payload when present."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayload)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["tags"],
            [{"key": "channel", "value": "web"}],
        )

    def test_create_shipment_request_without_tags(self):
        """Ensure tags are omitted from the outbound payload when not provided."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadWithoutTags)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertNotIn("tags", serialized["items"][0])

    def test_create_shipment_request_with_address_book_reference(self):
        """Ensure the recipient addressBookReference is forwarded when provided in shipping options."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadRichBase)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["recipient"]["addressBookReference"],
            "ADDR-001",
        )
    def test_create_shipment_request_with_carrier_name(self):
        """Ensure carrierName is set on postageDetails when explicitly provided or resolved from config."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayload)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["carrierName"],
            "Royal Mail OBA",
        )

    def test_create_shipment_request_with_cn_override(self):
        """Ensure the shipment request can explicitly force CN document inclusion."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadWithCN)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertTrue(serialized["items"][0]["label"]["includeCN"])

    def test_create_shipment_request_with_returns_label_override(self):
        """Ensure the shipment request can explicitly force returns label inclusion."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadWithReturnsLabel)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertTrue(serialized["items"][0]["label"]["includeReturnsLabel"])


    def test_create_shipment_request_without_explicit_totals(self):
        """Ensure subtotal and total are calculated when the caller does not provide explicit amounts."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadNoExplicitTotals)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertGreater(serialized["items"][0]["subtotal"], 0)
        self.assertGreater(serialized["items"][0]["total"], 0)

    def test_create_shipment_request_multi_parcel(self):
        """Ensure all parcels in a multi-parcel shipment are serialized into Royal Mail package entries."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadMultiParcel)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(len(serialized["items"][0]["packages"]), 2)

    def test_create_shipment_request_international_fields(self):
        """Ensure international-only customs/importer/postage fields are included for cross-border shipments."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadInternational)
        request = fixture.gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        item = serialized["items"][0]

        self.assertIn("importer", item)
        self.assertTrue(item["label"]["includeCN"])
        self.assertEqual(
            item["postageDetails"]["commercialInvoiceNumber"],
            "INV-INTL-1001",
        )
        self.assertEqual(
            item["postageDetails"]["IOSSNumber"],
            "IM2760000000",
        )
        self.assertEqual(
            item["postageDetails"]["recipientEoriNumber"],
            "FR12345678900013",
        )


    def test_create_shipment_request_invalid_service(self):
        """Reject unknown shipment service selectors before sending the request to Royal Mail."""
        shipment = models.ShipmentRequest(**fixture.ShipmentPayloadInvalidService)

        with self.assertRaises(ValueError):
            fixture.gateway.mapper.create_shipment_request(shipment)

    def test_parse_shipment_response_package_tracking_fallback(self):
        """Use the first package tracking number when the top-level order tracking number is missing."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTopLevelTracking

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "RM123456789GB")

    def test_parse_shipment_response_multiple_package_tracking(self):
        """Keep every package tracking number in shipment metadata and use the first one as fallback tracking."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithMultiplePackages

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed multi-package response: {lib.to_dict(parsed)}")
            self.assertEqual(parsed[0].tracking_number, "RM111111111GB")
            self.assertEqual(
                parsed[0].meta["package_tracking_numbers"],
                ["RM111111111GB", "RM222222222GB"],
            )

    def test_parse_shipment_response_without_label(self):
        """Treat shipments without an inline label as valid shipments with docs set to None."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutLabel

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed shipment without label: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0].docs)


    def test_parse_shipment_response_empty_created_orders(self):
        """Return no shipment and no messages when Royal Mail reports no created orders and no errors."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseEmptyCreatedOrders

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed empty createdOrders response: {lib.to_dict(parsed)}")
            self.assertListEqual(lib.to_dict(parsed), [None, []])


    def test_parse_shipment_array_error_response(self):
        """Flatten array-based shipment errors into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentArrayErrorResponse

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed shipment array errors: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 1)
            self.assertEqual(parsed[1][0].code, "BadRequest")


    def test_parse_shipment_nested_error_response(self):
        """Flatten nested Royal Mail shipment errors into one message per failed order."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentNestedErrorsResponse

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed shipment nested errors: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 2)
            self.assertEqual(parsed[1][0].code, "BadRequest")
            self.assertEqual(parsed[1][1].code, "Forbidden")

    def test_parse_shipment_response_without_tracking(self):
        """Default tracking_number when Royal Mail creates an order without any tracking codes."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTracking

            parsed = (
                karrio.Shipment.create(models.ShipmentRequest(**fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed shipment without tracking: {lib.to_dict(parsed)}")
            self.assertEqual(parsed[0].tracking_number, "no code provided")
            self.assertFalse(parsed[0].meta["tracking_number_provided"])
            self.assertEqual(parsed[0].meta["package_tracking_numbers"], [])











if __name__ == "__main__":
    unittest.main()


