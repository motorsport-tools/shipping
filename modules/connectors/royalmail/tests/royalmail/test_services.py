"""Royal Mail Click and Drop carrier services tests."""

import copy
import csv
import json
import pathlib
import re
import unittest
from collections import Counter, defaultdict

import karrio.core.models as models
import karrio.lib as lib
import karrio.plugins.royalmail as plugin
import karrio.providers.royalmail.units as provider_units
import karrio.references as references

from . import fixture


class TestRoyalMailClickandDropServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    # -------------------------------------------------------------------------
    # CSV helpers
    # -------------------------------------------------------------------------

    def _services_csv_path(self):
        return pathlib.Path(
            getattr(
                provider_units,
                "SERVICES_CSV",
                pathlib.Path(provider_units.__file__).with_name("services.csv"),
            )
        )

    def _csv_rows(self):
        with open(self._services_csv_path(), newline="", encoding="utf-8") as csvfile:
            return [
                {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in row.items()
                }
                for row in csv.DictReader(csvfile)
                if row.get("service_code")
            ]

    def _csv_rows_by_service_code(self):
        rows_by_code = {}

        for row in self._csv_rows():
            rows_by_code.setdefault(row["service_code"], row)

        return rows_by_code

    def _services_by_code(self):
        return {
            service.service_code: service
            for service in provider_units.DEFAULT_SERVICES or []
        }

    def _plugin_service_levels_by_code(self):
        service_levels = plugin.METADATA.service_levels or {}

        if isinstance(service_levels, dict):
            return service_levels

        return {
            self._value(service, "service_code"): service
            for service in service_levels
            if self._value(service, "service_code")
        }

    def _value(self, item, key, default=None):
        if isinstance(item, dict):
            return item.get(key, default)

        return getattr(item, key, default)

    def _feature_value(self, features, key, default=None):
        if isinstance(features, dict):
            return features.get(key, default)

        return getattr(features, key, default)

    def _metadata_value(self, metadata, key, default=None):
        if isinstance(metadata, dict):
            return metadata.get(key, default)

        return getattr(metadata, key, default)

    def _row_value(self, row, key, default=None):
        value = row.get(key, default)

        if value in [None, ""]:
            return default

        return value

    def _to_float(self, value, default=None):
        if value in [None, ""]:
            return default

        return float(value)

    def _to_bool(self, value, default=None):
        if value in [None, ""]:
            return default

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in ["true", "1", "yes", "y"]

    def _feature_tokens(self, row):
        features = self._row_value(row, "features", "") or ""

        return [
            token.strip().lower()
            for token in re.split(r"[,;|:]+", features)
            if token.strip()
        ]

    def _friendly_service_name(self, service_name):
        if service_name in [None, ""]:
            return None

        text = re.sub(r"\s*\([^)]*\)\s*", " ", service_name)
        text = re.sub(r"\s+", " ", text).strip()

        return text or None

    def _is_return_row(self, row):
        tokens = self._feature_tokens(row)

        return (
            self._to_bool(row.get("return_service"), default=False)
            or any(token in ["return", "returns", "return_service"] for token in tokens)
            or "return" in str(row.get("service_name", "")).lower()
            or "returns" in str(row.get("service_name", "")).lower()
        )

    def _normalize_weight_unit(self, unit):
        unit = str(unit or "KG").strip().upper()

        if unit in ["KG", "LB"]:
            return unit

        return "KG"

    def _normalize_dimension_unit(self, unit):
        unit = str(unit or "CM").strip().upper()

        if unit in ["CM", "IN"]:
            return unit

        return "CM"

    def _convert_weight(self, value, source_unit, target_unit=None):
        numeric = self._to_float(value)

        if numeric is None:
            return None

        source_unit = str(source_unit or "KG").strip().upper()
        target_unit = str(target_unit or self._normalize_weight_unit(source_unit)).upper()

        if source_unit in ["G", "GRAM", "GRAMS"]:
            kg = numeric / 1000
        elif source_unit in ["KG", "KGS", "KILOGRAM", "KILOGRAMS"]:
            kg = numeric
        elif source_unit in ["LB", "LBS", "POUND", "POUNDS"]:
            kg = numeric / 2.20462262185
        elif source_unit in ["OZ", "OUNCE", "OUNCES"]:
            kg = numeric / 35.27396195
        else:
            kg = numeric

        if target_unit == "LB":
            return kg * 2.20462262185

        return kg

    def _convert_dimension(self, value, source_unit, target_unit=None):
        numeric = self._to_float(value)

        if numeric is None:
            return None

        source_unit = str(source_unit or "CM").strip().upper()
        target_unit = str(
            target_unit or self._normalize_dimension_unit(source_unit)
        ).upper()

        if source_unit in [
            "MM",
            "MMS",
            "MILLIMETRE",
            "MILLIMETRES",
            "MILLIMETER",
            "MILLIMETERS",
        ]:
            cm = numeric / 10
        elif source_unit in [
            "CM",
            "CMS",
            "CENTIMETRE",
            "CENTIMETRES",
            "CENTIMETER",
            "CENTIMETERS",
        ]:
            cm = numeric
        elif source_unit in ["M", "METRE", "METRES", "METER", "METERS"]:
            cm = numeric * 100
        elif source_unit in ["IN", "INS", "INCH", "INCHES"]:
            cm = numeric * 2.54
        else:
            cm = numeric

        if target_unit == "IN":
            return cm / 2.54

        return cm

    def _package_format_kind_from_csv_row(self, row):
        """Infer the Royal Mail register package kind from CSV limits."""
        raw_weight_unit = row.get("weight_unit") or "G"
        raw_dimension_unit = row.get("dimension_unit") or "MM"

        weight_kg = self._convert_weight(
            row.get("max_weight"),
            raw_weight_unit,
            "KG",
        )
        weight_g = None if weight_kg is None else weight_kg * 1000

        dimensions_cm = [
            self._convert_dimension(row.get("max_length"), raw_dimension_unit, "CM"),
            self._convert_dimension(row.get("max_width"), raw_dimension_unit, "CM"),
            self._convert_dimension(row.get("max_height"), raw_dimension_unit, "CM"),
        ]

        if weight_g is None or any(value is None for value in dimensions_cm):
            return None

        dimensions_mm = [value * 10 for value in dimensions_cm]
        max_dim = max(dimensions_mm)
        min_dim = min(dimensions_mm)
        mid_dim = sorted(dimensions_mm)[1]

        if weight_g <= 100 and max_dim <= 240 and mid_dim <= 165 and min_dim <= 5:
            return "letter"

        if weight_g <= 750 and max_dim <= 353 and mid_dim <= 250 and min_dim <= 25:
            return "large_letter"

        return "parcel"

    def _package_format_identifier_for_kind(self, kind):
        return {
            "letter": "letter",
            "large_letter": "largeLetter",
            "parcel": "smallParcel",
        }.get(kind)

    def _rows_with_unique_selectors(self):
        rows = self._csv_rows()

        carrier_counts = Counter(
            row.get("carrier_service_code")
            for row in rows
            if row.get("carrier_service_code")
        )
        name_counts = Counter(
            row.get("service_name")
            for row in rows
            if row.get("service_name")
        )
        friendly_counts = Counter(
            self._friendly_service_name(row.get("service_name"))
            for row in rows
            if self._friendly_service_name(row.get("service_name"))
        )

        return [
            row
            for row in rows
            if row.get("service_code")
            and row.get("carrier_service_code")
            and row.get("service_name")
            and carrier_counts[row["carrier_service_code"]] == 1
            and name_counts[row["service_name"]] == 1
            and friendly_counts[self._friendly_service_name(row["service_name"])] == 1
        ]

    def _first_unique_selector_row(self, predicate=lambda row: True):
        for row in self._rows_with_unique_selectors():
            if predicate(row):
                return row

        raise AssertionError("No CSV service row matched the requested predicate")

    # -------------------------------------------------------------------------
    # Request helpers
    # -------------------------------------------------------------------------

    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _package_format(self, payload):
        request = fixture.gateway.mapper.create_shipment_request(self._shipment(payload))
        serialized = lib.to_dict(request.serialize())

        return serialized["items"][0]["packages"][0]["packageFormatIdentifier"]

    # -------------------------------------------------------------------------
    # Catalog tests
    # -------------------------------------------------------------------------

    def test_services_catalog_loads_from_csv(self):
        """Load every service declared in services.csv."""
        csv_rows_by_code = self._csv_rows_by_service_code()
        services_by_code = self._services_by_code()

        self.assertGreater(len(csv_rows_by_code), 0)
        self.assertEqual(set(services_by_code), set(csv_rows_by_code))

    def test_services_catalog_uses_csv_service_names(self):
        """Use service names from services.csv exactly; do not assert invented names."""
        csv_rows_by_code = self._csv_rows_by_service_code()
        services_by_code = self._services_by_code()

        for service_code, row in csv_rows_by_code.items():
            with self.subTest(service_code=service_code):
                service = services_by_code[service_code]

                self.assertEqual(service.service_code, row["service_code"])
                self.assertEqual(service.service_name, row["service_name"])
                self.assertEqual(
                    service.carrier_service_code,
                    row.get("carrier_service_code") or row["service_code"],
                )

    def test_plugin_metadata_exposes_csv_service_levels(self):
        """
        Expose the active CSV-backed service catalog through plugin metadata.

        Karrio uses plugin.METADATA.service_levels to build carrier references
        and default rate-table rows. Therefore inactive CSV rows must not be
        exposed here, otherwise they appear in the Karrio rate table UI.
        """
        all_csv_rows_by_code = self._csv_rows_by_service_code()
        active_csv_rows_by_code = {
            service_code: row
            for service_code, row in all_csv_rows_by_code.items()
            if provider_units.service_is_active(row)
        }
        inactive_csv_codes = {
            service_code
            for service_code, row in all_csv_rows_by_code.items()
            if not provider_units.service_is_active(row)
        }

        plugin_services_by_code = self._plugin_service_levels_by_code()

        self.assertEqual(plugin.METADATA.id, "royalmail")
        self.assertEqual(set(plugin_services_by_code), set(active_csv_rows_by_code))

        self.assertFalse(
            set(plugin_services_by_code) & inactive_csv_codes,
            msg=(
                "Inactive CSV services leaked into plugin metadata: "
                f"{set(plugin_services_by_code) & inactive_csv_codes}"
            ),
        )

        for service_code, row in active_csv_rows_by_code.items():
            with self.subTest(service_code=service_code):
                service = plugin_services_by_code[service_code]

                self.assertEqual(self._value(service, "service_code"), row["service_code"])
                self.assertEqual(self._value(service, "service_name"), row["service_name"])
                self.assertEqual(
                    self._value(service, "carrier_service_code"),
                    row.get("carrier_service_code") or row["service_code"],
                )

    def test_plugin_metadata_service_levels_are_json_serializable(self):
        """Keep plugin metadata service levels JSON-safe for /v1/references."""
        service_levels = plugin.METADATA.service_levels or []

        json.dumps(service_levels)

    # -------------------------------------------------------------------------
    # Unit and metadata tests
    # -------------------------------------------------------------------------

    def test_service_weight_limits_are_normalized_for_karrio_rating(self):
        """Normalize carrier weight units from services.csv into Karrio rating units."""
        services_by_code = self._services_by_code()

        for row in self._csv_rows():
            if row.get("max_weight") in [None, ""]:
                continue

            with self.subTest(service_code=row["service_code"]):
                service = services_by_code[row["service_code"]]

                raw_unit = row.get("weight_unit") or "KG"
                expected_unit = self._normalize_weight_unit(raw_unit)
                expected_max_weight = self._convert_weight(
                    row["max_weight"],
                    raw_unit,
                    expected_unit,
                )

                self.assertEqual(service.weight_unit, expected_unit)
                self.assertAlmostEqual(service.max_weight, expected_max_weight)

                if str(raw_unit).strip().upper() != expected_unit:
                    metadata = service.metadata or {}

                    self.assertEqual(
                        metadata.get("carrier_weight_unit"),
                        raw_unit,
                    )
                    self.assertEqual(
                        metadata.get("carrier_max_weight"),
                        self._to_float(row["max_weight"]),
                    )

    def test_service_dimension_limits_are_normalized_for_karrio_rating(self):
        """Normalize carrier dimension units from services.csv into Karrio rating units."""
        services_by_code = self._services_by_code()

        invalid_dimension_units = sorted(
            {
                service.dimension_unit
                for service in services_by_code.values()
                if service.dimension_unit not in [None, "CM", "IN"]
            }
        )

        self.assertEqual(invalid_dimension_units, [])

        for row in self._csv_rows():
            dimension_fields = ["max_length", "max_width", "max_height"]

            if all(row.get(field) in [None, ""] for field in dimension_fields):
                continue

            with self.subTest(service_code=row["service_code"]):
                service = services_by_code[row["service_code"]]

                raw_unit = row.get("dimension_unit") or "CM"
                expected_unit = self._normalize_dimension_unit(raw_unit)

                self.assertEqual(service.dimension_unit, expected_unit)

                for csv_field, service_field in [
                    ("max_length", "max_length"),
                    ("max_width", "max_width"),
                    ("max_height", "max_height"),
                ]:
                    if row.get(csv_field) in [None, ""]:
                        continue

                    expected_value = self._convert_dimension(
                        row[csv_field],
                        raw_unit,
                        expected_unit,
                    )

                    self.assertAlmostEqual(
                        getattr(service, service_field),
                        expected_value,
                    )

                if str(raw_unit).strip().upper() != expected_unit:
                    metadata = service.metadata or {}

                    self.assertEqual(
                        metadata.get("carrier_dimension_unit"),
                        raw_unit,
                    )

                    for csv_field, metadata_field in [
                        ("max_length", "carrier_max_length"),
                        ("max_width", "carrier_max_width"),
                        ("max_height", "carrier_max_height"),
                    ]:
                        if row.get(csv_field) in [None, ""]:
                            continue

                        self.assertEqual(
                            metadata.get(metadata_field),
                            self._to_float(row[csv_field]),
                        )

    # -------------------------------------------------------------------------
    # Feature tests
    # -------------------------------------------------------------------------

    def test_service_features_are_loaded_from_csv_tokens(self):
        """Expose services.csv feature tokens as Karrio ServiceLevelFeatures."""
        services_by_code = self._services_by_code()

        for row in self._csv_rows():
            tokens = self._feature_tokens(row)

            if not tokens:
                continue

            with self.subTest(service_code=row["service_code"]):
                service = services_by_code[row["service_code"]]
                features = service.features

                if "tracked" in tokens or "tracking" in tokens:
                    self.assertTrue(features.tracked)

                if "signature" in tokens or "signed" in tokens:
                    self.assertTrue(features.signature)

                if "b2c" in tokens:
                    self.assertTrue(features.b2c)

                if "b2b" in tokens:
                    self.assertTrue(features.b2b)

                if "insurance" in tokens:
                    self.assertTrue(features.insurance)

                if self._is_return_row(row):
                    self.assertEqual(features.shipment_type, "returns")
                    self.assertTrue((service.metadata or {}).get("return_service"))
                else:
                    self.assertEqual(features.shipment_type, "outbound")

    # -------------------------------------------------------------------------
    # Resolver tests
    # -------------------------------------------------------------------------

    def test_resolve_service_code_uses_csv_selectors(self):
        """Resolve CSV service codes, carrier codes, full names, and friendly names."""
        normal_row = self._first_unique_selector_row(
            lambda row: not self._is_return_row(row)
        )
        return_row = self._first_unique_selector_row(self._is_return_row)

        for row in [normal_row, return_row]:
            selectors = [
                row["service_code"],
                row["carrier_service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                with self.subTest(selector=selector, expected=row["service_code"]):
                    self.assertEqual(
                        provider_units.resolve_service_code(selector),
                        row["service_code"],
                    )

        self.assertIsNone(provider_units.resolve_service_code("not_a_service"))

    def test_resolve_carrier_service_uses_csv_selectors(self):
        """Resolve CSV selectors to the Royal Mail API serviceCode."""
        normal_row = self._first_unique_selector_row(
            lambda row: not self._is_return_row(row)
        )
        return_row = self._first_unique_selector_row(self._is_return_row)

        for row in [normal_row, return_row]:
            selectors = [
                row["service_code"],
                row["carrier_service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                with self.subTest(selector=selector, expected=row["carrier_service_code"]):
                    self.assertEqual(
                        provider_units.resolve_carrier_service(selector),
                        row["carrier_service_code"],
                    )

        self.assertIsNone(provider_units.resolve_carrier_service("not_a_service"))

    def test_resolve_service_register_code_uses_csv_selectors(self):
        """Resolve serviceRegisterCode from CSV-backed selectors."""
        normal_row = self._first_unique_selector_row(
            lambda row: not self._is_return_row(row) and row.get("service_register_code")
        )
        return_row = self._first_unique_selector_row(
            lambda row: self._is_return_row(row) and row.get("service_register_code")
        )

        for row in [normal_row, return_row]:
            selectors = [
                row["service_code"],
                row["carrier_service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                with self.subTest(selector=selector, expected=row["service_register_code"]):
                    self.assertEqual(
                        provider_units.resolve_service_register_code(selector),
                        row["service_register_code"],
                    )

        self.assertIsNone(
            provider_units.resolve_service_register_code("not_a_service")
        )

    def test_resolve_service_register_code_handles_duplicate_carrier_codes_by_package_format(self):
        """Resolve serviceRegisterCode for CSV services sharing the same carrier serviceCode."""
        rows_by_carrier_code = defaultdict(list)

        for row in self._csv_rows():
            if row.get("carrier_service_code") and row.get("service_register_code"):
                rows_by_carrier_code[row["carrier_service_code"]].append(row)

        duplicate_groups = [
            rows
            for rows in rows_by_carrier_code.values()
            if len({row["service_register_code"] for row in rows}) > 1
        ]

        self.assertGreater(
            len(duplicate_groups),
            0,
            "services.csv should contain at least one duplicate carrier serviceCode group",
        )

        tested = 0

        for rows in duplicate_groups:
            for row in rows:
                kind = self._package_format_kind_from_csv_row(row)
                package_format = self._package_format_identifier_for_kind(kind)

                if package_format is None:
                    continue

                with self.subTest(
                    carrier_service_code=row["carrier_service_code"],
                    package_format=package_format,
                    expected=row["service_register_code"],
                ):
                    self.assertEqual(
                        provider_units.resolve_service_register_code(
                            row["carrier_service_code"],
                            package_format=package_format,
                        ),
                        row["service_register_code"],
                    )

                tested += 1

        self.assertGreater(
            tested,
            0,
            "No duplicate carrier serviceCode rows had inferable package formats",
        )

    def test_return_service_detection_uses_csv_features(self):
        """
        Identify active return services based on CSV feature metadata.

        Inactive CSV services are intentionally excluded from runtime service
        resolution. Therefore inactive return services such as insured return
        variants should not be expected to resolve through
        provider_units.is_return_service().
        """
        rows = self._csv_rows()

        active_return_rows = [
            row
            for row in rows
            if provider_units.service_is_active(row) and self._is_return_row(row)
        ]
        active_outbound_rows = [
            row
            for row in rows
            if provider_units.service_is_active(row) and not self._is_return_row(row)
        ]
        inactive_return_rows = [
            row
            for row in rows
            if not provider_units.service_is_active(row) and self._is_return_row(row)
        ]

        self.assertGreater(len(active_return_rows), 0)
        self.assertGreater(len(active_outbound_rows), 0)
        self.assertGreater(len(inactive_return_rows), 0)

        for row in active_return_rows[:5]:
            selectors = [
                row["service_code"],
                row["carrier_service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                if selector in [None, ""]:
                    continue

                with self.subTest(selector=selector):
                    self.assertTrue(provider_units.is_return_service(selector))

        for row in active_outbound_rows[:5]:
            selectors = [
                row["service_code"],
                row["carrier_service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                if selector in [None, ""]:
                    continue

                with self.subTest(selector=selector):
                    self.assertFalse(provider_units.is_return_service(selector))

        for row in inactive_return_rows[:5]:
            selectors = [
                row["service_code"],
                row["service_name"],
                self._friendly_service_name(row["service_name"]),
            ]

            for selector in selectors:
                if selector in [None, ""]:
                    continue

                with self.subTest(selector=selector):
                    self.assertFalse(
                        provider_units.is_return_service(selector),
                        msg=(
                            "Inactive return services should not resolve as "
                            f"runtime return services: {selector}"
                        ),
                    )

    # -------------------------------------------------------------------------
    # Non-service-catalog behaviour tests
    # -------------------------------------------------------------------------

    def test_package_format_resolution(self):
        """Use explicit values, packaging aliases, raw dimension inference, and custom pass-through correctly."""
        explicit_payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        explicit_payload["options"]["package_format_identifier"] = "small_parcel"

        custom_payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        custom_payload["options"]["package_format_identifier"] = "myCustomFormat"

        scenarios = [
            # This helper reads the final Click & Drop API payload.
            # For domestic Royal Mail OBA parcel services such as TPN24,
            # parcel-like internal package bands serialize as `parcel`.
            ("explicit_small_parcel", explicit_payload, "parcel"),
            ("packaging_type_fallback", fixture.ShipmentPayloadEnvelopePackaging, "letter"),
            ("inferred_letter", fixture.ShipmentPayloadInferredLetter, "letter"),
            ("inferred_large_letter", fixture.ShipmentPayloadInferredLargeLetter, "largeLetter"),
            ("inferred_parcel", fixture.ShipmentPayloadInferredParcel, "parcel"),
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

    def test_legacy_royalmail_mapper_alias_exposes_capabilities(self):
        """Expose capabilities through legacy `karrio.mappers.royalmail` lookups."""
        capabilities = references.get_carrier_capabilities("royalmail")

        for capability in ["rating", "shipping", "tracking", "manifest"]:
            self.assertIn(capability, capabilities)

    def test_shipping_options_initializer_normalizes_extended_order_option_aliases(self):
        """Normalize additional standard and Royal Mail order option aliases."""
        options = provider_units.shipping_options_initializer(
            {
                "shipmentNote": "Handle with care",
                "specialInstructions": "Leave at loading bay",
                "shippingCharges": 4.75,
                "invoiceNumber": "INV-1001",
                "invoiceDate": "2024-02-01T10:00:00Z",
                "emailNotificationTo": "recipient",
            }
        )

        self.assertEqual(options.shipment_note.state, "Handle with care")
        self.assertEqual(
            options.special_instructions.state,
            "Leave at loading bay",
        )
        self.assertEqual(options.shipping_charges.state, 4.75)
        self.assertEqual(options.invoice_number.state, "INV-1001")
        self.assertEqual(
            options.invoice_date.state,
            "2024-02-01T10:00:00Z",
        )
        self.assertEqual(options.email_notification_to.state, "recipient")

    def test_plugin_references_expose_runtime_order_options(self):
        """Expose runtime-supported order options in Royal Mail carrier metadata."""
        details = references.get_carrier_details("royalmail")

        self.assertEqual(details.get("id"), "royalmail")

        shipping_options = details.get("shipping_options") or {}
        self.assertTrue(shipping_options)

        for option_name in [
            "shipping_charges",
            "shipment_note",
            "shipper_instructions",
            "recipient_instructions",
            "special_instructions",
            "invoice_number",
            "invoice_date",
            "email_notification_to",
        ]:
            with self.subTest(option_name=option_name):
                self.assertIn(option_name, shipping_options)

    def test_canonical_shipping_option_names_exclude_aliases(self):
        """Expose only canonical option names for UI/reference surfaces."""
        names = provider_units.canonical_shipping_option_names()

        self.assertIn("receive_email_notification", names)
        self.assertIn("receive_sms_notification", names)
        self.assertIn("request_signature_upon_delivery", names)
        self.assertIn("contains_dangerous_goods", names)

        self.assertNotIn("email_notification", names)
        self.assertNotIn("sms_notification", names)
        self.assertNotIn("signature_confirmation", names)
        self.assertNotIn("dangerous_good", names)

    def test_shipping_option_name_initializer_maps_aliases_to_canonical_names(self):
        """Accept aliases on input but normalize them to canonical names."""
        names = provider_units.shipping_option_names_initializer(
            [
                "email_notification",
                "smsNotification",
                "signatureConfirmation",
                "dangerous_good",
            ]
        )

        self.assertEqual(
            names,
            [
                "receive_email_notification",
                "receive_sms_notification",
                "request_signature_upon_delivery",
                "contains_dangerous_goods",
            ],
        )

    def _zones_by_label(self, service_code):
        service = self._services_by_code()[service_code]

        return {
            zone.label: zone
            for zone in service.zones or []
        }

    def test_royal_mail_generic_international_services_expand_to_all_royal_mail_zones(self):
        """intl_generic services should cover Europe Zones 1/2/3 and World Zones 1/2/3."""
        zones = self._zones_by_label("royal_mail_international_standard")

        self.assertEqual(
            set(zones),
            {
                "Europe Zone 1",
                "Europe Zone 2",
                "Europe Zone 3",
                "World Zone 1",
                "World Zone 2",
                "World Zone 3",
            },
        )

        self.assertEqual(
            zones["Europe Zone 1"].country_codes,
            ["IE", "FR", "DE", "DK", "MC"],
        )

        self.assertIn("AT", zones["Europe Zone 2"].country_codes)
        self.assertIn("ES", zones["Europe Zone 2"].country_codes)
        self.assertIn("IT", zones["Europe Zone 2"].country_codes)

        self.assertIn("CH", zones["Europe Zone 3"].country_codes)
        self.assertIn("NO", zones["Europe Zone 3"].country_codes)
        self.assertIn("RU", zones["Europe Zone 3"].country_codes)

        # World Zone 1 is intentionally the catch-all fallback.
        self.assertEqual(zones["World Zone 1"].country_codes, [])

        self.assertIn("AU", zones["World Zone 2"].country_codes)
        self.assertIn("NZ", zones["World Zone 2"].country_codes)
        self.assertIn("SG", zones["World Zone 2"].country_codes)

        self.assertEqual(zones["World Zone 3"].country_codes, ["US"])

    def test_royal_mail_europe_only_services_expand_to_europe_zones_only(self):
        """intl_europe services should not cover World Zone destinations."""
        zones = self._zones_by_label("parcel_force_europe")

        self.assertEqual(
            set(zones),
            {
                "Europe Zone 1",
                "Europe Zone 2",
                "Europe Zone 3",
            },
        )

        self.assertIn("FR", zones["Europe Zone 1"].country_codes)
        self.assertIn("NL", zones["Europe Zone 2"].country_codes)
        self.assertIn("CH", zones["Europe Zone 3"].country_codes)

    def test_royal_mail_row_services_expand_to_world_zones_only(self):
        """intl_row services should cover World Zones only, not Europe Zones."""
        zones = self._zones_by_label("parcel_force_globalpriority_row")

        self.assertEqual(
            set(zones),
            {
                "World Zone 1",
                "World Zone 2",
                "World Zone 3",
            },
        )

        # World Zone 1 is the non-Europe/non-WZ2/non-USA fallback.
        self.assertEqual(zones["World Zone 1"].country_codes, [])

        self.assertIn("AU", zones["World Zone 2"].country_codes)
        self.assertIn("SG", zones["World Zone 2"].country_codes)

        self.assertEqual(zones["World Zone 3"].country_codes, ["US"])

    def test_tpn24_blank_package_format_identifier_is_flexible(self):
        """
        TPN24 intentionally has a blank package_format_identifier in services.csv.

        That blank value must not be inferred into a strict smallParcel-only
        package band. TPN24 can be used with letter, largeLetter, or parcel package
        formats in Click & Drop.
        """
        service = provider_units.resolve_service_level("royal_mail_tracked_24")

        self.assertIsNotNone(service)

        metadata = service.metadata or {}

        self.assertIsNone(metadata.get("package_format_identifier"))
        self.assertFalse(metadata.get("package_format_identifier_is_explicit"))
        self.assertEqual(
            metadata.get("inferred_package_format_identifier"),
            "smallParcel",
        )

        for package_format in [
            "letter",
            "largeLetter",
            "smallParcel",
            "mediumParcel",
            "parcel",
        ]:
            with self.subTest(package_format=package_format):
                self.assertTrue(
                    provider_units.service_supports_package_format(
                        "royal_mail_tracked_24",
                        package_format,
                    )
                )

        self.assertEqual(
            provider_units.resolve_service_register_code(
                "royal_mail_tracked_24",
                package_format="letter",
            ),
            "02",
        )
        self.assertEqual(
            provider_units.resolve_service_register_code(
                "royal_mail_tracked_24",
                package_format="largeLetter",
            ),
            "02",
        )
        self.assertEqual(
            provider_units.resolve_service_register_code(
                "royal_mail_tracked_24",
                package_format="mediumParcel",
            ),
            "02",
        )


    def test_blank_package_format_identifier_does_not_make_all_services_flexible(self):
        """
        A blank package_format_identifier is not universally flexible.

        For example, first-class letter rows may have a blank API package format,
        but they must still not accept parcel shipments.
        """
        service = provider_units.resolve_service_level("royal_mail_first_class_letter")

        self.assertIsNotNone(service)

        metadata = service.metadata or {}

        self.assertIsNone(metadata.get("package_format_identifier"))
        self.assertFalse(metadata.get("package_format_identifier_is_explicit"))
        self.assertEqual(metadata.get("package_format_kind"), "letter")

        self.assertTrue(
            provider_units.service_supports_package_format(
                "royal_mail_first_class_letter",
                "letter",
            )
        )
        self.assertFalse(
            provider_units.service_supports_package_format(
                "royal_mail_first_class_letter",
                "smallParcel",
            )
        )
        self.assertIsNone(
            provider_units.resolve_service_register_code(
                "royal_mail_first_class_letter",
                package_format="smallParcel",
            )
        )