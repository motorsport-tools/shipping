"""Royal Mail Click and Drop carrier settings tests."""

import copy
import unittest

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

from .fixture import ShipmentPayload, ManifestPayload


class TestRoyalMailClickandDropSettings(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _gateway(self, config=None):
        return karrio.gateway["royalmail_clickdrop"].create(
            dict(
                id="123456789",
                test_mode=False,
                carrier_id="royalmail_clickdrop",
                api_key="TEST_API_KEY",
                #for future use of import and export accounts
                account_number="123456789",
                config=config or {},
            )
        )

    def test_server_url_uses_connection_config_base_url(self):
        gateway = self._gateway(
            config={
                "base_url": "https://example.test/custom/api/",
            }
        )

        print("DEBUG server_url:", gateway.settings.server_url)
        print(
            "DEBUG connection_config.base_url.state:",
            gateway.settings.connection_config.base_url.state,
        )

        self.assertEqual(
            gateway.settings.connection_config.base_url.state,
            "https://example.test/custom/api/",
        )
        self.assertEqual(
            gateway.settings.server_url,
            "https://example.test/custom/api",
        )

    def test_shipping_carrier_name_uses_connection_config_state(self):
        gateway = self._gateway(
            config={
                "carrier_name": "Royal Mail OBA",
            }
        )

        print(
            "DEBUG connection_config.carrier_name.state:",
            gateway.settings.connection_config.carrier_name.state,
        )
        print(
            "DEBUG settings.shipping_carrier_name:",
            gateway.settings.shipping_carrier_name,
        )

        self.assertEqual(
            gateway.settings.connection_config.carrier_name.state,
            "Royal Mail OBA",
        )
        self.assertEqual(
            gateway.settings.shipping_carrier_name,
            "Royal Mail OBA",
        )

    def test_shipment_request_uses_connection_config_carrier_name(self):
        gateway = self._gateway(
            config={
                "carrier_name": "Royal Mail OBA",
            }
        )

        payload = copy.deepcopy(ShipmentPayload)
        payload["options"].pop("carrier_name", None)

        shipment = models.ShipmentRequest(**payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print(
            "DEBUG shipment carrierName from connection config:",
            serialized["items"][0]["postageDetails"].get("carrierName"),
        )
        print("DEBUG shipment request:", serialized)

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["carrierName"],
            "Royal Mail OBA",
        )

    def test_manifest_request_uses_connection_config_carrier_name(self):
        gateway = self._gateway(
            config={
                "carrier_name": "Royal Mail OBA",
            }
        )

        payload = copy.deepcopy(ManifestPayload)
        payload["options"].pop("carrier_name", None)

        manifest = models.ManifestRequest(**payload)
        request = gateway.mapper.create_manifest_request(manifest)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG manifest request:", serialized)

        self.assertEqual(
            serialized,
            {
                "carrierName": "Royal Mail OBA",
            },
        )

    def test_request_option_carrier_name_overrides_connection_config(self):
        gateway = self._gateway(
            config={
                "carrier_name": "Royal Mail Default",
            }
        )

        shipment = models.ShipmentRequest(**ShipmentPayload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print(
            "DEBUG shipment carrierName from request options:",
            serialized["items"][0]["postageDetails"].get("carrierName"),
        )
        print("DEBUG shipment request:", serialized)

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["carrierName"],
            "Royal Mail OBA",
        )


if __name__ == "__main__":
    unittest.main()
