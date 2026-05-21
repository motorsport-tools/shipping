"""Royal Mail Click & Drop Karrio Rating API selector/filter contract tests.

These tests exercise the connector through the public Karrio SDK surface
(`karrio.Rating.fetch(...).from_(gateway).parse()`), not only through helper
functions. They are intended to catch regressions in local rate-table filtering,
service selection, connection service whitelists, and selected rating options.
"""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail.units as provider_units
import karrio.sdk as karrio

from . import fixture


def make_gateway(config=None):
    """Create a Royal Mail gateway with optional connection config overrides."""
    return karrio.gateway["royalmail"].create(
        {
            "id": "123456789",
            "carrier_id": "royalmail",
            "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
            "tracking_client_id": "ROYALMAIL_TRACKING_CLIENT_ID",
            "tracking_client_secret": "ROYALMAIL_TRACKING_CLIENT_SECRET",
            "config": {
                "click_and_drop_api_base_url": "https://api.parcel.royalmail.com/api/v1",
                "tracking_api_base_url": "https://api.royalmail.net",
                **(config or {}),
            },
        }
    )


def fetch_rates(payload, gateway=fixture.gateway):
    """Fetch rates through the public Karrio Rating API and return plain dicts."""
    response = (
        karrio.Rating.fetch(models.RateRequest(**payload))
        .from_(gateway)
        .parse()
    )

    return lib.to_dict(response)


def rate_service_codes(rates):
    return [rate["service"] for rate in rates]


def charge_by_name(rate):
    return {
        charge["name"]: charge
        for charge in rate.get("extra_charges", [])
    }


def service_level(service_code):
    service = provider_units.resolve_service_level(service_code)
    if service is None:
        raise AssertionError(f"{service_code!r} is not an active Royal Mail service")
    return service


def assert_rates_support_feature(testcase, rates, feature_name):
    testcase.assertGreater(len(rates), 0)

    for rate in rates:
        with testcase.subTest(service=rate["service"], feature=feature_name):
            service = service_level(rate["service"])
            value = getattr(service.features, feature_name, None)
            testcase.assertTrue(
                value is True or value not in [None, "", False],
                msg=f"{rate['service']} does not support {feature_name}",
            )


def domestic_payload(
    *,
    package_format="smallParcel",
    services=None,
    options=None,
    is_return=False,
):
    """Build a GB->GB rate request with package dimensions matching the format."""
    payload = copy.deepcopy(fixture.RatePayload)

    package_shapes = {
        "letter": {
            "weight": 50,
            "weight_unit": "G",
            "length": 16.5,
            "width": 24.0,
            "height": 0.5,
            "dimension_unit": "CM",
            "packaging_type": "letter",
            "package_format_identifier": "letter",
        },
        "largeLetter": {
            "weight": 100,
            "weight_unit": "G",
            "length": 35.3,
            "width": 25.0,
            "height": 2.5,
            "dimension_unit": "CM",
            "packaging_type": "largeLetter",
            "package_format_identifier": "largeLetter",
        },
        "smallParcel": {
            "weight": 0.5,
            "weight_unit": "KG",
            "length": 25.0,
            "width": 18.0,
            "height": 5.0,
            "dimension_unit": "CM",
            "packaging_type": "smallParcel",
            "package_format_identifier": "smallParcel",
        },
        "mediumParcel": {
            "weight": 2.5,
            "weight_unit": "KG",
            "length": 50.0,
            "width": 40.0,
            "height": 20.0,
            "dimension_unit": "CM",
            "packaging_type": "mediumParcel",
            "package_format_identifier": "mediumParcel",
        },
    }

    payload["parcels"] = [copy.deepcopy(package_shapes[package_format])]
    payload["services"] = copy.deepcopy(services or [])
    payload["is_return"] = is_return
    payload["options"] = {
        **payload.get("options", {}),
        "package_format_identifier": package_format,
        **(options or {}),
    }

    return payload


def international_payload(
    *,
    country_code="FR",
    package_format="smallParcel",
    services=None,
    options=None,
):
    payload = domestic_payload(
        package_format=package_format,
        services=services,
        options=options,
    )
    payload["recipient"] = {
        "address_line1": "10 Rue de Rivoli",
        "city": "Paris",
        "country_code": country_code,
        "person_name": "Jean Martin",
        "postal_code": "75001",
    }

    return payload


class TestRoyalMailRateApiSelectorsAndOptions(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_rating_fetch_is_local_and_does_not_call_click_and_drop_http(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["royal_mail_tracked_24"],
        )

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        mock.assert_not_called()
        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_tracked_24"])

    def test_requested_canonical_service_returns_only_that_service(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["royal_mail_tracked_24"],
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_tracked_24"])
        self.assertEqual(rates[0]["meta"]["carrier_service_code"], "TPN24")

    def test_requested_raw_carrier_service_code_resolves_to_canonical_rate_service(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["TPN24"],
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_tracked_24"])
        self.assertEqual(rates[0]["meta"]["carrier_service_code"], "TPN24")

    def test_raw_international_service_code_is_narrowed_by_package_format(self):
        payload = international_payload(
            package_format="smallParcel",
            services=["OTA"],
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(
            rate_service_codes(rates),
            ["royal_mail_international_tracked_small_parcel"],
        )
        self.assertEqual(rates[0]["meta"]["carrier_service_code"], "OTA")

    def test_connection_shipping_services_whitelist_limits_local_rating(self):
        gateway = make_gateway(
            {
                "shipping_services": ["royal_mail_tracked_24"],
            }
        )
        payload = domestic_payload(
            package_format="smallParcel",
            services=[],
        )

        rates, messages = fetch_rates(payload, gateway=gateway)

        print("configured service codes:", gateway.settings.configured_shipping_service_codes)
        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_tracked_24"])

    def test_requested_service_outside_connection_whitelist_is_not_returned(self):
        gateway = make_gateway(
            {
                "shipping_services": ["royal_mail_tracked_24"],
            }
        )
        payload = domestic_payload(
            package_format="mediumParcel",
            services=["parcel_force_express_24"],
        )

        rates, messages = fetch_rates(payload, gateway=gateway)

        print("configured service codes:", gateway.settings.configured_shipping_service_codes)
        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(rates, [])
        self.assertNotIn(
            "parcel_force_express_24",
            [
                rate["service"]
                for rate in rates
            ],
        )

    def test_is_tracked_false_does_not_filter_untracked_requested_service(self):
        payload = domestic_payload(
            package_format="letter",
            services=["royal_mail_first_class_letter"],
            options={"is_tracked": "false"},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_first_class_letter"])

    def test_is_tracked_true_filters_untracked_requested_service_with_message(self):
        payload = domestic_payload(
            package_format="letter",
            services=["royal_mail_first_class_letter"],
            options={"is_tracked": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "required_feature_not_supported"
                for message in messages
            ),
            messages,
        )

    def test_features_option_accepts_string_list_and_dict_forms(self):
        cases = [
            {"features": "tracked"},
            {"features": ["tracked"]},
            {"required_features": {"tracked": True, "signature": False}},
        ]

        for options in cases:
            with self.subTest(options=options):
                payload = domestic_payload(
                    package_format="letter",
                    services=[],
                    options=options,
                )

                rates, messages = fetch_rates(payload)

                print("options:", options)
                print("rates:", rates)
                print("messages:", messages)

                self.assertEqual(messages, [])
                assert_rates_support_feature(self, rates, "tracked")

    def test_signature_confirmation_option_adds_selected_surcharge_to_rate(self):
        payload = domestic_payload(
            package_format="letter",
            services=["royal_mail_first_class_letter"],
            options={"signature_confirmation": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_first_class_letter"])

        charges = charge_by_name(rates[0])

        self.assertIn("Signature on delivery", charges)
        self.assertEqual(charges["Signature on delivery"]["amount"], 2.0)
        self.assertEqual(rates[0]["total_charge"], 3.8)

    def test_signature_confirmation_camel_case_alias_adds_selected_surcharge_to_rate(self):
        payload = domestic_payload(
            package_format="letter",
            services=["royal_mail_first_class_letter"],
            options={"signatureConfirmation": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_first_class_letter"])
        self.assertEqual(
            charge_by_name(rates[0])["Signature on delivery"]["amount"],
            2.0,
        )

    def test_age_verification_option_filters_and_adds_selected_surcharge(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["royal_mail_tracked_24"],
            options={"age_verification": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertEqual(rate_service_codes(rates), ["royal_mail_tracked_24"])

        charges = charge_by_name(rates[0])

        self.assertIn("Age verification", charges)
        self.assertEqual(charges["Age verification"]["amount"], 2.4)

    def test_id_verification_option_returns_message_when_no_service_supports_it(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["royal_mail_tracked_24"],
            options={"id_verification": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "required_feature_not_supported"
                and "id_verification"
                in message.get("details", {}).get("required_features", [])
                for message in messages
            ),
            messages,
        )

    def test_dangerous_good_option_returns_message_for_explicit_unsupported_service(self):
        payload = domestic_payload(
            package_format="smallParcel",
            services=["royal_mail_tracked_24"],
            options={"dangerous_good": True},
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "required_feature_not_supported"
                and "dangerous_goods"
                in message.get("details", {}).get("required_features", [])
                for message in messages
            ),
            messages,
        )

    def test_rate_request_is_return_filters_to_return_services(self):
        payload = domestic_payload(
            package_format="mediumParcel",
            services=[],
            is_return=True,
        )

        rates, messages = fetch_rates(payload)

        print("rates:", rates)
        print("messages:", messages)

        self.assertEqual(messages, [])
        self.assertGreater(len(rates), 0)

        for rate in rates:
            with self.subTest(service=rate["service"]):
                service = service_level(rate["service"])
                self.assertEqual(service.features.shipment_type, "returns")


if __name__ == "__main__":
    unittest.main()