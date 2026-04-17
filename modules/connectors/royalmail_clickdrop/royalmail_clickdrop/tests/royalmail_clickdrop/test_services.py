"""Royal Mail Click and Drop carrier services tests."""

import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.plugins.royalmail_clickdrop as plugin
import karrio.providers.royalmail_clickdrop.units as provider_units

from .fixture import (
    gateway,
    ShipmentPayload,
    ShipmentPayloadEnvelopePackaging,
    ShipmentPayloadInferredLetter,
    ShipmentPayloadInferredLargeLetter,
    ShipmentPayloadInferredParcel,
    ExpectedCoreServices,
)


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

        codes = [s.service_code for s in services]
        for code in ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_plugin_metadata_exposes_service_levels(self):
        metadata = plugin.METADATA
        service_levels = metadata.service_levels or []

        print("DEBUG plugin metadata id:", metadata.id)
        print("DEBUG plugin service level count:", len(service_levels))

        self.assertEqual(metadata.id, "royalmail_clickdrop")
        self.assertGreater(len(service_levels), 0)

        codes = [s.service_code for s in service_levels]
        for code in ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_resolve_carrier_service(self):
        scenarios = [
            ("csv_service_key", "tpn24_01", "TPN24"),
            ("enum_alias", "tracked_24", "TPN24"),
            ("exact_carrier_code", "TPN24", "TPN24"),
            ("return_alias", "tracked_returns_48", "TSS"),
            ("return_exact_code", "TSS", "TSS"),
            ("unknown", "not_a_service", None),
        ]

        for name, selector, expected in scenarios:
            with self.subTest(name=name):
                resolved = provider_units.resolve_carrier_service(selector)

                print(f"DEBUG resolve carrier service [{name}]:", selector, resolved)

                self.assertEqual(resolved, expected)

    def test_return_service_detection(self):
        for selector in ["tracked_returns_48", "TSS", "RT0", "RTA"]:
            with self.subTest(selector=selector):
                result = provider_units.is_return_service(selector)

                print("DEBUG return service detection:", selector, result)

                self.assertTrue(result)

        for selector in ["tracked_24", "TPN24", "FE0"]:
            with self.subTest(selector=selector):
                result = provider_units.is_return_service(selector)

                print("DEBUG non-return service detection:", selector, result)

                self.assertFalse(result)

    def test_package_format_resolution(self):
        scenarios = [
            ("explicit_small_parcel", ShipmentPayload, "smallParcel"),
            ("packaging_type_fallback", ShipmentPayloadEnvelopePackaging, "letter"),
            ("inferred_letter", ShipmentPayloadInferredLetter, "letter"),
            ("inferred_large_letter", ShipmentPayloadInferredLargeLetter, "largeLetter"),
            ("inferred_parcel", ShipmentPayloadInferredParcel, "smallParcel"),
        ]

        for name, payload, expected_format in scenarios:
            with self.subTest(name=name):
                shipment = models.ShipmentRequest(**payload)
                request = gateway.mapper.create_shipment_request(shipment)
                serialized = lib.to_dict(request.serialize())

                print(f"DEBUG package format request [{name}]:", serialized)

                self.assertEqual(
                    serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
                    expected_format,
                )


if __name__ == "__main__":
    unittest.main()