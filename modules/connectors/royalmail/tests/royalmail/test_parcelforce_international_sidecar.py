"""Parcelforce international sidecar rate-table tests."""

import copy
import unittest

import attr
import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.royalmail.proxy as royalmail_proxy
import karrio.providers.royalmail.units as provider_units

from . import fixture


def _charge_amounts(rate):
    return {
        charge["name"]: charge["amount"]
        for charge in rate.get("extra_charges", [])
    }


class TestParcelforceInternationalSidecar(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _sidecar_service(self, service_code):
        service = provider_units.SERVICE_LEVEL_BY_CODE.get(service_code)

        if service is None:
            self.skipTest(
                f"{service_code} is not active. "
                "Check that parcelforce-international-services.csv is packaged "
                "and loaded."
            )

        return service

    def test_sidecar_activates_er3_and_loads_germany_rate_bands(self):
        service = self._sidecar_service(
            "parcel_force_europriority_dtp_ioss_insured_2500"
        )

        self.assertTrue(provider_units.service_is_active(service))

        germany_zones = [
            zone
            for zone in service.zones or []
            if "DE" in (zone.country_codes or [])
        ]

        self.assertEqual(len(germany_zones), 30)

        first_band = next(
            zone
            for zone in germany_zones
            if zone.min_weight == 0.001
        )

        top_band = max(germany_zones, key=lambda zone: zone.max_weight)

        self.assertEqual(first_band.rate, 7.22)
        self.assertEqual(top_band.rate, 22.44)

    def test_sidecar_loads_country_specific_additional_kg_surcharge_map(self):
        service = self._sidecar_service(
            "parcel_force_europriority_dtp_ioss_insured_2500"
        )

        by_country = service.metadata[
            "oversized_surcharge_amount_per_kg_by_country"
        ]

        self.assertEqual(by_country["DE"], 1.08)
        self.assertEqual(by_country["BE"], 0.78)
        self.assertEqual(service.metadata["oversized_surcharge_threshold_kg"], 30.0)
        self.assertEqual(service.metadata["oversized_surcharge_rounding"], "ceil")

    def test_country_specific_oversized_surcharge_is_used(self):
        service = self._sidecar_service(
            "parcel_force_europriority_dtp_ioss_insured_2500"
        )

        rated_service = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 35.0,
                "weight_unit": "KG",
            },
            destination_country_code="DE",
        )

        charges = {
            surcharge.name: surcharge.amount
            for surcharge in rated_service.surcharges
        }

        # Germany ER3 sidecar surcharge is £1.08/kg after 30kg.
        # 35kg - 30kg = 5 chargeable kg.
        self.assertEqual(
            charges["Parcelforce Oversized Surcharge"],
            5.40,
        )

    def test_country_specific_oversized_surcharge_changes_by_destination(self):
        service = self._sidecar_service(
            "parcel_force_europriority_dtp_ioss_insured_2500"
        )

        germany = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 35.0,
                "weight_unit": "KG",
            },
            destination_country_code="DE",
        )

        belgium = royalmail_proxy._with_active_royalmail_surcharges(
            service,
            surcharge_date=None,
            options={},
            parcel={
                "weight": 35.0,
                "weight_unit": "KG",
            },
            destination_country_code="BE",
        )

        germany_charges = {
            surcharge.name: surcharge.amount
            for surcharge in germany.surcharges
        }

        belgium_charges = {
            surcharge.name: surcharge.amount
            for surcharge in belgium.surcharges
        }

        self.assertEqual(
            germany_charges["Parcelforce Oversized Surcharge"],
            5.40,
        )

        # Belgium ER3 sidecar surcharge is £0.78/kg after 30kg.
        self.assertEqual(
            belgium_charges["Parcelforce Oversized Surcharge"],
            3.90,
        )

    def test_rating_uses_30kg_top_band_plus_additional_kg_surcharge(self):
        service = self._sidecar_service(
            "parcel_force_europriority_dtp_ioss_insured_2500"
        )

        settings = attr.evolve(
            fixture.gateway.settings,
            services=[service],
        )

        payload = copy.deepcopy(fixture.RatePayload)
        payload["services"] = [service.service_code]
        payload["recipient"]["country_code"] = "DE"
        payload["options"] = {
            **payload.get("options", {}),
            "rate_date": "2026-05-18",
        }
        payload["parcels"][0].update(
            {
                "weight": 35.0,
                "weight_unit": "KG",
                "length": 20,
                "width": 20,
                "height": 20,
                "dimension_unit": "CM",
            }
        )

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

        charges = _charge_amounts(rates[0])

        # Germany ER3 29-30kg top band from sidecar.
        self.assertEqual(charges["Base Charge"], 22.44)

        # 5kg over threshold * £1.08/kg.
        self.assertEqual(charges["Parcelforce Oversized Surcharge"], 5.40)