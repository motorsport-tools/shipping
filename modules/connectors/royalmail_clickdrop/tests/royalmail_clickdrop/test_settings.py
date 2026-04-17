"""Royal Mail Click and Drop carrier settings tests."""

import copy
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from .fixture import ShipmentPayload, ManifestPayload, ExpectedDefaultConnectionConfig


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
                account_number="123456789",
                config=config or {},
            )
        )

    def test_default_settings_values(self):
        gateway = self._gateway()

        print("DEBUG default server_url:", gateway.settings.server_url)
        print("DEBUG default headers:", gateway.settings.headers)
        print("DEBUG default label_type:", gateway.settings.label_type)


        self.assertEqual(
            gateway.settings.server_url,
            ExpectedDefaultConnectionConfig["base_url"],
        )
        self.assertEqual(gateway.settings.authorization, "Bearer TEST_API_KEY")
        self.assertEqual(
            gateway.settings.label_type,
            ExpectedDefaultConnectionConfig["label_type"],
        )
        self.assertIsInstance(gateway.settings.metadata, dict)
        self.assertIsInstance(gateway.settings.config, dict)

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

    def test_request_option_carrier_name_overrides_connection_config(self):
        gateway = self._gateway(
            config={
                "carrier_name": "Royal Mail Default",
            }
        )

        shipment_payload = copy.deepcopy(ShipmentPayload)
        shipment_payload["options"]["carrier_name"] = "Royal Mail OBA"

        shipment = models.ShipmentRequest(**shipment_payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG shipment request:", serialized)

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["carrierName"],
            "Royal Mail OBA",
        )

        manifest_payload = copy.deepcopy(ManifestPayload)
        manifest_payload["options"].pop("carrier_name", None)

        manifest = models.ManifestRequest(**manifest_payload)
        manifest_request = gateway.mapper.create_manifest_request(manifest)
        manifest_serialized = lib.to_dict(manifest_request.serialize())

        print("DEBUG manifest request from connection config:", manifest_serialized)

        self.assertEqual(
            manifest_serialized,
            {
                "carrierName": "Royal Mail Default",
            },
        )


if __name__ == "__main__":
    unittest.main()