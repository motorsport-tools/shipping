"""Royal Mail Click and Drop shipment validation tests."""

import copy
import unittest

import karrio.sdk as karrio
import karrio.core.errors as errors
import karrio.core.models as models
import karrio.lib as lib

from . import fixture


class TestRoyalMailClickandDropShipmentValidations(unittest.TestCase):
    def _create_request(self, payload):
        shipment = models.ShipmentRequest(**copy.deepcopy(payload))
        return fixture.gateway.mapper.create_shipment_request(shipment)

    def test_create_shipment_request_maps_email_notification_to_matching_billing_email(self):
        """Resolve email_notification_to to the billing target when it matches the billing email address."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"].pop("send_notifications_to", None)
        payload["options"]["email_notification_to"] = "billing@example.com"
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("email_notification", None)

        serialized = lib.to_dict(self._create_request(payload).serialize())
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "billing")
        self.assertTrue(postage["receiveEmailNotification"])

    def test_create_shipment_request_rejects_arbitrary_email_notification_to_address(self):
        """Reject arbitrary email_notification_to values that Royal Mail cannot map to recipient, sender, or billing."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithBilling)
        payload["options"].pop("send_notifications_to", None)
        payload["options"]["email_notification_to"] = "other@example.com"

        with self.assertRaisesRegex(
            ValueError,
            r"does not support arbitrary `email_notification_to` addresses",
        ):
            self._create_request(payload)

    def test_create_shipment_request_requires_subtotal_when_not_derivable(self):
        """Reject requests when Royal Mail-required subtotal cannot be determined."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["parcels"][0]["items"] = [{"sku": "SKU-1", "quantity": 1}]

        with self.assertRaisesRegex(ValueError, r"requires `subtotal`"):
            self._create_request(payload)

    def test_create_shipment_request_validates_consequential_loss_upper_bound(self):
        """Reject consequential loss values above the Royal Mail API maximum."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["consequential_loss"] = 10001

        with self.assertRaisesRegex(
            ValueError,
            r"`consequentialLoss` must be less than or equal to 10000",
        ):
            self._create_request(payload)

    def test_create_shipment_request_rejects_parcel_level_order_option_promotion_attempts(self):
        """
        Parcel-level Royal Mail order/postage options are invalid and must be rejected
        rather than promoted to shipment-level fields.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["shipping_charges"] = 3.5

        payload["parcels"][0]["options"] = {
            "shipping_charges": 99.0,
            "shipment_note": "parcel-level note should not become order special instructions",
        }

        with self.assertRaisesRegex(
            ValueError,
            r"unsupported Royal Mail package-level option\(s\): .*shipment_note.*shipping_charges|.*shipping_charges.*shipment_note",
        ):
            self._create_request(payload)


    def test_create_shipment_request_allows_multi_package_parcels(self):
        """
        Royal Mail Click & Drop supports multi-package shipments for parcel package kinds.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)

        serialized = lib.to_dict(self._create_request(payload).serialize())
        item = serialized["items"][0]

        self.assertEqual(len(item["packages"]), 2)


    def test_create_shipment_request_rejects_multi_package_letters(self):
        """
        Letters and large letters must be single-piece shipments.

        Keep item weights below package weights so this test exercises the
        multi-package letter rule, not the package-weight-vs-contents validator.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)
        payload["options"].pop("package_format_identifier", None)

        payload["parcels"][0].update(
            {
                "weight": 80,
                "weight_unit": "G",
                "length": 20,
                "width": 15,
                "height": 0.4,
                "dimension_unit": "CM",
                "packaging_type": "envelope",
            }
        )
        payload["parcels"][0]["items"] = [
            {
                "sku": "SKU-LETTER-1",
                "description": "Letter Insert",
                "quantity": 1,
                "value_amount": 1.0,
                "weight": 10,
                "weight_unit": "G",
                "hs_code": "491199",
                "origin_country": "GB",
            }
        ]

        payload["parcels"][1].update(
            {
                "weight": 90,
                "weight_unit": "G",
                "length": 22,
                "width": 16,
                "height": 0.5,
                "dimension_unit": "CM",
                "packaging_type": "envelope",
            }
        )
        payload["parcels"][1]["items"] = [
            {
                "sku": "SKU-LETTER-2",
                "description": "Letter Insert",
                "quantity": 1,
                "value_amount": 1.0,
                "weight": 10,
                "weight_unit": "G",
                "hs_code": "491199",
                "origin_country": "GB",
            }
        ]

        with self.assertRaisesRegex(
            ValueError,
            r"only supports multi-package shipments for parcel package formats",
        ):
            self._create_request(payload)

    def test_create_shipment_request_allows_parcel_level_package_format_identifier(self):
        """
        Parcel-level package_format_identifier is supported and overrides the
        shipment-level default for that parcel.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)
        payload["options"]["package_format_identifier"] = "medium_parcel"
        payload["parcels"][1]["options"] = {
            "packageFormatIdentifier": "smallParcel",
        }

        serialized = lib.to_dict(self._create_request(payload).serialize())
        packages = serialized["items"][0]["packages"]

        self.assertEqual(packages[0]["packageFormatIdentifier"], "parcel")
        self.assertEqual(packages[1]["packageFormatIdentifier"], "parcel")

    def test_create_shipment_request_rejects_parcel_level_service_override(self):
        """
        service_code is shipment-level and must not be supplied per parcel.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["options"] = {
            "serviceCode": "CRL48",
        }

        with self.assertRaisesRegex(
            ValueError,
            r"unsupported Royal Mail package-level option\(s\): service_code",
        ):
            self._create_request(payload)

    def test_create_shipment_request_rejects_parcel_level_notification_override(self):
        """
        Notification settings are shipment/postage-level and must not be supplied
        per parcel.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["options"] = {
            "sendNotificationsTo": "recipient",
        }

        with self.assertRaisesRegex(
            ValueError,
            r"unsupported Royal Mail package-level option\(s\): send_notifications_to",
        ):
            self._create_request(payload)

    def test_create_shipment_request_rejects_parcel_level_order_value_override(self):
        """
        Order value/invoice fields are shipment-level and must not be supplied per
        parcel.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["parcels"][0]["options"] = {
            "shippingCharges": 9.99,
            "invoiceNumber": "INV-PARCEL-1",
        }

        with self.assertRaisesRegex(
            ValueError,
            r"unsupported Royal Mail package-level option\(s\): .*invoice_number.*shipping_charges|.*shipping_charges.*invoice_number",
        ):
            self._create_request(payload)

    def test_create_shipment_request_rejects_mixed_letter_and_parcel_package_format_overrides(self):
        """
        Even with parcel-level package_format_identifier support, Royal Mail does
        not allow mixing letter/large-letter with parcel shipments.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)
        payload["options"].pop("package_format_identifier", None)

        payload["parcels"][0]["options"] = {
            "packageFormatIdentifier": "letter",
        }
        payload["parcels"][1]["options"] = {
            "packageFormatIdentifier": "smallParcel",
        }

        with self.assertRaisesRegex(
            ValueError,
            r"only supports multi-package shipments for parcel package formats",
        ):
            self._create_request(payload)

    def test_create_shipment_request_rejects_package_weight_less_than_contents(self):
        """
        Reject packages where the package weight is lower than the total declared
        contents weight.

        Example:
            package.weight = 9 g
            item.weight = 13 g

        This should fail locally before the request is sent to Click & Drop.
        """
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["parcels"][0]["weight"] = 9
        payload["parcels"][0]["weight_unit"] = "G"

        payload["parcels"][0]["items"] = [
            {
                "sku": "SKU-WEIGHT-1",
                "title": "Weighted item",
                "quantity": 1,
                "weight": 13,
                "weight_unit": "G",
                "value_amount": 10.0,
                "value_currency": "GBP",
            }
        ]

        with self.assertRaises(errors.ParsedMessagesError) as context:
            self._create_request(payload)

        messages = lib.to_dict(context.exception.messages)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["code"], "package_weight_less_than_contents")
        self.assertIn(
            "Package weight cannot be less than the total weight of its contents",
            messages[0]["message"],
        )
        self.assertEqual(messages[0]["details"]["field"], "parcels[0].weight")
        self.assertEqual(messages[0]["details"]["package_weight_in_grams"], 9)
        self.assertEqual(messages[0]["details"]["contents_weight_in_grams"], 13)
        self.assertEqual(messages[0]["details"]["minimum_package_weight_in_grams"], 13)

    def test_create_shipment_bubbles_package_weight_less_than_contents_message(self):
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)

        payload["parcels"][0]["weight"] = 9
        payload["parcels"][0]["weight_unit"] = "G"

        payload["parcels"][0]["items"] = [
            {
                "sku": "SKU-WEIGHT-1",
                "title": "Weighted item",
                "quantity": 1,
                "weight": 13,
                "weight_unit": "G",
                "value_amount": 10.0,
                "value_currency": "GBP",
            }
        ]

        shipment, messages = lib.to_dict(
            karrio.Shipment.create(
                models.ShipmentRequest(**payload)
            ).from_(fixture.gateway).parse()
        )

        self.assertIsNone(shipment)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["code"], "package_weight_less_than_contents")
        self.assertEqual(messages[0]["details"]["package_weight_in_grams"], 9)
        self.assertEqual(messages[0]["details"]["contents_weight_in_grams"], 13)