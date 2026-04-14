"""Royal Mail Click and Drop carrier shipment cancel tests."""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

from .fixture import (
    gateway,
    ShipmentCancelPayload,
    ShipmentCancelResponse,
    ShipmentCancelErrorResponse,
)


class TestRoyalMailClickandDropCancel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentCancelRequest = models.ShipmentCancelRequest(**ShipmentCancelPayload)

    def test_create_cancel_shipment_request(self):
        request = gateway.mapper.create_cancel_shipment_request(self.ShipmentCancelRequest)
        serialized = request.serialize()

        print("DEBUG create cancel shipment request:", serialized)

        self.assertEqual(serialized["orderIdentifiers"], "12345678")

    def test_cancel_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.cancel(self.ShipmentCancelRequest).from_(gateway)

            print("DEBUG cancel shipment call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678",
            )
            self.assertEqual(mock.call_args[1]["method"], "DELETE")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )

    def test_parse_cancel_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentCancelResponse

            confirmation, messages = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed cancel confirmation:", lib.to_dict(confirmation) if confirmation else None)
            print("DEBUG parsed cancel messages:", lib.to_dict(messages))

            self.assertIsNotNone(confirmation)
            self.assertEqual(len(messages), 0)
            self.assertTrue(confirmation.success)
            self.assertEqual(confirmation.operation, "Cancel Shipment")
            self.assertEqual(confirmation.carrier_id, "royalmail_clickdrop")

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentCancelErrorResponse

            confirmation, messages = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed cancel error confirmation:", confirmation)
            print("DEBUG parsed cancel error messages:", lib.to_dict(messages))

            self.assertIsNone(confirmation)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "NotFound")
            self.assertEqual(messages[0].message, "Order not found")


if __name__ == "__main__":
    unittest.main()
