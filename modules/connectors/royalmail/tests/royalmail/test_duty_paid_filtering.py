"""Royal Mail Click & Drop DDP/DAP/DTP filtering tests."""

import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.royalmail.units as provider_units

from .fixture import gateway


class TestRoyalMailDutyPaidRateFiltering(unittest.TestCase):
    def test_customs_ddp_alone_does_not_filter_normal_rating_services(self):
        payload = {
            "shipper": {
                "address_line1": "Carnguwch",
                "city": "Pwllheli",
                "country_code": "GB",
                "postal_code": "LL536NH",
                "person_name": "Sender",
            },
            "recipient": {
                "address_line1": "10 Rue de Rivoli",
                "city": "Paris",
                "country_code": "FR",
                "postal_code": "75001",
                "person_name": "Recipient",
            },
            "parcels": [
                {
                    "weight": 50,
                    "weight_unit": "G",
                    "length": 35.3,
                    "width": 25,
                    "height": 2.5,
                    "dimension_unit": "CM",
                    "packaging_type": "largeLetter",
                    "package_preset": "royalmail_large_letter",
                }
            ],
            "customs": {
                "content_type": "merchandise",
                "incoterm": "DDP",
                "commodities": [
                    {
                        "description": "test item",
                        "quantity": 1,
                        "value_amount": 30,
                        "value_currency": "GBP",
                        "weight": 50,
                        "weight_unit": "G",
                    }
                ],
            },
            "services": ["royal_mail_international_tracked_large_letter"],
            "options": {
                "currency": "GBP",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(messages, [])
        self.assertTrue(
            any(
                rate["service"] == "royal_mail_international_tracked_large_letter"
                for rate in rates
            ),
            rates,
        )

    def test_options_duty_paid_filters_non_ddp_rating_services(self):
        payload = {
            "shipper": {
                "address_line1": "Carnguwch",
                "city": "Pwllheli",
                "country_code": "GB",
                "postal_code": "LL536NH",
                "person_name": "Sender",
            },
            "recipient": {
                "address_line1": "10 Rue de Rivoli",
                "city": "Paris",
                "country_code": "FR",
                "postal_code": "75001",
                "person_name": "Recipient",
            },
            "parcels": [
                {
                    "weight": 50,
                    "weight_unit": "G",
                    "length": 35.3,
                    "width": 25,
                    "height": 2.5,
                    "dimension_unit": "CM",
                    "packaging_type": "largeLetter",
                    "package_preset": "royalmail_large_letter",
                }
            ],
            "customs": {
                "content_type": "merchandise",
                "incoterm": "DDP",
                "commodities": [
                    {
                        "description": "test item",
                        "quantity": 1,
                        "value_amount": 30,
                        "value_currency": "GBP",
                        "weight": 50,
                        "weight_unit": "G",
                    }
                ],
            },
            "services": ["royal_mail_international_tracked_large_letter"],
            "options": {
                "currency": "GBP",
                "duty_paid": True,
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "ddp_service_required"
                for message in messages
            ),
            messages,
        )

    def test_options_dtp_filters_non_ddp_rating_services(self):
        payload = {
            "shipper": {
                "address_line1": "Carnguwch",
                "city": "Pwllheli",
                "country_code": "GB",
                "postal_code": "LL536NH",
                "person_name": "Sender",
            },
            "recipient": {
                "address_line1": "10 Rue de Rivoli",
                "city": "Paris",
                "country_code": "FR",
                "postal_code": "75001",
                "person_name": "Recipient",
            },
            "parcels": [
                {
                    "weight": 50,
                    "weight_unit": "G",
                    "length": 35.3,
                    "width": 25,
                    "height": 2.5,
                    "dimension_unit": "CM",
                    "packaging_type": "largeLetter",
                    "package_preset": "royalmail_large_letter",
                }
            ],
            "services": ["royal_mail_international_tracked_large_letter"],
            "options": {
                "currency": "GBP",
                "incoterm": "DTP",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "ddp_service_required"
                for message in messages
            ),
            messages,
        )


class TestRoyalMailDutyPaidFiltering(unittest.TestCase):
    def test_customs_invoice_only_is_not_duty_paid(self):
        """
        Karrio core defaults models.Duty.paid_by to 'sender'.

        A customs object with invoice metadata only must not become DDP simply
        because the default Duty object says paid_by='sender'.
        """
        customs = models.Customs(
            commodities=[],
            content_type="merchandise",
            invoice="INV-CUSTOMS-1001",
            invoice_date="2024-01-03T10:00:00Z",
        )

        self.assertFalse(
            provider_units.is_duty_paid_requested(
                customs=customs,
                options={},
            )
        )

    def test_dap_overrides_customs_duty_costs(self):
        """
        DAP means recipient/importer pays duties.

        If a caller passes customsDutyCosts together with DAP, do not classify
        the shipment as DDP and do not force a DDP-capable service.
        """
        self.assertFalse(
            provider_units.is_duty_paid_requested(
                customs={
                    "content_type": "merchandise",
                    "incoterm": "DAP",
                    "commodities": [],
                },
                options={
                    "customs_duty_costs": 4.0,
                },
            )
        )

    def test_ddp_is_duty_paid(self):
        self.assertTrue(
            provider_units.is_duty_paid_requested(
                customs={
                    "content_type": "merchandise",
                    "incoterm": "DDP",
                    "commodities": [],
                },
                options={},
            )
        )

    def test_dtp_is_duty_paid(self):
        self.assertTrue(
            provider_units.is_duty_paid_requested(
                customs={
                    "content_type": "merchandise",
                    "incoterm": "DTP",
                    "commodities": [],
                },
                options={},
            )
        )

    def test_dtp_feature_is_duty_paid(self):
        self.assertTrue(
            provider_units.is_duty_paid_requested(
                customs=None,
                options={
                    "features": ["dtp"],
                },
            )
        )

    def test_dap_feature_is_not_duty_paid(self):
        self.assertFalse(
            provider_units.is_duty_paid_requested(
                customs=None,
                options={
                    "features": ["dap"],
                },
            )
        )

    def test_dtp_named_service_supports_ddp_filtering(self):
        """
        Some Parcelforce DTP services may be inactive/no-price in services.csv,
        but direct shipment validation should still recognize the duty-paid
        service intent from the service_code/name.
        """
        self.assertTrue(
            provider_units.service_supports_ddp(
                "parcel_force_europriority_dtp_ioss_insured_150"
            )
        )

    def test_normal_tracked_24_is_not_ddp_capable(self):
        self.assertFalse(
            provider_units.service_supports_ddp("royal_mail_tracked_24")
        )


    def test_customs_ddp_with_sender_paid_duty_filters_non_ddp_rating_services(self):
        payload = {
            "shipper": {
                "address_line1": "Carnguwch",
                "city": "Pwllheli",
                "country_code": "GB",
                "postal_code": "LL536NH",
                "person_name": "Sender",
            },
            "recipient": {
                "address_line1": "10 Rue de Rivoli",
                "city": "Paris",
                "country_code": "FR",
                "postal_code": "75001",
                "person_name": "Recipient",
            },
            "parcels": [
                {
                    "weight": 50,
                    "weight_unit": "G",
                    "length": 35.3,
                    "width": 25,
                    "height": 2.5,
                    "dimension_unit": "CM",
                    "packaging_type": "largeLetter",
                    "package_preset": "royalmail_large_letter",
                }
            ],
            "customs": {
                "content_type": "merchandise",
                "incoterm": "DDP",
                "duty": {
                    "currency": "GBP",
                    "declared_value": 30,
                    "paid_by": "sender",
                },
                "commodities": [
                    {
                        "description": "test item",
                        "quantity": 1,
                        "value_amount": 30,
                        "value_currency": "GBP",
                        "weight": 50,
                        "weight_unit": "G",
                    }
                ],
            },
            "services": ["royal_mail_international_tracked_large_letter"],
            "options": {
                "currency": "GBP",
            },
        }

        response = (
            karrio.Rating.fetch(models.RateRequest(**payload))
            .from_(gateway)
            .parse()
        )

        rates, messages = lib.to_dict(response)

        self.assertEqual(rates, [])
        self.assertTrue(
            any(
                message["code"] == "ddp_service_required"
                for message in messages
            ),
            messages,
        )

if __name__ == "__main__":
    unittest.main()