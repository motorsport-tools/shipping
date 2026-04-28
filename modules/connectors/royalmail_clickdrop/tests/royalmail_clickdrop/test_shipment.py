 
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

    def test_parse_failed_order_validation_errors(self):
        """Promote failed-order field validation errors into user-friendly Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentFailedOrdersValidationResponse

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed),
                fixture.ParsedShipmentFailedOrdersValidationResponse,
            )

    def test_create_shipment_request_raw_service_code_passes_through(self):
        """Allow raw Royal Mail service codes like CRL24 to pass straight into postageDetails.serviceCode."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithRawServiceCode)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["serviceCode"], "CRL24")
        self.assertEqual(postage["serviceRegisterCode"], "01")

    def test_create_shipment_request_service_option_overrides_payload_service(self):
        """Let options.service_code override payload.service after Karrio service normalization."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithServiceOptionOverride)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["serviceCode"], "CRL24")
        self.assertEqual(postage["serviceRegisterCode"], "01")

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

    def test_create_shipment_request_multi_parcel_customs_only_subtotal(self):
        """Use shipment-level customs commodities for subtotal when multi-parcel items are not parcel-scoped."""
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)
        payload["recipient"]["country_code"] = "FR"
        payload["recipient"]["postal_code"] = "75001"
        payload["recipient"]["city"] = "Paris"
        payload["recipient"]["person_name"] = "Jean Martin"
        payload["recipient"]["company_name"] = "Example FR"
        payload["recipient"]["email"] = "jean@example.fr"
        payload["reference"] = "ORDER-MULTI-CUSTOMS-ONLY"
        payload["options"]["order_reference"] = "ORDER-MULTI-CUSTOMS-ONLY"
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["options"]["shipping_cost_charged"] = 3.5
        payload["options"]["order_tax"] = 1.2

        for parcel in payload["parcels"]:
            parcel.pop("items", None)

        payload["customs"] = {
            "content_type": "merchandise",
            "commodities": [
                {
                    "sku": "SKU-1",
                    "description": "Blue T-Shirt",
                    "quantity": 2,
                    "value_amount": 12.5,
                    "weight": 150,
                    "weight_unit": "G",
                    "hs_code": "610910",
                    "origin_country": "GB",
                }
            ],
        }

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["subtotal"], 25.0)
        self.assertEqual(item["shippingCostCharged"], 3.5)
        self.assertEqual(item["orderTax"], 1.2)
        self.assertEqual(item["total"], 29.7)

    def test_create_shipment_request_with_standard_shipping_charges_alias(self):
        """Honor Karrio's standard shipping_charges option for Royal Mail shippingCostCharged."""
        payload = copy.deepcopy(fixture.ShipmentPayloadNoExplicitTotals)
        payload["options"].pop("shipping_cost_charged", None)
        payload["options"]["shipping_charges"] = 3.5

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["shippingCostCharged"], 3.5)
        self.assertEqual(item["total"], 29.7)

    def test_create_shipment_request_with_standard_email_notification_target_alias(self):
        """Honor Karrio's standard email_notification_to option for Royal Mail sendNotificationsTo."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["recipient"]["email"] = ""
        payload["options"].pop("send_notifications_to", None)
        payload["options"]["email_notification_to"] = "billing"
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("email_notification", None)

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "billing")
        self.assertTrue(postage["receiveEmailNotification"])

    def test_create_shipment_request_fractional_dangerous_goods_quantity(self):
        """Preserve fractional dangerous-goods quantities instead of coercing them to integers."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["contains_dangerous_goods"] = True
        payload["options"]["dangerous_goods_un_code"] = "1993"
        payload["options"]["dangerous_goods_description"] = "Flammable liquid"
        payload["options"]["dangerous_goods_quantity"] = 0.5

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["dangerousGoodsQuantity"], 0.5)

    def test_create_shipment_request_maps_all_supported_product_fields_from_karrio_items(self):
        """Populate all Royal Mail product fields that can be derived from Karrio item data."""
        serialized = self._serialized_request(fixture.ShipmentPayload)
        content = serialized["items"][0]["packages"][0]["contents"][0]

        self.assertEqual(content["SKU"], "SKU-1")
        self.assertEqual(content["name"], "Blue T-Shirt")
        self.assertEqual(content["quantity"], 2)
        self.assertEqual(content["unitValue"], 12.5)
        self.assertEqual(content["unitWeightInGrams"], 150)
        self.assertEqual(content["customsDescription"], "Blue T-Shirt")
        self.assertEqual(content["extendedCustomsDescription"], "Blue T-Shirt")
        self.assertEqual(content["customsCode"], "610910")
        self.assertEqual(content["originCountryCode"], "GB")
        self.assertEqual(content["customsDeclarationCategory"], "saleOfGoods")
        self.assertEqual(content["requiresExportLicence"], False)
        self.assertEqual(content["stockLocation"], "A1")
        self.assertEqual(content["useOriginPreference"], True)
        self.assertEqual(content["supplementaryUnits"], "1")
        self.assertNotIn("licenseNumber", content)
        self.assertNotIn("certificateNumber", content)

    def test_create_shipment_request_normalizes_item_customs_category_from_metadata(self):
        """Normalize Karrio item metadata customs category values into Royal Mail enum values."""
        payload = copy.deepcopy(fixture.ShipmentPayload)
        payload["parcels"][0]["items"][0]["metadata"]["customs_declaration_category"] = "sale_of_goods"

        serialized = self._serialized_request(payload)
        content = serialized["items"][0]["packages"][0]["contents"][0]

        self.assertEqual(content["customsDeclarationCategory"], "saleOfGoods")

    def test_create_shipment_request_supports_spec_valid_sku_plus_quantity_items(self):
        """Keep SKU lookup items to Royal Mail's SKU + quantity mode without auto-filled descriptive fields."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutItemValueWeight)

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]
        content = item["packages"][0]["contents"][0]

        self.assertEqual(content["SKU"], "SKU-LOOKUP-1")
        self.assertEqual(content["quantity"], 1)
        self.assertNotIn("name", content)
        self.assertNotIn("customsDescription", content)
        self.assertNotIn("extendedCustomsDescription", content)
        self.assertNotIn("unitValue", content)
        self.assertNotIn("unitWeightInGrams", content)
        self.assertEqual(item["subtotal"], 25.0)
        self.assertEqual(item["total"], 28.5)

    def test_create_shipment_request_quantizes_monetary_fields_to_two_decimals(self):
        """Quantize Royal Mail monetary fields to 2 decimal places using half-up rounding."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["items"][0]["value_amount"] = 12.345
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["options"]["shipping_cost_charged"] = 3.456
        payload["options"]["order_tax"] = 1.005

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]
        content = item["packages"][0]["contents"][0]

        self.assertEqual(content["unitValue"], 12.35)
        self.assertEqual(item["subtotal"], 24.69)
        self.assertEqual(item["shippingCostCharged"], 3.46)
        self.assertEqual(item["orderTax"], 1.01)
        self.assertEqual(item["total"], 29.16)

    def test_create_shipment_request_excludes_non_ddp_customs_duty_from_total(self):
        """Do not add customs duty to total when customsDutyCosts will not be serialized."""
        payload = copy.deepcopy(fixture.ShipmentPayloadInternational)
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["options"]["shipping_cost_charged"] = 3.5
        payload["options"]["order_tax"] = 1.2
        payload["options"]["customs_duty_costs"] = 4.0
        payload["customs"] = {
            "content_type": "merchandise",
            "incoterm": "DAP",
            "commodities": [],
        }

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertNotIn("customsDutyCosts", item)
        self.assertEqual(item["total"], 29.7)

    def test_create_shipment_request_includes_ddp_customs_duty_in_total(self):
        """Add customs duty to total when DDP causes customsDutyCosts to be serialized."""
        payload = copy.deepcopy(fixture.ShipmentPayloadInternational)
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["options"]["shipping_cost_charged"] = 3.5
        payload["options"]["order_tax"] = 1.2
        payload["options"]["customs_duty_costs"] = 4.0
        payload["customs"] = {
            "content_type": "merchandise",
            "incoterm": "DDP",
            "commodities": [],
        }

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["customsDutyCosts"], 4.0)
        self.assertEqual(item["total"], 33.7)

    def test_create_shipment_request_validates_item_quantity_bounds(self):
        """Reject Royal Mail product quantities outside the allowed range."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["items"][0]["quantity"] = 0

        with self.assertRaisesRegex(
            ValueError,
            r"`quantity` must be greater than or equal to 1",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_validates_package_weight_bounds(self):
        """Reject package weights above Royal Mail's maximum grams limit."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["weight"] = 31000
        payload["parcels"][0]["weight_unit"] = "G"

        with self.assertRaisesRegex(
            ValueError,
            r"`weightInGrams` must be less than or equal to 30000",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_validates_order_total_bounds(self):
        """Reject totals above Royal Mail's maximum allowed order amount."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["total"] = 1000000

        with self.assertRaisesRegex(
            ValueError,
            r"`total` must be less than or equal to 999999.00",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_normalizes_spaced_item_customs_category_from_metadata(self):
        """Normalize spaced Karrio item customs category values into Royal Mail enum values."""
        payload = copy.deepcopy(fixture.ShipmentPayload)
        payload["parcels"][0]["items"][0]["metadata"]["customs_declaration_category"] = "sale of goods"

        serialized = self._serialized_request(payload)
        content = serialized["items"][0]["packages"][0]["contents"][0]

        self.assertEqual(content["customsDeclarationCategory"], "saleOfGoods")

    def test_create_shipment_request_omits_invalid_item_origin_country_code(self):
        """Drop unrecognized origin country names instead of truncating them into invalid pseudo-codes."""
        payload = copy.deepcopy(fixture.ShipmentPayload)
        payload["parcels"][0]["items"][0]["origin_country"] = "England"

        serialized = self._serialized_request(payload)
        content = serialized["items"][0]["packages"][0]["contents"][0]

        self.assertNotIn("originCountryCode", content)

    def test_parse_shipment_response_empty_created_orders(self):
        """Return a parser error when Royal Mail reports no created orders and no carrier errors."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseEmptyCreatedOrders

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 1)
            self.assertEqual(parsed[1][0].code, "shipment_parse_error")

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

