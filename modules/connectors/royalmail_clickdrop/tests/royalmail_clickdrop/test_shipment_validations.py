"""Royal Mail Click and Drop shipment validation tests."""

import copy
import unittest

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