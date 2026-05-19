"""Royal Mail Click and Drop carrier settings tests."""

import copy
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import fixture


class TestRoyalMailClickandDropSettings(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _gateway(self, config=None):
        return karrio.gateway["royalmail"].create(
            dict(
                id="123456789",
                test_mode=False,
                carrier_id="royalmail",
                click_and_drop_api_key="TEST_API_KEY",
                config=config or {},
            )
        )

    def test_default_settings_values(self):
        """Initialize default connection settings and auth values correctly."""
        gateway = self._gateway()

        self.assertEqual(
            gateway.settings.server_url,
            fixture.ExpectedDefaultConnectionConfig["click_and_drop_api_base_url"],
        )
        self.assertEqual(
            gateway.settings.tracking_server_url,
            fixture.ExpectedDefaultConnectionConfig["tracking_api_base_url"],
        )
        self.assertEqual(gateway.settings.authorization, "Bearer TEST_API_KEY")
        self.assertEqual(
            gateway.settings.label_type,
            fixture.ExpectedDefaultConnectionConfig["label_type"],
        )
        self.assertIsInstance(gateway.settings.metadata, dict)
        self.assertIsInstance(gateway.settings.config, dict)

    def test_server_url_uses_connection_config_base_url(self):
        """Normalize configured Click & Drop API base URL overrides consistently."""
        gateway = self._gateway(
            config={"click_and_drop_api_base_url": "https://example.test/custom/api/"}
        )

        self.assertEqual(
            gateway.settings.connection_config.click_and_drop_api_base_url.state,
            "https://example.test/custom/api/",
        )
        self.assertEqual(
            gateway.settings.server_url,
            "https://example.test/custom/api",
        )

    def test_server_url_accepts_legacy_base_url_key(self):
        """Remain backward compatible with older `base_url` config payloads."""
        gateway = self._gateway(
            config={"base_url": "https://legacy.example.test/custom/api/"}
        )

        self.assertEqual(
            gateway.settings.server_url,
            "https://legacy.example.test/custom/api",
        )

    def test_connection_config_label_flags_flow_into_shipment_request(self):
        """Apply connector-level label defaults when shipment options do not override them."""
        gateway = self._gateway(
            config={
                "include_label_in_response": False,
                "include_return_label_in_response": True,
            }
        )

        shipment = models.ShipmentRequest(
            **copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        )
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertFalse(serialized["items"][0]["label"]["includeLabelInResponse"])
        self.assertTrue(serialized["items"][0]["label"]["includeReturnsLabel"])

    def test_request_label_flags_override_connection_config(self):
        """Let shipment-level label options override connection-level defaults."""
        gateway = self._gateway(
            config={
                "include_label_in_response": False,
                "include_return_label_in_response": False,
            }
        )

        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["reference"] = "ORDER-1001-RET"
        payload["options"]["order_reference"] = "ORDER-1001-RET"
        payload["options"]["include_returns_label"] = True
        payload["options"]["include_label_in_response"] = True

        shipment = models.ShipmentRequest(**payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertTrue(serialized["items"][0]["label"]["includeLabelInResponse"])
        self.assertTrue(serialized["items"][0]["label"]["includeReturnsLabel"])

    def test_shipping_carrier_name_uses_connection_config_state(self):
        """Expose configured carrier_name through settings."""
        gateway = self._gateway(config={"carrier_name": "Royal Mail OBA"})

        self.assertEqual(
            gateway.settings.connection_config.carrier_name.state,
            "Royal Mail OBA",
        )
        self.assertEqual(
            gateway.settings.shipping_carrier_name,
            "Royal Mail OBA",
        )

    def test_request_option_carrier_name_overrides_connection_config(self):
        """Let shipment carrier_name override connector default while manifests still use connector default."""
        gateway = self._gateway(config={"carrier_name": "Royal Mail Default"})

        shipment_payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        shipment_payload["options"]["carrier_name"] = "Royal Mail OBA"

        shipment = models.ShipmentRequest(**shipment_payload)
        request = gateway.mapper.create_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["postageDetails"]["carrierName"],
            "Royal Mail OBA",
        )

        manifest_payload = copy.deepcopy(fixture.ManifestPayload)
        manifest_payload["options"].pop("carrier_name", None)

        manifest = models.ManifestRequest(**manifest_payload)
        manifest_request = gateway.mapper.create_manifest_request(manifest)
        manifest_serialized = lib.to_dict(manifest_request.serialize())

        self.assertEqual(
            manifest_serialized,
            {"carrierName": "Royal Mail Default"},
        )

    def test_connection_config_initializer_normalizes_string_booleans(self):
        """Normalize string boolean config values through connection_config_initializer."""
        gateway = self._gateway(
            config={
                "include_label_in_response": "false",
                "include_return_label_in_response": "true",
            }
        )

        self.assertFalse(
            gateway.settings.connection_config.include_label_in_response.state
        )
        self.assertTrue(
            gateway.settings.connection_config.include_return_label_in_response.state
        )

    def test_shipping_services_respects_connection_config_service_whitelist(self):
        """Filter available services by config.shipping_services."""
        gateway = self._gateway(
            config={
                "shipping_services": [fixture.SHIPMENT_SERVICE_CODE],
            }
        )

        services = gateway.settings.shipping_services

        self.assertEqual([service.service_code for service in services], [fixture.SHIPMENT_SERVICE_CODE])

    def test_shipping_services_accepts_raw_carrier_service_code_in_config(self):
        """Allow config.shipping_services to use raw Royal Mail carrier serviceCode values."""
        gateway = self._gateway(
            config={
                "shipping_services": [fixture.SHIPMENT_CARRIER_SERVICE_CODE],
            }
        )

        services = gateway.settings.shipping_services

        self.assertTrue(any(service.service_code == fixture.SHIPMENT_SERVICE_CODE for service in services))
        self.assertTrue(
            gateway.settings.is_shipping_service_allowed(
                fixture.SHIPMENT_CARRIER_SERVICE_CODE
            )
        )

    def test_shipping_option_names_respect_connection_config_option_whitelist(self):
        """Filter available shipping option names by config.shipping_options."""
        gateway = self._gateway(
            config={
                "shipping_options": [
                    "shipmentNote",
                    "shippingCharges",
                    "emailNotificationTo",
                ],
            }
        )

        self.assertEqual(
            gateway.settings.shipping_option_names,
            ["shipment_note", "shipping_charges", "email_notification_to"],
        )
        self.assertTrue(gateway.settings.is_shipping_option_allowed("shipment_note"))
        self.assertTrue(gateway.settings.is_shipping_option_allowed("shipmentNote"))
        self.assertFalse(gateway.settings.is_shipping_option_allowed("invoice_number"))

    def test_shipping_option_names_default_to_canonical_names_only(self):
        """Default option list should not expose alias names."""
        gateway = self._gateway()
        names = gateway.settings.shipping_option_names

        self.assertIn("receive_email_notification", names)
        self.assertIn("receive_sms_notification", names)
        self.assertIn("request_signature_upon_delivery", names)
        self.assertIn("contains_dangerous_goods", names)

        self.assertNotIn("email_notification", names)
        self.assertNotIn("sms_notification", names)
        self.assertNotIn("signature_confirmation", names)
        self.assertNotIn("dangerous_good", names)

    def test_shipping_option_whitelist_returns_canonical_names_only(self):
        """Configured aliases should normalize to canonical names only."""
        gateway = self._gateway(
            config={
                "shipping_options": [
                    "email_notification",
                    "smsNotification",
                    "signatureConfirmation",
                    "dangerous_good",
                ],
            }
        )

        self.assertEqual(
            gateway.settings.shipping_option_names,
            [
                "receive_email_notification",
                "receive_sms_notification",
                "request_signature_upon_delivery",
                "contains_dangerous_goods",
            ],
        )

    def test_shipping_services_expands_ambiguous_raw_international_service_code_in_config(self):
        """Expand raw international carrier code OTA to all package-specific services."""
        gateway = self._gateway(
            config={
                "shipping_services": ["OTA"],
            }
        )

        service_codes = {
            service.service_code
            for service in gateway.settings.shipping_services
        }

        self.assertIn(
            "royal_mail_international_tracked_large_letter",
            service_codes,
        )
        self.assertIn(
            "royal_mail_international_tracked_small_parcel",
            service_codes,
        )
        self.assertIn(
            "royal_mail_international_tracked_medium_parcel",
            service_codes,
        )

        self.assertTrue(gateway.settings.is_shipping_service_allowed("OTA"))
        self.assertTrue(
            gateway.settings.is_shipping_service_allowed(
                "royal_mail_international_tracked_small_parcel"
            )
        )