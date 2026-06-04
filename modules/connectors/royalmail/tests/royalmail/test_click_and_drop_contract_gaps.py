"""Additional Royal Mail Click & Drop create-order contract tests.

These tests focus on Click & Drop OpenAPI contract fields that are easy to
regress because they are optional, edge-case, or mapped through Royal Mail
shipping options.
"""

import copy
import unittest

import karrio.core.models as models
import karrio.lib as lib

from . import fixture


class TestRoyalMailClickAndDropCreateOrderContractGaps(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _serialized_request(self, payload):
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(payload)
        )
        return lib.to_dict(request.serialize())

    def test_serializes_optional_postage_detail_fields_from_click_and_drop_spec(self):
        """Serialize optional Click & Drop postageDetails fields, not only service fields."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["recipient"]["phone_number"] = "07123456789"
        payload["recipient"]["email"] = "john@example.com"

        payload["options"].update(
            {
                "send_notifications_to": "recipient",
                "receive_email_notification": True,
                "receive_sms_notification": True,
                "request_signature_upon_delivery": True,
                "is_local_collect": True,
                "safe_place": "Front porch",
                "department": "Dispatch",
                "guaranteed_saturday_delivery": True,
                "requires_export_license": True,
            }
        )

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "recipient")
        self.assertEqual(postage["receiveEmailNotification"], True)
        self.assertEqual(postage["receiveSmsNotification"], True)
        self.assertEqual(postage["requestSignatureUponDelivery"], True)
        self.assertEqual(postage["isLocalCollect"], True)
        self.assertEqual(postage["safePlace"], "Front porch")
        self.assertEqual(postage["department"], "Dispatch")
        self.assertEqual(postage["guaranteedSaturdayDelivery"], True)
        self.assertEqual(postage["requiresExportLicense"], True)

    def test_royalmail_id_verification_implies_signature_request(self):
        """Royal Mail ID verification should map to requestSignatureUponDelivery."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"].pop("request_signature_upon_delivery", None)
        payload["options"]["royalmail_id_verification"] = True

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["requestSignatureUponDelivery"], True)

    def test_serializes_dangerous_goods_fields(self):
        """Serialize Click & Drop dangerous-goods fields from Royal Mail options."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"].update(
            {
                "contains_dangerous_goods": True,
                "dangerous_goods_un_code": "1950",
                "dangerous_goods_description": "Aerosols, limited quantity",
                "dangerous_goods_quantity": 2.5,
            }
        )

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["containsDangerousGoods"], True)
        self.assertEqual(item["dangerousGoodsUnCode"], "1950")
        self.assertEqual(
            item["dangerousGoodsDescription"],
            "Aerosols, limited quantity",
        )
        self.assertEqual(item["dangerousGoodsQuantity"], 2.5)

    def test_serializes_shipment_level_custom_package_format_identifier(self):
        """Serialize customPackageFormatIdentifier when supplied at shipment level."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"]["custom_package_format_identifier"] = "Warehouse Custom Box"

        serialized = self._serialized_request(payload)
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(
            package["customPackageFormatIdentifier"],
            "Warehouse Custom Box",
        )

    def test_serializes_parcel_level_custom_package_format_identifier(self):
        """Parcel-level customPackageFormatIdentifier should override shipment-level default."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"]["custom_package_format_identifier"] = "Shipment Custom Box"
        payload["parcels"][0]["options"] = {
            "custom_package_format_identifier": "Parcel Custom Box",
        }

        serialized = self._serialized_request(payload)
        package = serialized["items"][0]["packages"][0]

        self.assertEqual(
            package["customPackageFormatIdentifier"],
            "Parcel Custom Box",
        )

def test_click_and_drop_string_fields_are_capped_to_openapi_max_lengths(self):
    """Ensure generated payload does not exceed important Click & Drop maxLength values."""
    payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

    payload["options"].update(
        {
            "order_reference": "R" * 80,
            "carrier_name": "C" * 80,
            "safe_place": "S" * 120,
            "department": "D" * 200,
            "tags": [
                {
                    "key": "K" * 140,
                    "value": "V" * 140,
                }
            ],
            # Raw Click & Drop-shaped billing data is supported through options.
            # This lets us test addressLine3, which Karrio's normalized Address
            # model does not expose on recipient/shipper addresses.
            "billing": {
                "address": {
                    "fullName": "B" * 250,
                    "companyName": "Billing Company " + ("C" * 150),
                    "addressLine1": "Billing Line 1 " + ("A" * 150),
                    "addressLine2": "Billing Line 2 " + ("B" * 150),
                    "addressLine3": "Billing Line 3 " + ("C" * 150),
                    "city": "Billing City " + ("X" * 120),
                    "county": "Billing County " + ("Y" * 120),
                    "postcode": "P" * 40,
                    "countryCode": "GBR",
                },
                "phoneNumber": "0" * 40,
                "emailAddress": ("billing-" + ("e" * 260) + "@example.com"),
            },
        }
    )

    payload["recipient"].update(
        {
            "person_name": "N" * 250,
            "company_name": "Company " + ("C" * 120),
            "address_line1": "A" * 150,
            "address_line2": "B" * 150,
            # Do not use address_line3 here. Karrio's normalized Address model
            # does not accept it, so jstruct drops it as an unknown argument.
            "city": "City " + ("X" * 120),
            "state_code": "County " + ("Y" * 120),
            "postal_code": "P" * 40,
            "phone_number": "0" * 40,
            "email": ("recipient-" + ("e" * 260) + "@example.com"),
        }
    )

    payload["shipper"]["company_name"] = "Warehouse " + ("W" * 300)

    payload["parcels"][0]["items"][0].update(
        {
            "sku": "SKU-" + ("S" * 150),
            "description": "Description " + ("D" * 900),
            "hs_code": "123456789012345",
        }
    )

    payload["parcels"][0]["items"][0]["metadata"].update(
        {
            "stock_location": "L" * 80,
            "supplementary_units": "U" * 30,
            "license_number": "LIC-" + ("L" * 80),
            "certificate_number": "CERT-" + ("C" * 80),
        }
    )

    serialized = self._serialized_request(payload)

    item = serialized["items"][0]
    recipient_address = item["recipient"]["address"]
    billing = item["billing"]
    billing_address = billing["address"]
    postage = item["postageDetails"]
    content = item["packages"][0]["contents"][0]

    self.assertLessEqual(len(item["orderReference"]), 40)

    # Recipient address limits.
    self.assertLessEqual(len(recipient_address["fullName"]), 210)
    self.assertLessEqual(len(recipient_address["companyName"]), 100)
    self.assertLessEqual(len(recipient_address["addressLine1"]), 100)
    self.assertLessEqual(len(recipient_address["addressLine2"]), 100)
    self.assertLessEqual(len(recipient_address["city"]), 100)
    self.assertLessEqual(len(recipient_address["county"]), 100)
    self.assertLessEqual(len(recipient_address["postcode"]), 20)
    self.assertLessEqual(len(recipient_address["countryCode"]), 3)

    # addressLine3 is not available on Karrio's normalized recipient Address.
    self.assertNotIn("addressLine3", recipient_address)

    self.assertLessEqual(len(item["recipient"]["phoneNumber"]), 25)
    self.assertLessEqual(len(item["recipient"]["emailAddress"]), 254)

    # Billing address limits, including Click & Drop addressLine3.
    self.assertLessEqual(len(billing_address["fullName"]), 210)
    self.assertLessEqual(len(billing_address["companyName"]), 100)
    self.assertLessEqual(len(billing_address["addressLine1"]), 100)
    self.assertLessEqual(len(billing_address["addressLine2"]), 100)
    self.assertLessEqual(len(billing_address["addressLine3"]), 100)
    self.assertLessEqual(len(billing_address["city"]), 100)
    self.assertLessEqual(len(billing_address["county"]), 100)
    self.assertLessEqual(len(billing_address["postcode"]), 20)
    self.assertLessEqual(len(billing_address["countryCode"]), 3)

    self.assertLessEqual(len(billing["phoneNumber"]), 25)
    self.assertLessEqual(len(billing["emailAddress"]), 254)

    self.assertLessEqual(len(item["sender"]["tradingName"]), 250)

    self.assertLessEqual(len(postage["carrierName"]), 50)
    self.assertLessEqual(len(postage["safePlace"]), 90)
    self.assertLessEqual(len(postage["department"]), 150)

    self.assertLessEqual(len(item["tags"][0]["key"]), 100)
    self.assertLessEqual(len(item["tags"][0]["value"]), 100)

    self.assertLessEqual(len(content["SKU"]), 100)
    self.assertLessEqual(len(content["name"]), 800)
    self.assertLessEqual(len(content["customsDescription"]), 50)
    self.assertLessEqual(len(content["extendedCustomsDescription"]), 300)
    self.assertLessEqual(len(content["customsCode"]), 10)
    self.assertLessEqual(len(content["stockLocation"]), 50)
    self.assertLessEqual(len(content["supplementaryUnits"]), 17)
    self.assertLessEqual(len(content["licenseNumber"]), 41)
    self.assertLessEqual(len(content["certificateNumber"]), 41)

    def test_omits_dimensions_when_no_dimensions_are_supplied(self):
        """Click & Drop dimensions are optional and should be omitted when absent."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        for key in ["height", "width", "length", "dimension_unit"]:
            payload["parcels"][0].pop(key, None)

        serialized = self._serialized_request(payload)
        package = serialized["items"][0]["packages"][0]

        self.assertNotIn("dimensions", package)

    def test_rejects_partial_dimensions(self):
        """If dimensions are supplied, height, width, and depth must all be non-zero."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["parcels"][0].pop("height", None)
        payload["parcels"][0]["width"] = 18
        payload["parcels"][0]["length"] = 25
        payload["parcels"][0]["dimension_unit"] = "CM"

        with self.assertRaisesRegex(ValueError, "dimensions.*non-zero"):
            self._serialized_request(payload)

    def test_rejects_negative_shipping_cost_charged(self):
        """Click & Drop shippingCostCharged minimum is 0."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"]["shipping_cost_charged"] = -0.01

        with self.assertRaisesRegex(ValueError, "shippingCostCharged.*greater than or equal to 0"):
            self._serialized_request(payload)

    def test_rejects_negative_other_costs(self):
        """Click & Drop otherCosts minimum is 0."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"]["other_costs"] = -0.01

        with self.assertRaisesRegex(ValueError, "otherCosts.*greater than or equal to 0"):
            self._serialized_request(payload)

    def test_rejects_order_tax_above_click_and_drop_maximum(self):
        """Click & Drop orderTax maximum is 999999."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"]["order_tax"] = 1000000

        with self.assertRaisesRegex(ValueError, "orderTax.*less than or equal to 999999"):
            self._serialized_request(payload)

    def test_rejects_service_register_code_that_does_not_match_package_format(self):
        """Do not allow a caller to override serviceRegisterCode inconsistently."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["service"] = "royal_mail_tracked_24"
        payload["options"]["package_format_identifier"] = "small_parcel"
        payload["options"]["service_register_code"] = "99"

        with self.assertRaisesRegex(ValueError, "service_register_code.*does not match"):
            self._serialized_request(payload)

    def test_gb_to_ni_serializes_air_number_only_for_northern_ireland(self):
        """AIRNumber/UKIMS should be sent for GB -> Northern Ireland movements."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "SW1A1AA"

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "BT1 1AA"
        payload["recipient"]["residential"] = False

        payload["options"]["air_number"] = "UKIMS123456789"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["AIRNumber"], "UKIMS123456789")

    def test_non_ni_shipment_omits_air_number_even_when_option_is_present(self):
        """AIRNumber should not leak onto normal GB domestic shipments."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["shipper"]["country_code"] = "GB"
        payload["shipper"]["postal_code"] = "SW1A1AA"

        payload["recipient"]["country_code"] = "GB"
        payload["recipient"]["postal_code"] = "EC1A1AA"

        payload["options"]["air_number"] = "UKIMS123456789"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertNotIn("AIRNumber", postage)

    def test_email_notification_to_sender_implies_email_notification(self):
        """email_notification_to should enable email notification and select that target."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["options"].pop("send_notifications_to", None)
        payload["options"].pop("receive_email_notification", None)
        payload["options"]["email_notification_to"] = "sender"

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "sender")
        self.assertEqual(postage["receiveEmailNotification"], True)