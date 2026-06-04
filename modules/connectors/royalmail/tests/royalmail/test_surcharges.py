"Royal Mail UK domestic surcharge rating tests."

import copy
import unittest

import attr
import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.royalmail.proxy as royalmail_proxy
import karrio.providers.royalmail.units as provider_units
import karrio.sdk as karrio
from datetime import date, timedelta

from . import fixture


def _charge_amounts(rate):
    return {
        charge["name"]: charge["amount"]
        for charge in rate.get("extra_charges", [])
    }

def _amount(value, default=0.0):
    if value in [None, ""]:
        return default

    return float(value)


def _money(value):
    return round(float(value), 2)


def _percentage_amount(base, percentage):
    return _money(float(base) * float(percentage) / 100)


def _day_before(date_text):
    return (date.fromisoformat(date_text) - timedelta(days=1)).isoformat()

class TestRoyalMailClickAndDropSurcharges(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    SURCHARGE_METADATA_SERVICE_CODE = "royal_mail_24_Small_Parcel"
    SURCHARGE_RATE_SERVICE_CODE = "royal_mail_tracked_24"

    def _catalogue_service(self, service_code):
        """
        Return a service from the full CSV catalogue.

        Use this for metadata-loading tests. This intentionally includes
        inactive rows because inactive rows can still carry Click & Drop
        metadata such as surcharge amounts, package-format mapping, and
        serviceRegisterCode.
        """
        service = provider_units.ALL_SERVICE_LEVEL_BY_CODE.get(service_code)

        if service is None:
            self.fail(f"{service_code} was not loaded from services.csv")

        return service

    def _active_service(self, service_code):
        """
        Return an active runtime service.

        Use this for actual Rating.fetch(...) tests. If the CSV marks the
        service inactive, the test should not expect the rate mixer to return it.
        """
        service = provider_units.SERVICE_LEVEL_BY_CODE.get(service_code)

        if service is None:
            self.skipTest(
                f"{service_code} is not active in services.csv and should not "
                "be used for runtime rating assertions"
            )

        return service

    def _service_peak_dates(self, service):
        metadata = service.metadata or {}

        peak_start = metadata.get("peak_surcharge_start_date")
        peak_end = metadata.get("peak_surcharge_end_date")

        self.assertNotIn(peak_start, [None, ""])
        self.assertNotIn(peak_end, [None, ""])

        return peak_start, peak_end

    def _rate_for_service(self, service_code, rate_date="2026-05-18"):
        self._active_service(service_code)

        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service_code]
        payload["options"] = {
            **payload.get("options", {}),
            "rate_date": rate_date,
        }

        response = karrio.Rating.fetch(
            models.RateRequest(**payload)
        ).from_(fixture.gateway).parse()

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertEqual(len(rates), 1)

        return rates[0]
    
    def test_services_csv_loads_uk_domestic_surcharges(self):
        service = self._catalogue_service(self.SURCHARGE_METADATA_SERVICE_CODE)
        surcharges = {
            surcharge.id: surcharge
            for surcharge in service.surcharges
        }

        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_FUEL_ENERGY_SURCHARGE_ID].amount,
            16.0,
        )
        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_FUEL_ENERGY_SURCHARGE_ID].surcharge_type,
            "percentage",
        )
        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_GREEN_SURCHARGE_ID].amount,
            0.05,
        )
        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_PEAK_SURCHARGE_ID].amount,
            0.12,
        )

    def test_uso_first_and_second_class_rows_do_not_have_account_surcharges(self):
        for service_code in [
            "royal_mail_first_class_letter",
            "royal_mail_second_class_letter",
            "royal_mail_first_class_signed_letter",
            "royal_mail_second_class_signed_letter",
        ]:
            with self.subTest(service=service_code):
                service = provider_units.SERVICE_LEVEL_BY_CODE[service_code]
                surcharge_ids = {
                    surcharge.id
                    for surcharge in service.surcharges
                }

                self.assertFalse(
                    surcharge_ids.intersection(provider_units.ROYALMAIL_SURCHARGE_IDS)
                )

    def test_peak_surcharge_is_date_limited(self):
        service = self._catalogue_service(self.SURCHARGE_METADATA_SERVICE_CODE)
        peak_start, peak_end = self._service_peak_dates(service)

        outside_peak = provider_units.active_royalmail_surcharges(
            service.surcharges,
            at_date=_day_before(peak_start),
            peak_start_date=peak_start,
            peak_end_date=peak_end,
        )
        inside_peak = provider_units.active_royalmail_surcharges(
            service.surcharges,
            at_date=peak_start,
            peak_start_date=peak_start,
            peak_end_date=peak_end,
        )

        self.assertNotIn(
            provider_units.ROYALMAIL_PEAK_SURCHARGE_ID,
            {surcharge.id for surcharge in outside_peak},
        )
        self.assertIn(
            provider_units.ROYALMAIL_PEAK_SURCHARGE_ID,
            {surcharge.id for surcharge in inside_peak},
        )

    def test_rate_applies_fuel_energy_and_green_outside_peak(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)
        peak_start, _ = self._service_peak_dates(service)

        rate = self._rate_for_service(
            service.service_code,
            rate_date=_day_before(peak_start),
        )
        charges = _charge_amounts(rate)

        base_charge = charges["Base Charge"]
        expected_fuel = _percentage_amount(
            base_charge,
            service.metadata["fuel_energy_surcharge_percentage"],
        )
        expected_green = _amount(service.metadata["green_surcharge_amount"])
        expected_total = _money(base_charge + expected_fuel + expected_green)

        self.assertEqual(rate["total_charge"], expected_total)
        self.assertEqual(charges["Fuel and Energy Surcharge"], expected_fuel)
        self.assertEqual(charges["Green Surcharge"], expected_green)
        self.assertNotIn("Peak Surcharge", charges)

    def test_rate_applies_peak_inside_peak_window(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)
        peak_start, _ = self._service_peak_dates(service)

        rate = self._rate_for_service(
            service.service_code,
            rate_date=peak_start,
        )
        charges = _charge_amounts(rate)

        base_charge = charges["Base Charge"]
        expected_fuel = _percentage_amount(
            base_charge,
            service.metadata["fuel_energy_surcharge_percentage"],
        )
        expected_green = _amount(service.metadata["green_surcharge_amount"])
        expected_peak = _amount(service.metadata["peak_surcharge_amount"])
        expected_total = _money(
            base_charge + expected_fuel + expected_green + expected_peak
        )

        self.assertEqual(rate["total_charge"], expected_total)
        self.assertEqual(charges["Fuel and Energy Surcharge"], expected_fuel)
        self.assertEqual(charges["Green Surcharge"], expected_green)
        self.assertEqual(charges["Peak Surcharge"], expected_peak)

    def test_rate_uses_planned_despatch_date_for_peak_surcharge(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)
        peak_start, _ = self._service_peak_dates(service)

        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service.service_code]
        payload["options"] = {
            **payload.get("options", {}),
            "planned_despatch_date": peak_start,
        }

        response = karrio.Rating.fetch(
            models.RateRequest(**payload)
        ).from_(fixture.gateway).parse()

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertEqual(len(rates), 1)

        charges = _charge_amounts(rates[0])

        base_charge = charges["Base Charge"]
        expected_fuel = _percentage_amount(
            base_charge,
            service.metadata["fuel_energy_surcharge_percentage"],
        )
        expected_green = _amount(service.metadata["green_surcharge_amount"])
        expected_peak = _amount(service.metadata["peak_surcharge_amount"])
        expected_total = _money(
            base_charge + expected_fuel + expected_green + expected_peak
        )

        self.assertEqual(rates[0]["total_charge"], expected_total)
        self.assertEqual(charges["Fuel and Energy Surcharge"], expected_fuel)
        self.assertEqual(charges["Green Surcharge"], expected_green)
        self.assertEqual(charges["Peak Surcharge"], expected_peak)

    def test_rate_uses_planned_despatch_date_camel_case_for_peak_surcharge(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)
        peak_start, _ = self._service_peak_dates(service)

        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service.service_code]
        payload["options"] = {
            **payload.get("options", {}),
            "plannedDespatchDate": peak_start,
        }

        response = karrio.Rating.fetch(
            models.RateRequest(**payload)
        ).from_(fixture.gateway).parse()

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertEqual(len(rates), 1)

        charges = _charge_amounts(rates[0])
        expected_peak = _amount(service.metadata["peak_surcharge_amount"])

        self.assertEqual(charges["Peak Surcharge"], expected_peak)

    def test_parcelforce_services_load_13_percent_fuel_surcharge(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_48_large"]
        surcharges = {
            surcharge.id: surcharge
            for surcharge in service.surcharges
        }

        self.assertEqual(
            surcharges[
                provider_units.ROYALMAIL_PARCELFORCE_FUEL_ENERGY_SURCHARGE_ID
            ].amount,
            13.0,
        )
        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_GREEN_SURCHARGE_ID].amount,
            0.05,
        )
        self.assertEqual(
            surcharges[provider_units.ROYALMAIL_PEAK_SURCHARGE_ID].amount,
            4.50,
        )

    def test_peak_window_uses_service_metadata_dates(self):
        service = self._catalogue_service(self.SURCHARGE_METADATA_SERVICE_CODE)
        peak_start, peak_end = self._service_peak_dates(service)

        self.assertEqual(
            service.metadata["peak_surcharge_start_date"],
            peak_start,
        )
        self.assertEqual(
            service.metadata["peak_surcharge_end_date"],
            peak_end,
        )

        outside_peak = provider_units.active_royalmail_surcharges(
            service.surcharges,
            at_date=_day_before(peak_start),
            peak_start_date=peak_start,
            peak_end_date=peak_end,
        )
        inside_peak = provider_units.active_royalmail_surcharges(
            service.surcharges,
            at_date=peak_start,
            peak_start_date=peak_start,
            peak_end_date=peak_end,
        )

        self.assertNotIn(
            provider_units.ROYALMAIL_PEAK_SURCHARGE_ID,
            {surcharge.id for surcharge in outside_peak},
        )
        self.assertIn(
            provider_units.ROYALMAIL_PEAK_SURCHARGE_ID,
            {surcharge.id for surcharge in inside_peak},
        )

    def test_services_csv_loads_signature_and_age_verification_prices(self):
        """
        Royal Mail optional feature charges should be loaded from services.csv.

        Source guide values:
            - Royal Mail 24/48 signature: £2.00
            - Tracked parcel signature: £0.70
            - Parcelforce express parcel signature: £0.70
            - Age verification: £2.40
        """
        royal_mail_24 = self._catalogue_service(
            "royal_mail_24_Small_Parcel"
        )
        tracked_24 = self._catalogue_service(
            "royal_mail_tracked_24"
        )
        parcelforce_24 = self._catalogue_service(
            "parcel_force_express_24"
        )

        self.assertEqual(
            royal_mail_24.metadata["signature_surcharge_amount"],
            2.00,
        )

        self.assertEqual(
            tracked_24.metadata["signature_surcharge_amount"],
            0.70,
        )
        self.assertEqual(
            tracked_24.metadata["signature_surcharge_large_letter_amount"],
            1.10,
        )
        self.assertEqual(
            tracked_24.metadata["signature_surcharge_parcel_amount"],
            0.70,
        )
        self.assertEqual(
            tracked_24.metadata["age_verification_surcharge_amount"],
            2.40,
        )

        self.assertEqual(
            parcelforce_24.metadata["signature_surcharge_amount"],
            0.70,
        )
        self.assertEqual(
            parcelforce_24.metadata["age_verification_surcharge_amount"],
            2.40,
        )

    def test_signature_surcharge_uses_tracked_large_letter_price_when_requested(self):
        """
        Royal Mail Tracked signature pricing differs by package format:
            largeLetter -> £1.10
            parcel      -> £0.70
        """
        service = provider_units.SERVICE_LEVEL_BY_CODE["royal_mail_tracked_24"]

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={
                "request_signature_upon_delivery": True,
                "package_format_identifier": "largeLetter",
            },
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertIn(
            {
                "id": "royalmail_signature_on_delivery",
                "name": "Signature on delivery",
                "amount": 1.10,
                "surcharge_type": "fixed",
                "active": True,
            },
            surcharges,
        )

    def test_signature_surcharge_uses_tracked_parcel_price_by_default(self):
        """
        Tracked parcel signature should use the 70p surcharge.
        """
        service = provider_units.SERVICE_LEVEL_BY_CODE["royal_mail_tracked_24"]

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={
                "request_signature_upon_delivery": True,
                "package_format_identifier": "mediumParcel",
            },
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertIn(
            {
                "id": "royalmail_signature_on_delivery",
                "name": "Signature on delivery",
                "amount": 0.70,
                "surcharge_type": "fixed",
                "active": True,
            },
            surcharges,
        )

    def test_age_verification_adds_configured_surcharge(self):
        """
        Age verification should add the configured Royal Mail surcharge when the
        user requests the option.
        """
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={
                "royalmail_age_verification": True,
            },
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertIn(
            {
                "id": "royalmail_age_verification",
                "name": "Age verification",
                "amount": 2.40,
                "surcharge_type": "fixed",
                "active": True,
            },
            surcharges,
        )

    def test_parcelforce_oversized_surcharge_is_calculated_per_kg_over_threshold(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        service = attr.evolve(
            service,
            max_weight=30.0,
            metadata={
                **(service.metadata or {}),
                "oversized_surcharge_amount_per_kg": 10.00,
                "oversized_surcharge_threshold_kg": 30.0,
                "oversized_surcharge_rounding": "ceil",
            },
            surcharges=[],
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 35.0,
                "weight_unit": "KG",
            },
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertIn(
            {
                "id": "royalmail_parcelforce_oversized",
                "name": "Parcelforce Oversized Surcharge",
                "amount": 50.0,
                "surcharge_type": "fixed",
                "active": True,
            },
            surcharges,
        )

        # The original 30kg max should be relaxed for this rated parcel so the
        # universal rating engine can return the base rate plus overweight surcharge.
        self.assertEqual(rated_service.max_weight, 35.0)


    def test_parcelforce_oversized_surcharge_is_not_added_at_threshold(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        service = attr.evolve(
            service,
            max_weight=30.0,
            metadata={
                **(service.metadata or {}),
                "oversized_surcharge_amount_per_kg": 10.00,
                "oversized_surcharge_threshold_kg": 30.0,
                "oversized_surcharge_rounding": "ceil",
            },
            surcharges=[],
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 30.0,
                "weight_unit": "KG",
            },
        )

        self.assertEqual(rated_service.surcharges, [])


    def test_parcelforce_oversized_surcharge_supports_gram_weights(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        service = attr.evolve(
            service,
            max_weight=30.0,
            metadata={
                **(service.metadata or {}),
                "oversized_surcharge_amount_per_kg": 10.00,
                "oversized_surcharge_threshold_kg": 30.0,
                "oversized_surcharge_rounding": "ceil",
            },
            surcharges=[],
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 35000,
                "weight_unit": "G",
            },
        )

        charges = {
            surcharge.name: surcharge.amount
            for surcharge in rated_service.surcharges
        }

        self.assertEqual(
            charges["Parcelforce Oversized Surcharge"],
            50.0,
        )


    def test_rate_applies_parcelforce_oversized_surcharge_to_total(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        # Force the normal max/zone max to 30kg to prove the oversized helper opens
        # the top band for the rated parcel.
        zones = [
            attr.evolve(
                zone,
                max_weight=30.0,
            )
            for zone in service.zones or []
        ]

        service = attr.evolve(
            service,
            max_weight=30.0,
            zones=zones,
            metadata={
                **(service.metadata or {}),
                "oversized_surcharge_amount_per_kg": 10.00,
                "oversized_surcharge_threshold_kg": 30.0,
                "oversized_surcharge_rounding": "ceil",
                "vat_applicable": False,
            },
            surcharges=[],
        )

        settings = attr.evolve(
            fixture.gateway.settings,
            services=[service],
        )

        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service.service_code]
        payload["parcels"][0]["weight"] = 35.0
        payload["parcels"][0]["weight_unit"] = "KG"

        response = royalmail_proxy.Proxy(settings=settings).get_rates(
            lib.Serializable(
                models.RateRequest(**payload)
            )
        ).deserialize()

        rates, messages = response[0][1]
        rates = lib.to_dict(rates)
        messages = lib.to_dict(messages)

        self.assertEqual(messages, [])
        self.assertEqual(len(rates), 1)

        rate = rates[0]
        charges = _charge_amounts(rate)

        self.assertEqual(
            charges["Parcelforce Oversized Surcharge"],
            50.0,
        )

        expected_total = _money(
            charges["Base Charge"]
            + charges["Parcelforce Oversized Surcharge"]
        )

        self.assertEqual(
            rate["total_charge"],
            expected_total,
        )

    def test_parcelforce_chargeable_weight_uses_volumetric_weight(self):
        parcel = {
            "weight": 8000,
            "weight_unit": "G",
            "length": 40,
            "width": 30,
            "height": 50,
            "dimension_unit": "CM",
        }

        self.assertEqual(
            royalmail_proxy._parcel_chargeable_weight_kg(parcel),
            12.0,
        )

    def test_parcelforce_oversized_surcharge_uses_volumetric_weight_over_30kg(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE["parcel_force_express_24"]

        service = attr.evolve(
            service,
            max_weight=30.0,
            metadata={
                **(service.metadata or {}),
                "oversized_surcharge_amount_per_kg": 10.00,
                "oversized_surcharge_threshold_kg": 30.0,
                "oversized_surcharge_rounding": "ceil",
            },
            surcharges=[],
        )

        # Declared/pre-advised Click & Drop weight is only 8kg and is therefore
        # valid for the API's 30000g package limit.
        #
        # Rating weight is different:
        #   100cm * 50cm * 40cm / 5000 = 40kg volumetric
        #
        # Additional kg after 30kg:
        #   40kg - 30kg = 10kg
        #   10kg * £10 = £100
        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 8000,
                "weight_unit": "G",
                "length": 100,
                "width": 50,
                "height": 40,
                "dimension_unit": "CM",
            },
        )

        surcharges = lib.to_dict(rated_service.surcharges)

        self.assertIn(
            {
                "id": "royalmail_parcelforce_oversized",
                "name": "Parcelforce Oversized Surcharge",
                "amount": 100.0,
                "surcharge_type": "fixed",
                "active": True,
            },
            surcharges,
        )

        self.assertEqual(rated_service.max_weight, 40.0)

    def test_rate_normalization_defaults_to_declared_weight(self):
        parcel = {
            "weight": 8000,
            "weight_unit": "G",
            "length": 40,
            "width": 30,
            "height": 50,
            "dimension_unit": "CM",
        }

        normalized = royalmail_proxy._normalize_rate_parcel_for_universal_rating(parcel)

        # Normal Royal Mail rating pass uses declared/pre-advised weight.
        self.assertEqual(normalized["weight"], 8.0)
        self.assertEqual(normalized["weight_unit"], "KG")

        # Original parcel is not mutated.
        self.assertEqual(parcel["weight"], 8000)
        self.assertEqual(parcel["weight_unit"], "G")


    def test_rate_normalization_can_use_chargeable_weight_for_parcelforce_pass(self):
        parcel = {
            "weight": 8000,
            "weight_unit": "G",
            "length": 40,
            "width": 30,
            "height": 50,
            "dimension_unit": "CM",
        }

        normalized = royalmail_proxy._normalize_rate_parcel_for_universal_rating(
            parcel,
            use_chargeable_weight=True,
        )

        # Parcelforce chargeable-weight pass uses volumetric/chargeable weight.
        self.assertEqual(normalized["weight"], 12.0)
        self.assertEqual(normalized["weight_unit"], "KG")

        # Original parcel is not mutated. Shipment creation can still send
        # weightInGrams = 8000 to Click & Drop.
        self.assertEqual(parcel["weight"], 8000)
        self.assertEqual(parcel["weight_unit"], "G")

    def _settings_with_large_packaging_charge(self, service, enabled=True):
        return attr.evolve(
            fixture.gateway.settings,
            services=[service],
            config={
                **(fixture.gateway.settings.config or {}),
                "apply_large_packaging_charge_to_rates": enabled,
            },
        )

    def _large_packaging_rate_payload(self, service_code, parcel_values):
        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service_code]
        payload["parcels"] = []

        for index, value in enumerate(parcel_values, start=1):
            parcel = copy.deepcopy(fixture.RatePayload["parcels"][0])
            parcel["items"] = [
                {
                    "description": f"Rated item {index}",
                    "sku": f"LPC-{index}",
                    "quantity": 1,
                    "value_amount": value,
                    "weight": 0.1,
                    "weight_unit": "KG",
                }
            ]
            payload["parcels"].append(parcel)

        return payload

    def test_large_packaging_charge_tiers_are_based_on_order_items_total(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)

        service = attr.evolve(
            service,
            surcharges=[],
            metadata={
                **(service.metadata or {}),
                "vat_applicable": False,
            },
        )

        settings = self._settings_with_large_packaging_charge(
            service,
            enabled=True,
        )

        cases = [
            # Exact thresholds are not charged at the higher tier because the
            # rule is "order value over £X".
            (500.00, None),
            (500.01, 5.00),
            (1000.00, 5.00),
            (1000.01, 10.00),
            (2000.00, 10.00),
            (2000.01, 15.00),
            (3000.00, 15.00),
            (3000.01, 20.00),
        ]

        for order_value, expected_amount in cases:
            with self.subTest(order_value=order_value):
                payload = self._large_packaging_rate_payload(
                    service.service_code,
                    [order_value],
                )

                surcharge = royalmail_proxy._royalmail_large_packaging_charge_surcharge(
                    settings,
                    models.RateRequest(**payload),
                )

                actual_amount = (
                    None
                    if surcharge is None
                    else surcharge.amount
                )

                self.assertEqual(actual_amount, expected_amount)

    def test_large_packaging_charge_is_disabled_by_default(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)

        service = attr.evolve(
            service,
            surcharges=[],
            metadata={
                **(service.metadata or {}),
                "vat_applicable": False,
            },
        )

        settings = self._settings_with_large_packaging_charge(
            service,
            enabled=False,
        )

        payload = self._large_packaging_rate_payload(
            service.service_code,
            [3000.01],
        )

        surcharge = royalmail_proxy._royalmail_large_packaging_charge_surcharge(
            settings,
            models.RateRequest(**payload),
        )

        self.assertIsNone(surcharge)

    def test_rate_applies_large_packaging_charge_once_per_parcel_when_enabled(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)

        service = attr.evolve(
            service,
            surcharges=[],
            metadata={
                **(service.metadata or {}),
                "vat_applicable": False,
            },
        )

        settings = self._settings_with_large_packaging_charge(
            service,
            enabled=True,
        )

        # Full order item value = £1001, so the £10-per-parcel tier applies.
        payload = self._large_packaging_rate_payload(
            service.service_code,
            [600.00, 401.00],
        )

        response = royalmail_proxy.Proxy(settings=settings).get_rates(
            lib.Serializable(
                models.RateRequest(**payload)
            )
        ).deserialize()

        self.assertEqual(len(response), 2)

        for _, package_response in response:
            rates, messages = package_response
            rates = lib.to_dict(rates)
            messages = lib.to_dict(messages)

            self.assertEqual(messages, [])
            self.assertEqual(len(rates), 1)

            rate = rates[0]
            charges = _charge_amounts(rate)

            self.assertEqual(
                charges["Large Packaging Charge"],
                10.00,
            )

            self.assertEqual(
                rate["total_charge"],
                _money(
                    charges["Base Charge"]
                    + charges["Large Packaging Charge"]
                ),
            )

    def test_large_packaging_charge_uses_quantity_times_item_value(self):
        service = self._active_service(self.SURCHARGE_RATE_SERVICE_CODE)

        service = attr.evolve(
            service,
            surcharges=[],
            metadata={
                **(service.metadata or {}),
                "vat_applicable": False,
            },
        )

        settings = self._settings_with_large_packaging_charge(
            service,
            enabled=True,
        )

        payload = self._large_packaging_rate_payload(
            service.service_code,
            [250.01],
        )
        payload["parcels"][0]["items"][0]["quantity"] = 2

        surcharge = royalmail_proxy._royalmail_large_packaging_charge_surcharge(
            settings,
            models.RateRequest(**payload),
        )

        # 250.01 * 2 = 500.02, so the first tier applies.
        self.assertIsNotNone(surcharge)
        self.assertEqual(surcharge.amount, 5.00)