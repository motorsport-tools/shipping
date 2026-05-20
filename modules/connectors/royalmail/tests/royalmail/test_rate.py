"""Royal Mail Click and Drop carrier rating tests."""

import unittest
from unittest.mock import patch

import copy

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail.units as provider_units
import karrio.sdk as karrio
from karrio.core.utils.transformer import transform_to_shared_zones_format

import attr
import karrio.mappers.royalmail.proxy as royalmail_proxy
import karrio.mappers.royalmail.mapper as royalmail_mapper
from . import fixture


class TestRoyalMailClickandDropRating(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RateRequest = models.RateRequest(**fixture.RatePayload)

    def _active_services_by_code(self):
        return {
            service.service_code: service
            for service in provider_units.DEFAULT_SERVICES
            if provider_units.service_is_active(service)
        }

    def _first_domestic_service_with_rate(self):
        
        for service in provider_units.DEFAULT_SERVICES:
            if service.active is False:
                continue

            if service.domicile is not True:
                continue

            if not provider_units.service_is_active(service):
                continue            

            for zone in service.zones or []:
                if zone.rate is None:
                    continue

                country_codes = zone.country_codes or []

                if not country_codes or "GB" in country_codes:
                    return service, zone

        raise AssertionError(
            "services.csv does not contain an active domestic GB service with a rate"
        )

    def test_create_rate_request(self):
        """Keep rate request serialization aligned with the universal Karrio rating payload."""
        request = fixture.gateway.mapper.create_rate_request(self.RateRequest)

        print(f"Generated request: {lib.to_dict(request.serialize())}")

        self.assertEqual(
            lib.to_dict(request.serialize()),
            lib.to_dict(self.RateRequest),
        )

    def test_get_rates(self):
        """Royal Mail Click & Drop has no rate endpoint; rates are resolved locally from services.csv."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            response = (
                karrio.Rating.fetch(self.RateRequest)
                .from_(fixture.gateway)
                .parse()
            )

            rates, messages = lib.to_dict(response)

            print(f"Resolved rates: {rates}")
            print(f"Rating messages: {messages}")

            mock.assert_not_called()

        self.assertEqual(messages, [])
        self.assertGreater(len(rates), 0)

        services_by_code = self._active_services_by_code()

        for rate in rates:
            with self.subTest(service=rate["service"]):
                self.assertIn(rate["service"], services_by_code)

                service = services_by_code[rate["service"]]

                self.assertEqual(rate["carrier_id"], "royalmail")
                self.assertEqual(rate["currency"], service.currency)
                self.assertEqual(
                    rate["meta"]["carrier_service_code"],
                    service.carrier_service_code,
                )
                self.assertEqual(
                    rate["meta"]["service_name"],
                    service.service_name,
                )

    def test_parse_rate_response(self):
        """Parse the universal local-rating response shape into Karrio rate details."""
        service, zone = self._first_domestic_service_with_rate()

        rate = models.RateDetails(
            carrier_id="royalmail",
            carrier_name="royalmail",
            service=service.service_code,
            currency=service.currency,
            total_charge=zone.rate,
            transit_days=zone.transit_days or service.transit_days,
            meta={
                "service_name": service.service_name,
                "carrier_service_code": service.carrier_service_code,
                "shipping_charges": zone.rate,
                "shipping_currency": service.currency,
            },
        )

        internal_response = [
            (
                "1",
                (
                    [rate],
                    [],
                ),
            )
        ]

        parsed_response = fixture.gateway.mapper.parse_rate_response(
            lib.Deserializable(internal_response, lambda value: value)
        )

        print(f"Parsed response: {lib.to_dict(parsed_response)}")

        self.assertListEqual(
            lib.to_dict(parsed_response),
            lib.to_dict(([rate], [])),
        )

    def test_parse_error_response(self):
        """Parse local-rating messages from the universal rating response shape."""
        message = models.Message(
            carrier_id="royalmail",
            carrier_name="royalmail",
            code="rate_table_error",
            message="No matching rate table entry found",
            details={"operation": "rating"},
        )

        internal_response = [
            (
                "1",
                (
                    [],
                    [message],
                ),
            )
        ]

        parsed_response = fixture.gateway.mapper.parse_rate_response(
            lib.Deserializable(internal_response, lambda value: value)
        )

        print(f"Error response: {lib.to_dict(parsed_response)}")

        self.assertListEqual(
            lib.to_dict(parsed_response),
            lib.to_dict(([], [message])),
        )


    def test_signature_confirmation_adds_option_surcharge(self):
        service, _ = self._first_domestic_service_with_rate()

        service = attr.evolve(
            service,
            metadata={
                **(service.metadata or {}),
                "signature_surcharge_amount": 2.00,
            },
            surcharges=[],
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={"signature_confirmation": True},
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertEqual(
            surcharges,
            [
                {
                    "id": "royalmail_signature_on_delivery",
                    "name": "Signature on delivery",
                    "amount": 2.0,
                    "surcharge_type": "fixed",
                    "active": True,
                }
            ],
        )

    def test_signature_confirmation_does_not_charge_when_price_is_blank(self):
        service, _ = self._first_domestic_service_with_rate()

        service = attr.evolve(
            service,
            metadata={
                **(service.metadata or {}),
                "signature_surcharge_amount": None,
            },
            surcharges=[],
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={"signature_confirmation": True},
        )

        self.assertEqual(rated_service.surcharges, [])

    def test_uk_vat_is_added_to_net_rate_total(self):
        service, zone = self._first_domestic_service_with_rate()

        service = attr.evolve(
            service,
            metadata={
                **(service.metadata or {}),
                "vat_applicable": True,
                "vat_rate_percentage": 20.0,
                "prices_include_vat": False,
            },
        )

        settings = attr.evolve(
            fixture.gateway.settings,
            services=[service],
        )

        rate = models.RateDetails(
            carrier_id="royalmail",
            carrier_name="royalmail",
            service=service.service_code,
            currency=service.currency,
            total_charge=10.00,
            extra_charges=[
                models.ChargeDetails(
                    name="Base Charge",
                    amount=8.00,
                    currency=service.currency,
                ),
                models.ChargeDetails(
                    name="Signature on delivery",
                    amount=2.00,
                    currency=service.currency,
                ),
            ],
            meta={
                "service_name": service.service_name,
                "carrier_service_code": service.carrier_service_code,
            },
        )

        taxed_rate = royalmail_mapper._apply_royalmail_vat_to_rate(
            rate,
            settings,
        )

        self.assertEqual(taxed_rate.total_charge, 12.00)

        vat_charge = taxed_rate.extra_charges[-1]

        self.assertEqual(vat_charge.id, "royalmail_uk_vat")
        self.assertEqual(vat_charge.name, "UK VAT (20%)")
        self.assertEqual(vat_charge.amount, 2.00)
        self.assertEqual(vat_charge.currency, service.currency)
        self.assertEqual(vat_charge.charge_type, "tax")

        self.assertEqual(taxed_rate.meta["net_charge"], 10.00)
        self.assertEqual(taxed_rate.meta["vat_amount"], 2.00)
        self.assertEqual(taxed_rate.meta["gross_charge"], 12.00)


    def test_uk_vat_is_not_added_when_service_is_not_taxable(self):
        service, _ = self._first_domestic_service_with_rate()

        service = attr.evolve(
            service,
            metadata={
                **(service.metadata or {}),
                "vat_applicable": False,
                "vat_rate_percentage": 20.0,
                "prices_include_vat": False,
            },
        )

        settings = attr.evolve(
            fixture.gateway.settings,
            services=[service],
        )

        rate = models.RateDetails(
            carrier_id="royalmail",
            carrier_name="royalmail",
            service=service.service_code,
            currency=service.currency,
            total_charge=10.00,
            extra_charges=[],
            meta={},
        )

        taxed_rate = royalmail_mapper._apply_royalmail_vat_to_rate(
            rate,
            settings,
        )

        self.assertEqual(taxed_rate.total_charge, 10.00)
        self.assertEqual(taxed_rate.extra_charges, [])
        self.assertNotIn("vat_amount", taxed_rate.meta or {})

    def test_insurance_coverage_filters_rates_to_services_with_enough_compensation(self):
        """
        Karrio UI insurance checkbox sends options.insurance.

        Royal Mail should only return services where services.csv
        included_compensation >= options.insurance.

        For 2100 GBP coverage, Parcelforce Comp 3 / 2500 compensation services
        should remain, while base/Comp1/Comp2 services should be filtered out.
        """
        payload = {
            **fixture.RatePayload,
            "options": {
                **fixture.RatePayload.get("options", {}),
                "insurance": 2100,
                "package_format_identifier": "mediumParcel",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)
        services = {rate["service"] for rate in rates}

        self.assertEqual(messages, [])

        self.assertIn("parcel_force_express_24_insured_2500", services)
        self.assertNotIn("parcel_force_express_24", services)
        self.assertNotIn("parcel_force_express_24_insured_150", services)
        self.assertNotIn("parcel_force_express_24_insured_750", services)

        for rate in rates:
            included_compensation = provider_units.included_compensation_amount(
                rate["service"]
            )

            self.assertIsNotNone(
                included_compensation,
                msg=f"{rate['service']} is missing included compensation metadata",
            )
            self.assertGreaterEqual(
                included_compensation,
                2100,
                msg=f"{rate['service']} does not cover requested insurance",
            )

            self.assertGreaterEqual(
                rate["meta"].get("included_compensation", 0),
                2100,
            )

    def test_insurance_coverage_50_allows_international_tracked_ota(self):
        """
        If the user requests insurance coverage <= 50, OTA International Tracked
        services are still eligible because their CSV included_compensation is
        50.
        """
        payload = {
            **fixture.RatePayload,
            "recipient": {
                **fixture.RatePayload["recipient"],
                "address_line1": "10 Rue de Rivoli",
                "city": "Paris",
                "postal_code": "75001",
                "country_code": "FR",
            },
            "services": ["OTA"],
            "options": {
                **fixture.RatePayload.get("options", {}),
                "insurance": 50,
                "package_format_identifier": "smallParcel",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)
        services = {rate["service"] for rate in rates}

        self.assertEqual(messages, [])
        self.assertIn("royal_mail_international_tracked_small_parcel", services)

        for rate in rates:
            self.assertGreaterEqual(
                provider_units.included_compensation_amount(rate["service"]),
                50,
            )

    def test_requested_service_with_insufficient_compensation_returns_rating_message(self):
        """
        If a caller explicitly requests a service that cannot cover the selected
        Karrio insurance value, remove the rate and return a useful message.
        """
        payload = {
            **fixture.RatePayload,
            "services": ["parcel_force_express_24"],
            "options": {
                **fixture.RatePayload.get("options", {}),
                "insurance": 2100,
                "package_format_identifier": "mediumParcel",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "insurance_coverage_not_supported"
                for message in messages
            )
        )

    def test_default_rate_table_reference_excludes_inactive_csv_services(self):
        """
        Karrio references['ratesheets'] is built from METADATA.service_levels.

        Therefore REFERENCE_SERVICE_LEVELS must not include inactive services,
        otherwise the rate table UI will show active=False rows from services.csv.
        """
        inactive_codes = {
            service.service_code
            for service in provider_units.DEFAULT_SERVICES
            if not provider_units.service_is_active(service)
        }

        reference_codes = {
            service["service_code"]
            for service in provider_units.REFERENCE_SERVICE_LEVELS
        }

        self.assertTrue(
            inactive_codes,
            msg="Test requires at least one inactive service in services.csv",
        )
        self.assertFalse(
            inactive_codes & reference_codes,
            msg=f"Inactive services leaked into rate-table references: {inactive_codes & reference_codes}",
        )

    def test_shipping_service_enum_excludes_inactive_csv_services(self):
        inactive_codes = {
            service.service_code
            for service in provider_units.DEFAULT_SERVICES
            if not provider_units.service_is_active(service)
        }

        enum_codes = set(provider_units.ShippingService.__members__.keys())

        self.assertFalse(
            inactive_codes & enum_codes,
            msg=f"Inactive services leaked into ShippingService enum: {inactive_codes & enum_codes}",
        )

    def test_inactive_exact_service_selector_resolves_to_no_rate_services(self):
        inactive_service = next(
            service
            for service in provider_units.DEFAULT_SERVICES
            if not provider_units.service_is_active(service)
        )

        self.assertEqual(
            provider_units.resolve_rate_service_codes(inactive_service.service_code),
            [],
        )

    def test_string_false_active_service_is_not_rated(self):
        """
        Defensive regression test for server/rate-table paths where active may
        arrive as the string 'False'. Python would otherwise treat it as truthy.
        """
        service, _ = self._first_domestic_service_with_rate()
        disabled_service = attr.evolve(service, active="False")

        settings = attr.evolve(
            fixture.gateway.settings,
            services=[disabled_service],
        )

        response = royalmail_proxy.Proxy(settings=settings).get_rates(
            lib.Serializable(self.RateRequest)
        ).deserialize()

        returned_rates = [
            rate
            for _, package_result in response
            for rate in package_result[0]
        ]

        self.assertEqual(returned_rates, [])

    def test_reference_service_zones_are_priced_and_weight_banded(self):
        """
        Every Royal Mail ServiceZone exposed to default rate sheets must be a
        priced weight band.
        """
        bad_zones = []

        for service in provider_units.REFERENCE_SERVICE_LEVELS:
            for zone in service.get("zones") or []:
                rate = zone.get("rate")
                min_weight = zone.get("min_weight")
                max_weight = zone.get("max_weight")

                if (
                    rate in [None, ""]
                    or min_weight in [None, ""]
                    or max_weight in [None, ""]
                    or float(min_weight) <= 0
                    or float(max_weight) <= float(min_weight)
                ):
                    bad_zones.append(
                        {
                            "service_code": service.get("service_code"),
                            "zone": zone,
                        }
                    )

        self.assertEqual(bad_zones, [])

    def test_reference_service_zone_weight_bands_do_not_overlap(self):
        """
        Bands for the same service + zone must not overlap.
        """
        overlaps = []

        for service in provider_units.REFERENCE_SERVICE_LEVELS:
            groups = {}

            for zone in service.get("zones") or []:
                key = (
                    service.get("service_code"),
                    zone.get("id"),
                    zone.get("label"),
                    tuple(sorted(zone.get("country_codes") or [])),
                    tuple(sorted(zone.get("postal_codes") or [])),
                    tuple(sorted(zone.get("cities") or [])),
                )

                groups.setdefault(key, []).append(zone)

            for key, zones in groups.items():
                zones = sorted(
                    zones,
                    key=lambda item: (
                        float(item.get("min_weight")),
                        float(item.get("max_weight")),
                    ),
                )

                previous_zone = None

                for zone in zones:
                    if (
                        previous_zone is not None
                        and float(zone.get("min_weight")) < float(previous_zone.get("max_weight"))
                    ):
                        overlaps.append(
                            {
                                "key": key,
                                "previous": previous_zone,
                                "current": zone,
                            }
                        )

                    previous_zone = zone

        self.assertEqual(overlaps, [])

    def test_default_rate_table_reference_populates_service_rates(self):
        """
        Regression test for the rate-sheet UI showing '-' in cells.
        """
        rate_sheet = transform_to_shared_zones_format(
            provider_units.REFERENCE_SERVICE_LEVELS
        )

        services = rate_sheet["services"]
        zones = rate_sheet["zones"]
        service_rates = rate_sheet["service_rates"]

        service = next(
            item
            for item in services
            if item["service_code"] == "royal_mail_international_economy_small_parcel"
        )

        europe_zone_1 = next(
            zone
            for zone in zones
            if zone["label"] == "Europe Zone 1"
        )

        matching_rates = [
            rate
            for rate in service_rates
            if rate["service_id"] == service["id"]
            and rate["zone_id"] == europe_zone_1["id"]
            and rate["min_weight"] == 0.001
            and rate["max_weight"] == 0.100001
        ]

        self.assertEqual(len(matching_rates), 1)
        self.assertEqual(matching_rates[0]["rate"], 14.70)

    def test_default_rate_table_reference_does_not_emit_blank_rate_rows(self):
        """
        Default rate-sheet references must not emit blank/null service_rates.
        """
        rate_sheet = transform_to_shared_zones_format(
            provider_units.REFERENCE_SERVICE_LEVELS
        )

        bad_rates = [
            rate
            for rate in rate_sheet["service_rates"]
            if rate.get("rate") in [None, ""]
            or rate.get("min_weight") in [None, ""]
            or rate.get("max_weight") in [None, ""]
            or float(rate.get("min_weight")) <= 0
            or float(rate.get("max_weight")) <= float(rate.get("min_weight"))
        ]

        self.assertEqual(bad_rates, [])

    def _letter_rate_payload(self, **options):
        payload = copy.deepcopy(fixture.RatePayload)

        payload["parcels"] = [
            {
                "dimension_unit": "CM",
                "height": 0.5,
                "is_document": False,
                "length": 16.5,
                "package_format_identifier": "letter",
                "packaging_type": "letter",
                "weight": 50,
                "weight_unit": "G",
                "width": 24,
            }
        ]

        payload["options"] = {
            **payload.get("options", {}),
            "package_format_identifier": "letter",
            **options,
        }

        return payload

    def test_is_tracked_option_filters_rates_to_tracked_services(self):
        """
        Karrio API callers can request tracked services with:

            options.is_tracked = true

        Royal Mail local rating should then return only services whose
        services.csv feature metadata includes `tracked`.
        """
        payload = self._letter_rate_payload(is_tracked=True)

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertGreater(len(rates), 0)

        for rate in rates:
            with self.subTest(service=rate["service"]):
                service = provider_units.resolve_service_level(rate["service"])

                self.assertIsNotNone(service)
                self.assertTrue(
                    getattr(service.features, "tracked", False),
                    msg=(
                        "options.is_tracked=true should only return tracked "
                        f"services, but got {rate['service']}"
                    ),
                )

    def test_features_option_filters_rates_to_tracked_services(self):
        """
        Karrio universal rating has an options.features convention.

        The Royal Mail extension enforces it locally because the universal
        rating proxy currently passes required_features through without
        applying the filter.
        """
        payload = self._letter_rate_payload(features=["tracked"])

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertGreater(len(rates), 0)

        for rate in rates:
            with self.subTest(service=rate["service"]):
                service = provider_units.resolve_service_level(rate["service"])

                self.assertIsNotNone(service)
                self.assertTrue(
                    getattr(service.features, "tracked", False),
                    msg=(
                        "options.features=['tracked'] should only return "
                        f"tracked services, but got {rate['service']}"
                    ),
                )

    def test_explicit_untracked_service_with_is_tracked_returns_rating_message(self):
        """
        If the caller explicitly asks for an untracked service while also
        requiring tracking, remove the rate and return a helpful message.
        """
        payload = self._letter_rate_payload(is_tracked=True)
        payload["services"] = ["royal_mail_first_class_letter"]

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(fixture.gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "required_feature_not_supported"
                for message in messages
            ),
            msg=messages,
        )

if __name__ == "__main__":
    unittest.main()