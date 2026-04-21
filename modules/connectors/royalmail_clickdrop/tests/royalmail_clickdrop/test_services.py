 
"""Royal Mail Click and Drop carrier services tests."""

import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.plugins.royalmail_clickdrop as plugin
import karrio.providers.royalmail_clickdrop.units as provider_units
from . import fixture



class TestRoyalMailClickandDropServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_services_catalog_loads(self):
        """Verify the services CSV is loaded and exposes the expected core Royal Mail service keys."""
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
        for code in fixture.ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_plugin_metadata_exposes_service_levels(self):
        """Verify plugin metadata publishes the same service catalog used by the connector."""
        metadata = plugin.METADATA
        service_levels = metadata.service_levels or []

        print("DEBUG plugin metadata id:", metadata.id)
        print("DEBUG plugin service level count:", len(service_levels))

        self.assertEqual(metadata.id, "royalmail_clickdrop")
        self.assertGreater(len(service_levels), 0)

        codes = [s.service_code for s in service_levels]
        for code in fixture.ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_resolve_carrier_service(self):
        """Verify service resolution works for CSV keys, enum aliases, direct carrier codes, and unknown values."""
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
        """Verify return services are correctly distinguished from outbound services."""
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
        """Verify package format selection uses explicit values, packaging aliases, and dimension/weight inference correctly."""
        scenarios = [
            ("explicit_small_parcel", fixture.ShipmentPayload, "smallParcel"),
            ("packaging_type_fallback", fixture.ShipmentPayloadEnvelopePackaging, "letter"),
            ("inferred_letter", fixture.ShipmentPayloadInferredLetter, "letter"),
            ("inferred_large_letter", fixture.ShipmentPayloadInferredLargeLetter, "largeLetter"),
            ("inferred_parcel", fixture.ShipmentPayloadInferredParcel, "smallParcel"),
        ]

        for name, payload, expected_format in scenarios:
            with self.subTest(name=name):
                shipment = models.ShipmentRequest(**payload)
                request = fixture.gateway.mapper.create_shipment_request(shipment)
                serialized = lib.to_dict(request.serialize())

                print(f"DEBUG package format request [{name}]:", serialized)

                self.assertEqual(
                    serialized["items"][0]["packages"][0]["packageFormatIdentifier"],
                    expected_format,
                )
    def test_shipping_options_initializer_normalizes_legacy_keys(self):
        """Verify legacy shipping option names are normalized into the canonical option keys expected by the mapper."""
        options = provider_units.shipping_options_initializer(
            {
                "receiveEmailNotification": True,
                "AIRNumber": "UKIMS123",
            }
        )

        self.assertTrue(options.receive_email_notification.state)
        self.assertEqual(options.air_number.state, "UKIMS123")

if __name__ == "__main__":
    unittest.main()