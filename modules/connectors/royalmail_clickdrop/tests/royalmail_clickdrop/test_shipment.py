"""Royal Mail Click and Drop carrier shipment tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import fixture


class TestRoyalMailClickandDropShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _serialized_request(self, payload):
        request = fixture.gateway.mapper.create_shipment_request(self._shipment(payload))
        return lib.to_dict(request.serialize())

    def test_create_shipment_request(self):
        """Serialize a normalized Karrio shipment into the Royal Mail create-order payload."""
        self.assertEqual(
            self._serialized_request(fixture.ShipmentPayload),
            fixture.ShipmentRequest,
        )

    def test_create_shipment(self):
        """Verify the proxy sends the shipment creation request to POST /orders."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.create(self._shipment(fixture.ShipmentPayload)).from_(fixture.gateway)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders",
            )

    def test_parse_shipment_response(self):
        """Parse a successful order creation response into Karrio shipment details and documents."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponse

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed),
                fixture.ParsedShipmentResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail shipment creation errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentErrorResponse

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed),
                fixture.ParsedShipmentErrorResponse,
            )

    def test_create_shipment_request_with_billing(self):
        """Map YAML-compliant billing.address fields into the outbound request."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithBilling)
        billing = serialized["items"][0]["billing"]

        self.assertEqual(billing["address"]["addressLine1"], "2 Billing Street")
        self.assertEqual(billing["address"]["city"], "London")
        self.assertEqual(billing["address"]["postcode"], "EC1A1AA")
        self.assertEqual(billing["address"]["countryCode"], "GB")
        self.assertEqual(billing["emailAddress"], "billing@example.com")
        self.assertEqual(billing["phoneNumber"], "07111111111")

    def test_create_shipment_request_with_billing_missing_postcode(self):
        """Allow billing without postcode because the Royal Mail YAML does not require it."""
        serialized = self._serialized_request(fixture.ShipmentPayloadMissingBillingPostcode)
        billing = serialized["items"][0]["billing"]

        self.assertEqual(billing["address"]["addressLine1"], "2 Billing Street")
        self.assertEqual(billing["address"]["city"], "London")
        self.assertEqual(billing["address"]["countryCode"], "GB")
        self.assertNotIn("postcode", billing["address"])

    def test_create_shipment_request_without_billing(self):
        """Omit billing when the caller does not provide it."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithoutBilling)
        self.assertNotIn("billing", serialized["items"][0])

    def test_create_shipment_request_with_address_book_reference(self):
        """Forward recipient addressBookReference when provided in shipment options."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithoutBilling)

        self.assertEqual(
            serialized["items"][0]["recipient"]["addressBookReference"],
            "ADDR-001",
        )

    def test_create_shipment_request_without_tags(self):
        """Omit tags when no tags are provided."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithoutTags)
        self.assertNotIn("tags", serialized["items"][0])

    def test_create_shipment_request_order_extras(self):
        """Serialize planned despatch date, special instructions, and other costs."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithOrderExtras)
        item = serialized["items"][0]

        self.assertEqual(item["plannedDespatchDate"], "2024-01-02T10:00:00Z")
        self.assertEqual(item["specialInstructions"], "Leave with dispatch desk")
        self.assertEqual(item["otherCosts"], 1.25)

    def test_create_shipment_request_with_cn_override(self):
        """Allow domestic shipments to explicitly request CN inclusion."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithCN)

        self.assertTrue(serialized["items"][0]["label"]["includeCN"])

    def test_create_shipment_request_with_returns_label_override(self):
        """Allow shipment-level returns label option to flow into label generation."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithReturnsLabel)

        self.assertTrue(serialized["items"][0]["label"]["includeReturnsLabel"])

    def test_create_shipment_request_without_explicit_totals(self):
        """Calculate subtotal and total when caller omits them."""
        serialized = self._serialized_request(fixture.ShipmentPayloadNoExplicitTotals)
        item = serialized["items"][0]

        self.assertEqual(item["subtotal"], 25.0)
        self.assertEqual(item["shippingCostCharged"], 3.5)
        self.assertEqual(item["orderTax"], 1.2)
        self.assertEqual(item["total"], 29.7)

    def test_create_shipment_request_multi_parcel(self):
        """Serialize one Royal Mail package entry per Karrio parcel."""
        serialized = self._serialized_request(fixture.ShipmentPayloadMultiParcel)

        self.assertEqual(len(serialized["items"][0]["packages"]), 2)
        self.assertEqual(
            serialized["items"][0]["packages"][1]["packageFormatIdentifier"],
            "mediumParcel",
        )

    def test_create_shipment_request_multi_item_contents(self):
        """Serialize every line item in a parcel into package contents."""
        serialized = self._serialized_request(fixture.ShipmentPayloadMultiItem)
        contents = serialized["items"][0]["packages"][0]["contents"]

        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0]["SKU"], "SKU-1")
        self.assertEqual(contents[1]["SKU"], "SKU-2")
        self.assertEqual(contents[1]["customsCode"], "491199")

    def test_create_shipment_request_omits_optional_sections(self):
        """Omit optional sections when the source payload does not provide them."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithoutOptionalSections)
        item = serialized["items"][0]

        self.assertNotIn("billing", item)
        self.assertNotIn("importer", item)
        self.assertNotIn("tags", item)
        self.assertNotIn("addressBookReference", item["recipient"])
        self.assertNotIn("commercialInvoiceNumber", item["postageDetails"])
        self.assertNotIn("commercialInvoiceDate", item["postageDetails"])

    def test_create_shipment_request_international_fields(self):
        """Include importer and international postage details and auto-enable CN for cross-border shipments."""
        serialized = self._serialized_request(fixture.ShipmentPayloadInternational)
        item = serialized["items"][0]

        self.assertEqual(item["recipient"]["address"]["countryCode"], "FR")
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
        """Reject unknown service selectors before sending the request."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid Royal Mail Click & Drop service selector",
        ):
            fixture.gateway.mapper.create_shipment_request(
                self._shipment(fixture.ShipmentPayloadInvalidService)
            )

    def test_parse_shipment_response_package_tracking_fallback(self):
        """Use the first package tracking number when the top-level order tracking number is missing."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTopLevelTracking

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "RM999999999GB")

    def test_parse_shipment_response_multiple_package_tracking(self):
        """Keep all package tracking numbers in meta and use the first as fallback tracking."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithMultiplePackages

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "RM111111111GB")
            self.assertEqual(
                parsed[0].meta["package_tracking_numbers"],
                ["RM111111111GB", "RM222222222GB"],
            )

    def test_parse_shipment_response_without_label(self):
        """Treat shipments without inline labels as valid shipments with docs set to None."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutLabel

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertIsNone(parsed[0].docs)

    def test_parse_shipment_response_empty_created_orders(self):
        """Return no shipment and no messages when Royal Mail reports no created orders and no errors."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseEmptyCreatedOrders

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertListEqual(lib.to_dict(parsed), [None, []])

    def test_parse_shipment_array_error_response(self):
        """Flatten array-based shipment errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentArrayErrorResponse

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 1)
            self.assertEqual(parsed[1][0].code, "BadRequest")

    def test_parse_shipment_nested_error_response(self):
        """Flatten nested shipment errors into one Karrio message per Royal Mail error item."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentNestedErrorsResponse

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 2)
            self.assertEqual(parsed[1][0].code, "BadRequest")
            self.assertEqual(parsed[1][1].code, "Forbidden")

    def test_parse_shipment_response_without_tracking(self):
        """Fallback to the connector no-tracking marker when no tracking numbers are returned."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTracking

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "no code provided")
            self.assertFalse(parsed[0].meta["tracking_number_provided"])
            self.assertEqual(parsed[0].meta["package_tracking_numbers"], [])


if __name__ == "__main__":
    unittest.main()
