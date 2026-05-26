"""Royal Mail Click & Drop international rate-table matrix tests."""

import copy
import unittest

from .fixture import gateway

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio


GBShipper = {
    "address_line1": "Carnguwch",
    "address_line2": "Llithfaen",
    "city": "Pwllheli",
    "company_name": "Motorsport Tools Ltd",
    "country_code": "GB",
    "email": "sales@example.co.uk",
    "person_name": "Sales Team",
    "phone_number": "01758750000",
    "postal_code": "LL536NH",
}

Recipients = {
    "FR": {
        "address_line1": "10 Rue de Rivoli",
        "city": "Paris",
        "country_code": "FR",
        "email": "jean.martin@example.fr",
        "person_name": "Jean Martin",
        "phone_number": "+33102030405",
        "postal_code": "75001",
        "residential": True,
    },
    "DE": {
        "address_line1": "Pariser Platz 1",
        "city": "Berlin",
        "country_code": "DE",
        "email": "max.mustermann@example.de",
        "person_name": "Max Mustermann",
        "phone_number": "+4930123456",
        "postal_code": "10117",
        "residential": True,
    },
    "US": {
        "address_line1": "350 Fifth Avenue",
        "city": "New York",
        "country_code": "US",
        "email": "john.smith@example.com",
        "person_name": "John Smith",
        "phone_number": "+12125550100",
        "postal_code": "10118",
        "residential": True,
        "state_code": "NY",
    },
    "AU": {
        "address_line1": "200 George Street",
        "city": "Sydney",
        "country_code": "AU",
        "email": "olivia.brown@example.com.au",
        "person_name": "Olivia Brown",
        "phone_number": "+61290000000",
        "postal_code": "2000",
        "residential": True,
        "state_code": "NSW",
    },
    "CA": {
        "address_line1": "100 Queen Street West",
        "city": "Toronto",
        "country_code": "CA",
        "email": "emily.taylor@example.ca",
        "person_name": "Emily Taylor",
        "phone_number": "+14165550100",
        "postal_code": "M5H 2N2",
        "residential": True,
        "state_code": "ON",
    },
}

Commodity = {
    "description": "test item",
    "hs_code": "87654321",
    "origin_country": "CN",
    "quantity": 1,
    "sku": "00003",
    "title": "ipod",
    "value_amount": 30,
    "value_currency": "GBP",
    "weight": 50,
    "weight_unit": "G",
}

Customs = {
    "certify": True,
    "commercial_invoice": True,
    "commodities": [Commodity],
    "content_description": "Consumer electronics",
    "content_type": "merchandise",
    "duty": {
        "currency": "GBP",
        "declared_value": 30,
        "paid_by": "recipient",
    },
    "incoterm": "DAP",
    "invoice": "INV-INTL-001",
    "invoice_date": "2026-05-15",
    "signer": "Sales Team",
}

DapCustoms = {
    "certify": True,
    "commercial_invoice": True,
    "commodities": [Commodity],
    "content_description": "Consumer electronics",
    "content_type": "merchandise",
    "duty": {
        "currency": "GBP",
        "declared_value": 30,
        "paid_by": "recipient",
    },
    "incoterm": "DAP",
    "invoice": "INV-INTL-001",
    "invoice_date": "2026-05-15",
    "signer": "Sales Team",
}

DdpCustoms = {
    "certify": True,
    "commercial_invoice": True,
    "commodities": [Commodity],
    "content_description": "Consumer electronics",
    "content_type": "merchandise",
    "duty": {
        "currency": "GBP",
        "declared_value": 30,
        "paid_by": "sender",
    },
    "incoterm": "DDP",
    "invoice": "INV-INTL-001",
    "invoice_date": "2026-05-15",
    "signer": "Sales Team",
}

LargeLetterParcel = {
    "dimension_unit": "CM",
    "height": 2.5,
    "is_document": False,
    "items": [Commodity],
    "length": 35.3,
    "package_preset": "royalmail_large_letter",
    "packaging_type": "largeLetter",
    "weight": 50,
    "weight_unit": "G",
    "width": 25,
}

SmallParcel = {
    "dimension_unit": "CM",
    "height": 8,
    "is_document": False,
    "items": [Commodity],
    "length": 20,
    "package_preset": "royalmail_small_parcel",
    "packaging_type": "smallParcel",
    "weight": 50,
    "weight_unit": "G",
    "width": 15,
}

MediumParcel = {
    "dimension_unit": "CM",
    "height": 20,
    "is_document": False,
    "items": [Commodity],
    "length": 50,
    "package_preset": "royalmail_medium_parcel",
    "packaging_type": "mediumParcel",
    "weight": 50,
    "weight_unit": "G",
    "width": 40,
}

RAW_INTERNATIONAL_TRACKED = "OTA"

TRACKED_LARGE_LETTER = "royal_mail_international_tracked_large_letter"
TRACKED_SMALL_PARCEL = "royal_mail_international_tracked_small_parcel"
TRACKED_MEDIUM_PARCEL = "royal_mail_international_tracked_medium_parcel"



def rate_payload(
    country_code: str,
    parcel: dict,
    services=None,
    reference: str = None,
    customs: dict = None,
) -> dict:
    return {
        "shipper": copy.deepcopy(GBShipper),
        "recipient": copy.deepcopy(Recipients[country_code]),
        "parcels": [copy.deepcopy(parcel)],
        "customs": copy.deepcopy(customs or DapCustoms),
        "payment": {"paid_by": "sender"},
        "reference": reference or f"RATE-INTL-{country_code}",
        "services": copy.deepcopy(services or []),
        "options": {
            "currency": "GBP",
            "shipping_date": "2026-05-15T13:34:00Z",
        },
    }

def fetch_rates(payload: dict):
    response = (
        karrio.Rating.fetch(models.RateRequest(**payload))
        .from_(gateway)
        .parse()
    )

    return lib.to_dict(response)


def find_rate(rates, service_code):
    return next(
        (
            rate
            for rate in rates
            if rate["service"] == service_code
        ),
        None,
    )

class TestRoyalMailInternationalRateMatrix(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_mapper_preserves_raw_ota_selector(self):
        """
        Raw Royal Mail service codes such as OTA are intentionally preserved by
        the mapper.

        They are expanded by the proxy during rating because expansion requires
        Royal Mail package-format context.
        """
        cases = [
            ("largeLetter", LargeLetterParcel),
            ("smallParcel", SmallParcel),
            ("mediumParcel", MediumParcel),
        ]

        for package_format, parcel in cases:
            with self.subTest(package_format=package_format):
                payload = rate_payload(
                    "FR",
                    parcel,
                    services=[RAW_INTERNATIONAL_TRACKED],
                )

                request = gateway.mapper.create_rate_request(
                    models.RateRequest(**payload)
                )

                serialized = lib.to_dict(request.serialize())

                self.assertEqual(
                    serialized["services"],
                    [RAW_INTERNATIONAL_TRACKED],
                )

    def test_raw_ota_config_still_returns_international_rate(self):
        configured_gateway = karrio.gateway["royalmail"].create(
            dict(
                id="123456789",
                test_mode=False,
                carrier_id="royalmail",
                click_and_drop_api_key="TEST_API_KEY",
                config={
                    "shipping_services": ["OTA"],
                },
            )
        )

        payload = rate_payload(
            "FR",
            SmallParcel,
            services=["OTA"],
        )

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(configured_gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)



        self.assertEqual(messages, [])

        rate = find_rate(
            rates,
            "royal_mail_international_tracked_small_parcel",
        )

        self.assertIsNotNone(rate)
        self.assertEqual(rate["total_charge"], 11.09)
        self.assertEqual(rate["meta"]["carrier_service_code"], "OTA")

    def test_raw_ota_returns_package_specific_rates(self):
        cases = [
            (
                "largeLetter",
                LargeLetterParcel,
                TRACKED_LARGE_LETTER,
                10.98,
            ),
            (
                "smallParcel",
                SmallParcel,
                TRACKED_SMALL_PARCEL,
                11.09,
            ),
            (
                "mediumParcel",
                MediumParcel,
                TRACKED_MEDIUM_PARCEL,
                13.16,
            ),
        ]

        for package_format, parcel, expected_service, expected_total in cases:
            with self.subTest(package_format=package_format):
                payload = rate_payload(
                    "FR",
                    parcel,
                    services=[RAW_INTERNATIONAL_TRACKED],
                )

                rates, messages = fetch_rates(payload)

                self.assertEqual(messages, [])

                rate = find_rate(rates, expected_service)

                self.assertIsNotNone(
                    rate,
                    f"Expected {expected_service} when rating OTA as {package_format}",
                )
                self.assertEqual(rate["total_charge"], expected_total)
                self.assertEqual(rate["currency"], "GBP")
                self.assertEqual(rate["meta"]["carrier_service_code"], "OTA")

                returned_services = [item["service"] for item in rates]

                if package_format == "largeLetter":
                    self.assertNotIn(TRACKED_SMALL_PARCEL, returned_services)
                    self.assertNotIn(TRACKED_MEDIUM_PARCEL, returned_services)

                if package_format == "smallParcel":
                    self.assertNotIn(TRACKED_LARGE_LETTER, returned_services)
                    self.assertNotIn(TRACKED_MEDIUM_PARCEL, returned_services)

                if package_format == "mediumParcel":
                    self.assertNotIn(TRACKED_LARGE_LETTER, returned_services)
                    self.assertNotIn(TRACKED_SMALL_PARCEL, returned_services)

    def test_international_tracked_large_letter_country_zones(self):
        expected = {
            "FR": 10.98,
            "DE": 10.98,
            "US": 12.21,
            "AU": 12.66,
            "CA": 13.16,
        }

        for country_code, expected_total in expected.items():
            with self.subTest(country_code=country_code):
                payload = rate_payload(
                    country_code,
                    LargeLetterParcel,
                    services=[TRACKED_LARGE_LETTER],
                )

                rates, messages = fetch_rates(payload)

                self.assertEqual(messages, [])

                rate = find_rate(rates, TRACKED_LARGE_LETTER)

                self.assertIsNotNone(rate)
                self.assertEqual(rate["total_charge"], expected_total)
                self.assertEqual(rate["meta"]["carrier_service_code"], "OTA")
                self.assertEqual(
                    rate["meta"]["service_name"],
                    "International Tracked Large Letter",
                )

    def test_international_tracked_small_parcel_country_specific_rows(self):
        expected = {
            "FR": 11.09,
            "DE": 9.13,
            "US": 13.63,
            "AU": 13.83,
            "CA": 16.17,
        }

        for country_code, expected_total in expected.items():
            with self.subTest(country_code=country_code):
                payload = rate_payload(
                    country_code,
                    SmallParcel,
                    services=[TRACKED_SMALL_PARCEL],
                )

                rates, messages = fetch_rates(payload)

                self.assertEqual(messages, [])

                rate = find_rate(rates, TRACKED_SMALL_PARCEL)

                self.assertIsNotNone(rate)
                self.assertEqual(rate["total_charge"], expected_total)
                self.assertEqual(rate["meta"]["carrier_service_code"], "OTA")
                self.assertEqual(
                    rate["meta"]["service_name"],
                    "International Tracked Small Parcel",
                )

    def test_international_tracked_small_parcel_weight_bands(self):
        cases = [
            # country, weight_g, expected surcharge-inclusive rate
            ("FR", 50, 11.09),
            ("FR", 251, 12.15),
            ("FR", 501, 12.43),
            ("DE", 50, 9.13),
            ("DE", 251, 10.53),
            ("US", 50, 13.63),
            ("US", 251, 15.96),
            ("AU", 50, 13.83),
            ("AU", 251, 17.75),
            ("CA", 50, 16.17),
            ("CA", 501, 19.05),
        ]

        for country_code, weight_g, expected_total in cases:
            with self.subTest(country_code=country_code, weight_g=weight_g):
                parcel = copy.deepcopy(SmallParcel)
                parcel["weight"] = weight_g
                parcel["items"][0]["weight"] = weight_g

                payload = rate_payload(
                    country_code,
                    parcel,
                    services=[TRACKED_SMALL_PARCEL],
                )

                rates, messages = fetch_rates(payload)

                self.assertEqual(messages, [])

                rate = find_rate(rates, TRACKED_SMALL_PARCEL)

                self.assertIsNotNone(rate)
                self.assertEqual(rate["total_charge"], expected_total)

    def test_without_requested_services_returns_international_rates(self):
        payload = rate_payload(
            "FR",
            SmallParcel,
            services=[],
        )

        rates, messages = fetch_rates(payload)

        self.assertEqual(messages, [])

        returned_services = [rate["service"] for rate in rates]

        self.assertIn(TRACKED_SMALL_PARCEL, returned_services)
        self.assertIn("royal_mail_international_standard_small_parcel", returned_services)

        self.assertNotIn("royal_mail_24_Small_Parcel", returned_services)
        self.assertNotIn("royal_mail_48_Small_Parcel", returned_services)

    def test_incompatible_package_format_returns_clear_message(self):
        parcel = copy.deepcopy(SmallParcel)

        # Keep dimensions large-letter-compatible so universal rating can match
        # the service first. The Royal Mail package-format filter should then
        # remove it because the caller explicitly said smallParcel.
        parcel["height"] = 2
        parcel["length"] = 20
        parcel["width"] = 15
        parcel["packaging_type"] = "smallParcel"

        payload = rate_payload(
            "FR",
            parcel,
            services=[TRACKED_LARGE_LETTER],
        )

        rates, messages = fetch_rates(payload)

        self.assertEqual(rates, [])

        self.assertTrue(
            any(
                message["code"] == "package_format_not_supported"
                for message in messages
            ),
            messages,
        )


if __name__ == "__main__":
    unittest.main()