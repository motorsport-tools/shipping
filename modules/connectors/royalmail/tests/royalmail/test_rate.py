"""Royal Mail Click and Drop carrier rating tests."""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail.units as provider_units
import karrio.sdk as karrio

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
            if service.active is not False
        }

    def _first_domestic_service_with_rate(self):
        for service in provider_units.DEFAULT_SERVICES:
            if service.active is False:
                continue

            if service.domicile is not True:
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

    def test_get_large_letter_rates_filters_out_parcelforce(self):
        payload = {
            **fixture.RatePayload,
            "recipient": {
                "address_line1": "Ffordd Caergybi",
                "city": "LlanfairPwll",
                "country_code": "GB",
                "email": "richard.al.simcox@gmail.com",
                "person_name": "richard Simcox",
                "phone_number": "07807816582",
                "postal_code": "LL615SJ",
                "residential": True,
                "state_code": "Ynys Mon",
            },
            "shipper": {
                "address_line1": "Carnguwch",
                "address_line2": "Llithfaen",
                "city": "Pwllheli",
                "company_name": "Motorsport Tools Ltd",
                "country_code": "GB",
                "email": "richard.simcox@motorsport-tools.com",
                "person_name": "Sales Team",
                "phone_number": "01758750000",
                "postal_code": "LL536NH",
                "state_code": "Gwynedd",
            },
            "parcels": [
                {
                    "dimension_unit": "CM",
                    "height": 2.5,
                    "is_document": False,
                    "length": 35.3,
                    "package_preset": "royalmail_large_letter",
                    "packaging_type": "largeLetter",
                    "weight": 1,
                    "weight_unit": "G",
                    "width": 25,
                }
            ],
            "options": {
                **fixture.RatePayload.get("options", {}),
                "shipping_date": "2026-05-14T10:56",
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
        self.assertIn("royal_mail_24_LargeLetter", services)
        self.assertIn("royal_mail_48_LargeLetter", services)
        self.assertNotIn("parcel_force_express_24", services)

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

if __name__ == "__main__":
    unittest.main()