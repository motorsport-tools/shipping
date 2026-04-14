"""Royal Mail Click and Drop carrier services tests."""

import copy
import unittest

import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.plugins.royalmail_clickdrop as plugin
import karrio.core.models as models

from .fixture import gateway, ShipmentPayload


class TestRoyalMailClickandDropServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_services_catalog_loads(self):
        services = provider_units.DEFAULT_SERVICES or []

        print("DEBUG loaded service levels count:", len(services))
        print(
            "DEBUG first services:",
            [
                {
                    "service_code": s.service_code,
                    "carrier_service_code": s.carrier_service_code,
                    "service_name": s.service_name,
                }
                for s in services[:10]
            ],
        )

        self.assertGreater(len(services), 0)

        tpn24 = next((s for s in services if s.service_code == "tpn24_01"), None)
        self.assertIsNotNone(tpn24)
        self.assertEqual(tpn24.carrier_service_code, "TPN24")
        self.assertEqual(tpn24.service_name, "Tracked 24 (01 / 214655TN)")

    def test_plugin_metadata_exposes_service_levels(self):
        metadata = plugin.METADATA
        service_levels = metadata.service_levels or []

        print("DEBUG plugin metadata id:", metadata.id)
        print("DEBUG plugin service level count:", len(service_levels))

        self.assertEqual(metadata.id, "royalmail_clickdrop")
        self.assertGreater(len(service_levels), 0)

        codes = [s.service_code for s in service_levels]
        self.assertIn("tpn24_01", codes)
        self.assertIn("fe0_01", codes)

    def test_resolve_carrier_service(self):
        print(
            "DEBUG resolve csv service by CSV key:",
            provider_units.resolve_carrier_service("tpn24_01"),
        )
        print(
            "DEBUG resolve enum alias:",
            provider_units.resolve_carrier_service("tracked_24"),
        )
        print(
            "DEBUG resolve exact enum alias:",
            provider_units.resolve_carrier_service("express_48"),
        )
        print(
            "DEBUG resolve exact carrier code:",
            provider_units.resolve_carrier_service("TPN24"),
        )

        self.assertEqual(provider_units.resolve_carrier_service("tpn24_01"), "TPN24")
        self.assertEqual(provider_units.resolve_carrier_service("tracked_24"), "TPN24")
        self.assertEqual(provider_units.resolve_carrier_service("express_48"), "FE0")
        self.assertEqual(provider_units.resolve_carrier_service("TPN24"), "TPN24")

    def test_resolve_unknown_service_returns_none(self):
        print(
            "DEBUG resolve unknown service:",
            provider_units.resolve_carrier_service("TPN"),
        )

        self.assertIsNone(provider_units.resolve_carrier_service("TPN"))
        self.assertIsNone(provider_units.resolve_carrier_service("express48"))
        self.assertIsNone(provider_units.resolve_carrier_service("not_a_service"))

    def test_shipment_request_uses_resolved_csv_service_code(self):
        payload = copy.deepcopy(ShipmentPayload)
        payload["service"] = "tpn24_01"
        payload["options"].pop("service_code", None)

        shipment = models.ShipmentRequest(**payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG shipment request from csv service selector:", serialized)

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["serviceCode"],
            "TPN24",
        )

    def test_shipment_request_uses_exact_carrier_service_code(self):
        payload = copy.deepcopy(ShipmentPayload)
        payload["service"] = "TPN24"
        payload["options"].pop("service_code", None)

        shipment = models.ShipmentRequest(**payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print("DEBUG shipment request from exact carrier service code:", serialized)

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["serviceCode"],
            "TPN24",
        )


if __name__ == "__main__":
    unittest.main()
