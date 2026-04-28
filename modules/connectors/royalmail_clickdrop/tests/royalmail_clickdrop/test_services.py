 
"""Royal Mail Click and Drop carrier services tests."""

import copy
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.plugins.royalmail_clickdrop as plugin
import karrio.providers.royalmail_clickdrop.units as provider_units

from . import fixture

import logging
import karrio.sdk as karrio

logger = logging.getLogger(__name__)

class TestRoyalMailClickandDropServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _package_format(self, payload):
        request = fixture.gateway.mapper.create_shipment_request(self._shipment(payload))
        serialized = lib.to_dict(request.serialize())
        return serialized["items"][0]["packages"][0]["packageFormatIdentifier"]

    def test_services_catalog_loads(self):
        """Load services from CSV and expose expected core Royal Mail service codes."""
        services = provider_units.DEFAULT_SERVICES or []
        self.assertGreater(len(services), 0)

        codes = [service.service_code for service in services]
        for code in fixture.ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_plugin_metadata_exposes_service_levels(self):
        """Expose the same service catalog through plugin metadata."""
        metadata = plugin.METADATA
        service_levels = metadata.service_levels or []

        self.assertEqual(metadata.id, "royalmail")
        self.assertGreater(len(service_levels), 0)

        codes = [service.service_code for service in service_levels]
        for code in fixture.ExpectedCoreServices:
            self.assertIn(code, codes)

    def test_service_weight_limits_are_normalized(self):
        """Keep Royal Mail service metadata in grams exactly as declared in services.csv."""
        services = {
            service.service_code: service
            for service in provider_units.DEFAULT_SERVICES or []
        }

        self.assertEqual(services["TPN24"].weight_unit, "G")
        self.assertEqual(services["TPN24"].max_weight, 2000.0)

        self.assertEqual(services["FE0"].weight_unit, "G")
        self.assertEqual(services["FE0"].max_weight, 30000.0)

    def test_service_features_are_loaded(self):
        """Expose services.csv feature tokens as Karrio ServiceLevelFeatures."""
        services = {
            service.service_code: service
            for service in provider_units.DEFAULT_SERVICES or []
        }

        tracked_24 = services["TPN24"]
        self.assertTrue(tracked_24.features.tracked)
        self.assertTrue(tracked_24.features.b2c)
        self.assertTrue(tracked_24.features.b2b)
        self.assertEqual(tracked_24.features.shipment_type, "outbound")

        tracked_returns = services["TSS"]
        self.assertTrue(tracked_returns.features.tracked)
        self.assertEqual(tracked_returns.features.shipment_type, "returns")

    def test_resolve_carrier_service(self):
        """Resolve service aliases and direct service codes, but not raw register codes."""
        scenarios = [
            ("tracked_24", "TPN24"),
            ("TPN24", "TPN24"),
            ("tracked_returns_48", "TSS"),
            ("TSS", "TSS"),
            ("1", None),
            ("01", None),
            ("not_a_service", None),
        ]

        for selector, expected in scenarios:
            with self.subTest(selector=selector):
                self.assertEqual(
                    provider_units.resolve_carrier_service(selector),
                    expected,
                )

    def test_resolve_service_register_code(self):
        """Resolve serviceRegisterCode from the CSV service catalog."""
        scenarios = [
            ("tracked_24", fixture.ExpectedServiceRegisterCodes["TPN24"]),
            ("TPN24", fixture.ExpectedServiceRegisterCodes["TPN24"]),
            ("tracked_returns_48", fixture.ExpectedServiceRegisterCodes["TSS"]),
            ("TSS", fixture.ExpectedServiceRegisterCodes["TSS"]),
            ("not_a_service", None),
        ]

        for selector, expected in scenarios:
            with self.subTest(selector=selector):
                self.assertEqual(
                    provider_units.resolve_service_register_code(selector),
                    expected,
                )

    def test_return_service_detection(self):
        """Identify return services correctly."""
        for selector in ["tracked_returns_48", "TSS", "RT0", "RTA"]:
            with self.subTest(selector=selector):
                self.assertTrue(provider_units.is_return_service(selector))

        for selector in ["tracked_24", "TPN24", "FE0"]:
            with self.subTest(selector=selector):
                self.assertFalse(provider_units.is_return_service(selector))

    def test_package_format_resolution(self):
        """Use explicit values, packaging aliases, raw dimension inference, and custom pass-through correctly."""
        custom_payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        custom_payload["options"]["package_format_identifier"] = "myCustomFormat"

        scenarios = [
            ("explicit_small_parcel", fixture.ShipmentPayload, "smallParcel"),
            ("packaging_type_fallback", fixture.ShipmentPayloadEnvelopePackaging, "letter"),
            ("inferred_letter", fixture.ShipmentPayloadInferredLetter, "letter"),
            ("inferred_large_letter", fixture.ShipmentPayloadInferredLargeLetter, "largeLetter"),
            ("inferred_parcel", fixture.ShipmentPayloadInferredParcel, "smallParcel"),
            ("custom_passthrough", custom_payload, "myCustomFormat"),
        ]

        for name, payload, expected in scenarios:
            with self.subTest(name=name):
                self.assertEqual(self._package_format(payload), expected)

    def test_shipping_options_initializer_normalizes_legacy_keys(self):
        """Normalize legacy option names into canonical Karrio option keys."""
        options = provider_units.shipping_options_initializer(
            {
                "receiveEmailNotification": True,
                "AIRNumber": "UKIMS123",
            }
        )

        self.assertTrue(options.receive_email_notification.state)
        self.assertEqual(options.air_number.state, "UKIMS123")


