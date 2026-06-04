 
"""Royal Mail Click and Drop carrier shipment tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.royalmail.units as provider_units

from . import fixture


class TestRoyalMailClickandDropShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _serialized_request(self, payload):
        request = fixture.gateway.mapper.create_shipment_request(self._shipment(payload))
        return lib.to_dict(request.serialize())

    def _set_single_light_item(
        self,
        payload,
        *,
        item_weight: int = 10,
        item_value: float = 1.0,
    ):
        """
        Make a copied shipment payload physically valid for letter/large-letter
        tests that lower the parcel weight.

        The base Royal Mail fixture contains 2 x 150 g items = 300 g contents.
        Tests that change the package to a 100 g large letter must also lower
        the contents weight, otherwise the package/content weight validator
        correctly rejects the request before the package-format behaviour can be
        asserted.
        """
        payload["parcels"][0]["items"] = [
            {
                "sku": "LL-TEST-ITEM",
                "description": "Large letter test item",
                "quantity": 1,
                "value_amount": item_value,
                "weight": item_weight,
                "hs_code": "491199",
                "origin_country": "GB",
                "metadata": {
                    "customs_declaration_category": "saleOfGoods",
                    "requires_export_licence": False,
                    "stock_location": "A1",
                    "use_origin_preference": True,
                    "supplementary_units": 1,
                    "license_number": "",
                    "certificate_number": "",
                },
            }
        ]

        payload["options"]["subtotal"] = item_value
        payload["options"]["order_tax"] = 0.0

        shipping_cost = (
            payload["options"].get("shipping_cost_charged")
            or payload["options"].get("shipping_charges")
            or 0.0
        )

        payload["options"]["total"] = float(item_value) + float(shipping_cost)

        return payload

    def test_create_shipment_request(self):
        """Serialize a normalized Karrio shipment into the Royal Mail create-order payload."""
        self.assertEqual(
            self._serialized_request(fixture.ShipmentPayload),
            fixture.ShipmentRequest,
        )

    def test_create_shipment(self):
        """Verify the proxy sends the shipment creation request to POST /orders."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.create(
                self._shipment(fixture.ShipmentPayloadWithoutBilling)
            ).from_(fixture.gateway)

            self.assertTrue(mock.called)
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders",
            )

    def test_parse_failed_order_validation_errors(self):
        """Promote failed-order field validation errors into user-friendly Karrio messages."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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

    def test_create_shipment_request_rejects_explicit_email_notification_for_unsupported_service(self):
        """Fail early when the caller explicitly enables email notifications for a service that does not support them."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["service"] = fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE
        payload["options"]["receive_email_notification"] = True

        with self.assertRaisesRegex(
            ValueError,
            r"does not support email notifications",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_raw_service_code_passes_through(self):
        """Allow raw Royal Mail service codes like CRL24 to pass straight into postageDetails.serviceCode."""
        serialized = self._serialized_request(fixture.ShipmentPayloadWithRawServiceCode)
        postage = serialized["items"][0]["postageDetails"]

        expected_register_code = provider_units.resolve_service_register_code(
            fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE,
            package_format=fixture.SHIPMENT_PACKAGE_FORMAT_IDENTIFIER,
        )

        self.assertEqual(postage["serviceCode"], fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE)
        self.assertEqual(postage["serviceRegisterCode"], expected_register_code)

    def test_create_shipment_request_service_option_overrides_payload_service(self):
        """Let options.service_code override payload.service after Karrio service normalization."""
        serialized = self._serialized_request(
            fixture.ShipmentPayloadWithServiceOptionOverride
        )
        postage = serialized["items"][0]["postageDetails"]

        expected_register_code = provider_units.resolve_service_register_code(
            fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE,
            package_format=fixture.SHIPMENT_PACKAGE_FORMAT_IDENTIFIER,
        )

        self.assertEqual(postage["serviceCode"], fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE)
        self.assertEqual(postage["serviceRegisterCode"], expected_register_code)

    def test_parse_shipment_response(self):
        """Parse a successful order creation response into Karrio shipment details and documents."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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

        self.assertEqual(
            [
                package["packageFormatIdentifier"]
                for package in serialized["items"][0]["packages"]
            ],
            ["parcel", "parcel"],
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTopLevelTracking

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "RM999999999GB")

    def test_parse_shipment_response_multiple_package_tracking(self):
        """Keep all package tracking numbers in meta and use the first as fallback tracking."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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

            self.assertEqual(
                parsed[0].meta["tracking_options"]["order_references"],
                {
                    "RM111111111GB": "ORDER-1001",
                    "RM222222222GB": "ORDER-1001",
                },
            )
            self.assertEqual(
                parsed[0].meta["tracking_lookup"]["tracking_numbers"],
                ["RM111111111GB", "RM222222222GB"],
            )
            self.assertEqual(
                parsed[0].meta["tracking_lookup"]["order_reference"],
                "ORDER-1001",
            )

    def test_parse_shipment_response_without_label(self):
        """Treat shipments without inline labels as valid shipments with docs set to None."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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

    def test_create_shipment_request_dangerous_goods_quantity_serializes_as_number(self):
        """Serialize dangerous-goods quantity as a numeric value supported by the Royal Mail API."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["contains_dangerous_goods"] = True
        payload["options"]["dangerous_goods_un_code"] = "1993"
        payload["options"]["dangerous_goods_description"] = "Flammable liquid"
        payload["options"]["dangerous_goods_quantity"] = 1

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["dangerousGoodsQuantity"], 1.0)
        self.assertIsInstance(item["dangerousGoodsQuantity"], float)

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

        # Use an active DDP small-parcel service. This resolves to Royal Mail MPR
        # but also carries the email_notifications feature in services.csv, so the
        # inherited fixture notification options remain valid.
        payload["service"] = "royal_mail_international_ddp_tracked_small_parcel"

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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentResponseWithoutTracking

            parsed = (
                karrio.Shipment.create(self._shipment(fixture.ShipmentPayload))
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].tracking_number, "no code provided")
            self.assertFalse(parsed[0].meta["tracking_number_provided"])
            self.assertEqual(parsed[0].meta["package_tracking_numbers"], [])

    def test_create_shipment_request_rejects_standard_email_notification_alias_for_unsupported_service(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["service"] = fixture.ROYAL_MAIL_24_RAW_SERVICE_CODE
        payload["options"].pop("receive_email_notification", None)
        payload["options"]["email_notification"] = True

        with self.assertRaisesRegex(
            ValueError,
            r"does not support email notifications",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_raw_service_code_omits_notification_fields(self):
        serialized = self._serialized_request(fixture.ShipmentPayloadWithRawServiceCode)
        postage = serialized["items"][0]["postageDetails"]

        self.assertNotIn("receiveEmailNotification", postage)
        self.assertNotIn("receiveSmsNotification", postage)
        self.assertNotIn("sendNotificationsTo", postage)

    def test_create_shipment_request_with_sms_notification_only(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("email_notification", None)
        payload["options"]["receive_sms_notification"] = True
        payload["options"]["send_notifications_to"] = "recipient"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "recipient")
        self.assertTrue(postage["receiveSmsNotification"])
        self.assertNotIn("receiveEmailNotification", postage)

    def test_create_shipment_request_rejects_sms_notification_without_phone(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["recipient"]["phone_number"] = ""
        payload["options"]["receive_sms_notification"] = True
        payload["options"]["send_notifications_to"] = "recipient"

        with self.assertRaisesRegex(
            ValueError,
            r"does not have a phone number",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_email_notification_to_implies_email_notification(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"].pop("send_notifications_to", None)
        payload["options"].pop("receive_email_notification", None)
        payload["options"]["email_notification_to"] = "billing"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "billing")
        self.assertTrue(postage["receiveEmailNotification"])

    def test_create_shipment_request_send_notifications_to_only_does_not_imply_email(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("email_notification", None)
        payload["options"]["send_notifications_to"] = "recipient"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertNotIn("sendNotificationsTo", postage)
        self.assertNotIn("receiveEmailNotification", postage)
        self.assertNotIn("receiveSmsNotification", postage)

    def test_create_shipment_request_email_notification_target_respects_explicit_false(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"].pop("send_notifications_to", None)
        payload["options"]["email_notification_to"] = "billing"
        payload["options"]["receive_email_notification"] = False
        payload["options"].pop("email_notification", None)

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertNotIn("sendNotificationsTo", postage)
        self.assertNotIn("receiveEmailNotification", postage)
        self.assertNotIn("receiveSmsNotification", postage)

    def test_create_shipment_request_sms_notification_requires_explicit_send_notifications_target(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"].pop("send_notifications_to", None)
        payload["options"]["email_notification_to"] = "billing"
        payload["options"]["receive_email_notification"] = False
        payload["options"]["receive_sms_notification"] = True

        with self.assertRaisesRegex(
            ValueError,
            r"SMS notifications require an explicit .*send_notifications_to",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_send_notifications_to_overrides_email_notification_target(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"]["send_notifications_to"] = "recipient"
        payload["options"]["email_notification_to"] = "billing"
        payload["options"]["receive_email_notification"] = True
        payload["options"]["receive_sms_notification"] = True

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "recipient")
        self.assertTrue(postage["receiveEmailNotification"])
        self.assertTrue(postage["receiveSmsNotification"])

    def test_create_shipment_request_supports_special_instructions_alias(self):
        """Map specialInstructions into the order-level specialInstructions field."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"].pop("shipment_note", None)
        payload["options"].pop("shipper_instructions", None)
        payload["options"].pop("recipient_instructions", None)
        payload["options"]["specialInstructions"] = "Leave at loading bay"

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["specialInstructions"], "Leave at loading bay")

    def test_create_shipment_request_supports_standard_invoice_and_shipping_charge_aliases(self):
        """Allow standard Karrio aliases to feed Royal Mail monetary and invoice fields."""
        payload = copy.deepcopy(fixture.ShipmentPayloadInternational)
        payload["options"].pop("shipping_cost_charged", None)
        payload["options"].pop("commercial_invoice_number", None)
        payload["options"].pop("commercial_invoice_date", None)

        payload["options"]["shippingCharges"] = 4.75
        payload["options"]["invoiceNumber"] = "INV-STD-1001"
        payload["options"]["invoiceDate"] = "2024-02-01T10:00:00Z"

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["shippingCostCharged"], 4.75)
        self.assertEqual(
            item["postageDetails"]["commercialInvoiceNumber"],
            "INV-STD-1001",
        )
        self.assertTrue(
            item["postageDetails"]["commercialInvoiceDate"].startswith("2024-02-01T10:00:00")
        )

    def test_create_shipment_request_rejects_disallowed_service_from_config(self):
        gateway = karrio.gateway["royalmail"].create(
            {
                "id": "123456789",
                "carrier_id": "royalmail",
                "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
                "config": {
                    "shipping_services": ["tracked_returns_48"],
                },
            }
        )

        shipment = models.ShipmentRequest(**copy.deepcopy(fixture.ShipmentPayloadWithoutBilling))

        with self.assertRaisesRegex(
            ValueError,
            r"service is not allowed by `config\.shipping_services`",
        ):
            gateway.mapper.create_shipment_request(shipment)

    def test_create_shipment_request_rejects_disallowed_shipping_option_from_config(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        allowed_option_names = sorted(
            provider_units.normalize_option_keys(payload.get("options", {})).keys()
        )

        gateway = karrio.gateway["royalmail"].create(
            {
                "id": "123456789",
                "carrier_id": "royalmail",
                "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
                "config": {
                    "shipping_options": allowed_option_names,
                },
            }
        )

        payload["options"]["shipping_charges"] = 4.75
        shipment = models.ShipmentRequest(**payload)

        with self.assertRaisesRegex(
            ValueError,
            r"disallowed shipping option\(s\): shipping_charges",
        ):
            gateway.mapper.create_shipment_request(shipment)

    def test_create_shipment_parse_returns_clear_message_when_email_notification_has_no_resolvable_recipient(self):
        """Return a clear Karrio error when email notifications are enabled but no recipient can be resolved."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"].pop("send_notifications_to", None)
        payload["options"].pop("email_notification_to", None)
        payload["options"]["receive_email_notification"] = True

        payload["recipient"].pop("email", None)
        payload["shipper"].pop("email", None)

        parsed = (
            karrio.Shipment.create(self._shipment(payload))
            .from_(fixture.gateway)
            .parse()
        )

        self.assertIsNone(parsed[0])
        self.assertEqual(len(parsed[1]), 1)
        self.assertIn(
            "email notifications were requested",
            parsed[1][0].message,
        )
        self.assertIn(
            "no notification recipient could be resolved",
            parsed[1][0].message,
        )

    def test_create_shipment_request_crl48_small_parcel_uses_click_and_drop_parcel_format(self):
        """
        Royal Mail OBA CRL48 parcel services use the smallParcel rating/register
        category internally, but Click & Drop expects packageFormatIdentifier=parcel
        in the shipment API payload.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_48_Small_Parcel"
        payload["options"]["package_format_identifier"] = "small_parcel"
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        # CRL24/CRL48 do not support email notifications in this connector.
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("receive_sms_notification", None)
        payload["options"].pop("email_notification_to", None)

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "CRL48")
        self.assertEqual(postage["serviceRegisterCode"], "02")
        self.assertEqual(package["packageFormatIdentifier"], "parcel")

    def test_create_shipment_request_crl48_large_letter_keeps_large_letter_format(self):
        """
        Only parcel-like CRL24/CRL48 package formats should be collapsed to
        `parcel`. largeLetter must remain largeLetter.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_48_LargeLetter"
        payload["options"]["package_format_identifier"] = "large_letter"
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        payload["parcels"][0].update(
            {
                "weight": 100,
                "weight_unit": "G",
                "length": 30,
                "width": 20,
                "height": 2,
                "dimension_unit": "CM",
                "packaging_type": "largeLetter",
            }
        )

        self._set_single_light_item(payload, item_weight=10, item_value=1.0)

        # CRL24/CRL48 do not support email notifications in this connector.
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("receive_sms_notification", None)
        payload["options"].pop("email_notification_to", None)

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "CRL48")
        self.assertEqual(postage["serviceRegisterCode"], "01")
        self.assertEqual(package["packageFormatIdentifier"], "largeLetter")

    def test_create_shipment_request_tpn24_small_parcel_uses_click_and_drop_parcel_format(self):
        """
        Royal Mail Tracked 24 uses the smallParcel package band internally for
        rating/register resolution, but Click & Drop rejects smallParcel for TPN24.

        The outbound API packageFormatIdentifier must be `parcel`.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_tracked_24"
        payload["options"]["package_format_identifier"] = "small_parcel"
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "TPN24")
        self.assertEqual(postage["serviceRegisterCode"], "02")
        self.assertEqual(package["packageFormatIdentifier"], "parcel")

    def test_click_and_drop_package_format_resolver_maps_tpn24_small_parcel_to_parcel(self):
        self.assertEqual(
            provider_units.resolve_click_and_drop_package_format_identifier(
                "royal_mail_tracked_24",
                "smallParcel",
            ),
            "parcel",
        )


    def test_click_and_drop_package_format_resolver_keeps_large_letter(self):
        self.assertEqual(
            provider_units.resolve_click_and_drop_package_format_identifier(
                "royal_mail_48_LargeLetter",
                "largeLetter",
            ),
            "largeLetter",
        )


    def test_click_and_drop_package_format_resolver_maps_crl48_small_parcel_to_parcel(self):
        self.assertEqual(
            provider_units.resolve_click_and_drop_package_format_identifier(
                "royal_mail_48_Small_Parcel",
                "smallParcel",
            ),
            "parcel",
        )

    def test_create_shipment_request_tpn24_small_parcel_uses_click_and_drop_parcel_format(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_tracked_24"
        payload["options"]["package_format_identifier"] = "small_parcel"
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "TPN24")
        self.assertEqual(postage["serviceRegisterCode"], "02")
        self.assertEqual(package["packageFormatIdentifier"], "parcel")

    def test_create_shipment_request_tpn24_large_letter_uses_large_letter_register_code(self):
        """
        TPN24 is a Royal Mail Click & Drop product family.

        The same serviceCode can represent multiple Royal Mail products, and the
        package format determines the serviceRegisterCode:

            TPN24 + largeLetter -> serviceRegisterCode 01 / 214655TN
            TPN24 + parcel      -> serviceRegisterCode 02 / 904405TN

        Therefore a large-letter shipment must keep packageFormatIdentifier as
        largeLetter and must use serviceRegisterCode 01.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_tracked_24"
        payload["options"].pop("package_format_identifier", None)
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        payload["parcels"][0].update(
            {
                "weight": 100,
                "weight_unit": "G",
                "length": 30,
                "width": 20,
                "height": 2,
                "dimension_unit": "CM",
                "packaging_type": "largeLetter",
            }
        )

        self._set_single_light_item(payload, item_weight=10, item_value=1.0)

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "TPN24")
        self.assertEqual(postage["serviceRegisterCode"], "01")
        self.assertEqual(package["packageFormatIdentifier"], "largeLetter")

    def test_click_and_drop_package_format_resolver_maps_parcelforce_medium_parcel_to_parcel(self):
        """
        Parcelforce Click & Drop services such as NDA reject Royal Mail package
        bands like mediumParcel. They expect generic packageFormatIdentifier=parcel.
        """
        self.assertEqual(
            provider_units.resolve_click_and_drop_package_format_identifier(
                "parcel_force_express_24",
                "mediumParcel",
            ),
            "parcel",
        )

        # Also verify raw carrier service-code selector support.
        self.assertEqual(
            provider_units.resolve_click_and_drop_package_format_identifier(
                "NDA",
                "MediumParcel",
            ),
            "parcel",
        )

    def test_create_shipment_request_parcelforce_express_24_uses_config_carrier_name_and_parcel_package_format(self):
        """
        Parcelforce Click & Drop service NDA should use:

            serviceCode = NDA
            serviceRegisterCode = 01
            packageFormatIdentifier = parcel

        But carrierName must come from account config, not from a hard-coded
        service-derived value such as "Parcelforce Worldwide".
        """
        gateway = karrio.gateway["royalmail"].create(
            {
                "id": "123456789",
                "carrier_id": "royalmail",
                "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
                "tracking_client_id": "ROYALMAIL_TRACKING_CLIENT_ID",
                "tracking_client_secret": "ROYALMAIL_TRACKING_CLIENT_SECRET",
                "config": {
                    "click_and_drop_api_base_url": "https://api.parcel.royalmail.com/api/v1",
                    "tracking_api_base_url": "https://api.royalmail.net",
                    "carrier_name": "Royal Mail",
                },
            }
        )

        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "parcel_force_express_24"
        payload["options"]["package_format_identifier"] = "MediumParcel"

        # Force the request to use connection config rather than shipment option.
        payload["options"].pop("carrier_name", None)
        payload["options"].pop("carrierName", None)

        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        serialized = lib.to_dict(request.serialize())

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "NDA")
        self.assertEqual(postage["serviceRegisterCode"], "01")
        self.assertEqual(postage["carrierName"], "Royal Mail")
        self.assertEqual(package["packageFormatIdentifier"], "parcel")

    def test_click_and_drop_package_format_resolver_canonicalizes_standard_package_format_case(self):
        """
        Standard Click & Drop identifiers should be serialized using documented
        lower-camel casing, while unknown custom package formats pass through.
        """
        self.assertEqual(
            provider_units.normalize_click_and_drop_package_format_identifier(
                "MediumParcel"
            ),
            "mediumParcel",
        )
        self.assertEqual(
            provider_units.normalize_click_and_drop_package_format_identifier(
                "large letter"
            ),
            "largeLetter",
        )
        self.assertEqual(
            provider_units.normalize_click_and_drop_package_format_identifier(
                "myCustomWarehouseBox"
            ),
            "myCustomWarehouseBox",
        )

    def test_create_shipment_request_explicit_carrier_name_overrides_config(self):
        """
        Shipment option carrier_name should override connection config when
        explicitly supplied, but the connector must never replace it with a
        service-derived Parcelforce value.
        """
        gateway = karrio.gateway["royalmail"].create(
            {
                "id": "123456789",
                "carrier_id": "royalmail",
                "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
                "config": {
                    "carrier_name": "Royal Mail",
                },
            }
        )

        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "parcel_force_express_24"
        payload["options"]["package_format_identifier"] = "MediumParcel"
        payload["options"]["carrier_name"] = "Royal Mail OBA"

        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        serialized = lib.to_dict(request.serialize())

        postage = serialized["items"][0]["postageDetails"]
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(postage["serviceCode"], "NDA")
        self.assertEqual(postage["serviceRegisterCode"], "01")
        self.assertEqual(postage["carrierName"], "Royal Mail OBA")
        self.assertEqual(package["packageFormatIdentifier"], "parcel")

    def test_create_shipment_maps_karrio_insurance_to_consequential_loss(self):
        """
        Karrio UI insurance checkbox sends options.insurance.

        Royal Mail Click & Drop should receive this as:
            postageDetails.consequentialLoss

        The selected service must also include enough compensation in services.csv.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "parcel_force_express_24_insured_2500"
        payload["options"]["package_format_identifier"] = "mediumParcel"
        payload["options"]["insurance"] = 2100
        payload["options"].pop("consequential_loss", None)
        payload["options"].pop("consequentialLoss", None)

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["serviceCode"], "NDE")
        self.assertEqual(postage["serviceRegisterCode"], "01")
        self.assertEqual(postage["consequentialLoss"], 2100)

    def test_create_shipment_explicit_consequential_loss_overrides_insurance(self):
        """
        If both fields are supplied, the Royal Mail-specific option should win.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "parcel_force_express_24_insured_2500"
        payload["options"]["package_format_identifier"] = "mediumParcel"
        payload["options"]["insurance"] = 2100
        payload["options"]["consequential_loss"] = 2500

        serialized = self._serialized_request(payload)

        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["serviceCode"], "NDE")
        self.assertEqual(postage["consequentialLoss"], 2500)

    def test_create_shipment_rejects_insurance_when_selected_service_under_covers(self):
        """
        Direct shipment creation should not allow a base Parcelforce service to
        be used when the user requested compensation that requires a Comp 3
        service.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "parcel_force_express_24"
        payload["options"]["package_format_identifier"] = "mediumParcel"
        payload["options"]["insurance"] = 2100

        with self.assertRaisesRegex(
            ValueError,
            "only includes compensation cover",
        ):
            self._serialized_request(payload)

    def test_create_shipment_request_tpn24_register_code_follows_package_format(self):
        """
        TPN24 uses serviceRegisterCode 01 for large letters and 02 for parcels.
        """
        cases = [
            {
                "package_format_identifier": None,
                "packaging_type": "largeLetter",
                "weight": 100,
                "length": 30,
                "width": 20,
                "height": 2,
                "expected_package_format": "largeLetter",
                "expected_register_code": "01",
            },
            {
                "package_format_identifier": "small_parcel",
                "packaging_type": "smallParcel",
                "weight": 1000,
                "length": 30,
                "width": 20,
                "height": 10,
                "expected_package_format": "parcel",
                "expected_register_code": "02",
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

                payload["service"] = "royal_mail_tracked_24"
                payload["options"]["carrier_name"] = "Royal Mail OBA"

                if case["package_format_identifier"] is None:
                    payload["options"].pop("package_format_identifier", None)
                else:
                    payload["options"]["package_format_identifier"] = case[
                        "package_format_identifier"
                    ]

                payload["parcels"][0].update(
                    {
                        "weight": case["weight"],
                        "weight_unit": "G",
                        "length": case["length"],
                        "width": case["width"],
                        "height": case["height"],
                        "dimension_unit": "CM",
                        "packaging_type": case["packaging_type"],
                    }
                )

                self._set_single_light_item(payload, item_weight=10, item_value=1.0)

                serialized = self._serialized_request(payload)

                postage = serialized["items"][0]["postageDetails"]
                package = serialized["items"][0]["packages"][0]

                self.assertEqual(postage["serviceCode"], "TPN24")
                self.assertEqual(
                    postage["serviceRegisterCode"],
                    case["expected_register_code"],
                )
                self.assertEqual(
                    package["packageFormatIdentifier"],
                    case["expected_package_format"],
                )

    def test_shipment_rejects_zero_dimensions(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)
        payload["parcels"][0]["height"] = 0

        with self.assertRaisesRegex(ValueError, "dimensions.*non-zero"):
            fixture.gateway.mapper.create_shipment_request(
                models.ShipmentRequest(**payload)
            )
    def test_gb_to_gb_residential_recipient_sets_is_recipient_a_business_false(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "LL615SJ"
        payload["recipient"]["residential"] = True

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            False,
        )

    def test_gb_to_gb_business_recipient_sets_is_recipient_a_business_true(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "LL615SJ"
        payload["recipient"]["residential"] = False

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            True,
        )

    def test_gb_to_international_residential_recipient_sets_is_recipient_a_business_false(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadInternational)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "FR"
        payload["recipient"]["postal_code"] = "75001"
        payload["recipient"]["residential"] = True

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            False,
        )

    def test_gb_to_international_business_recipient_sets_is_recipient_a_business_true(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadInternational)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "FR"
        payload["recipient"]["postal_code"] = "75001"
        payload["recipient"]["residential"] = False

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            True,
        )

    def test_gb_to_ni_residential_recipient_sets_is_recipient_a_business_false(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "BT1 1AA"
        payload["recipient"]["residential"] = True

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            False,
        )

    def test_gb_to_ni_business_recipient_sets_is_recipient_a_business_true(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "BT1 1AA"
        payload["recipient"]["residential"] = False

        request = fixture.gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["isRecipientABusiness"],
            True,
        )

    def test_gb_to_ni_requires_recipient_residential_flag_when_unknown(self):
        payload = copy.deepcopy(fixture.ShipmentPayload)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "LL536NH"
        payload["shipper"]["residential"] = False

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "BT1 1AA"

        # Do not pop the key. Karrio's Address model defaults missing
        # residential to False, so popping it will still normalize to business.
        # Use None to explicitly simulate an unknown residential/business state.
        payload["recipient"]["residential"] = None

        with self.assertRaisesRegex(ValueError, "recipient.residential"):
            fixture.gateway.mapper.create_shipment_request(
                models.ShipmentRequest(**payload)
            )