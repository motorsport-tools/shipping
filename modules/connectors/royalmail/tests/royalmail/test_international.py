"""Royal Mail Click and Drop international rating and customs tests."""

import copy
import logging
import unittest
from unittest.mock import ANY, patch

from .fixture import gateway

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropInternationalRating(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RateRequest = models.RateRequest(
            **copy.deepcopy(InternationalLargeLetterRatePayloads["FR"])
        )

    def test_create_rate_request(self):
        request = gateway.mapper.create_rate_request(self.RateRequest)

        self.assertEqual(
            lib.to_dict(request.serialize()),
            lib.to_dict(self.RateRequest),
        )

    def test_get_rates(self):
        for country_code, expected in ExpectedLargeLetterRates.items():
            with self.subTest(country_code=country_code):
                payload = copy.deepcopy(InternationalLargeLetterRatePayloads[country_code])
                response = (
                    karrio.Rating.fetch(models.RateRequest(**payload))
                    .from_(gateway)
                    .parse()
                )
                rates, messages = lib.to_dict(response)

                self.assertEqual(messages, [], messages)

                rate = next(
                    (
                        item
                        for item in rates
                        if item["service"] == INTERNATIONAL_LARGE_LETTER_SERVICE
                    ),
                    None,
                )

                self.assertIsNotNone(
                    rate,
                    (
                        f"Expected {INTERNATIONAL_LARGE_LETTER_SERVICE} for {country_code}. "
                        f"rates={rates!r} messages={messages!r}"
                    ),
                )
                self.assertEqual(rate["carrier_id"], "royalmail")
                self.assertEqual(rate["carrier_name"], "royalmail")
                self.assertEqual(rate["currency"], "GBP")
                self.assertEqual(rate["total_charge"], expected["total_charge"])
                self.assertEqual(rate["transit_days"], expected["transit_days"])
                self.assertEqual(
                    rate["meta"]["carrier_service_code"],
                    "OTA",
                )
                self.assertEqual(
                    rate["meta"]["service_name"],
                    "International Tracked Large Letter",
                )

    def test_parse_rate_response(self):
        internal_response = [
            (
                "1",
                (
                    [
                        models.RateDetails(
                            carrier_id="royalmail",
                            carrier_name="royalmail",
                            service=INTERNATIONAL_LARGE_LETTER_SERVICE,
                            currency="GBP",
                            total_charge=9.80,
                            transit_days=7,
                            meta={
                                "service_name": "International Tracked Large Letter",
                                "carrier_service_code": "OTA",
                                "shipping_charges": 9.80,
                                "shipping_currency": "GBP",
                            },
                        )
                    ],
                    [],
                ),
            )
        ]

        parsed_response = gateway.mapper.parse_rate_response(
            lib.Deserializable(internal_response, lambda value: value)
        )

        self.assertListEqual(
            lib.to_dict(parsed_response),
            ParsedInternationalRateResponse,
        )

    def test_parse_error_response(self):
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

        parsed_response = gateway.mapper.parse_rate_response(
            lib.Deserializable(internal_response, lambda value: value)
        )


        self.assertListEqual(
            lib.to_dict(parsed_response),
            lib.to_dict(([], [message])),
        )


class TestRoyalMailClickandDropInternationalShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentRequest = models.ShipmentRequest(
            **copy.deepcopy(InternationalShipmentPayloads["FR"])
        )
    def test_create_shipment_request(self):
        for country_code in InternationalShipmentPayloads:
            with self.subTest(country_code=country_code):
                payload = copy.deepcopy(InternationalShipmentPayloads[country_code])
                request = gateway.mapper.create_shipment_request(
                    models.ShipmentRequest(**payload)
                )
                serialized = lib.to_dict(request.serialize())

                item = serialized["items"][0]
                package = item["packages"][0]
                content = package["contents"][0]

                self.assertEqual(
                    item["recipient"]["address"]["countryCode"],
                    country_code,
                )
                self.assertEqual(
                    item["recipient"]["address"]["postcode"],
                    InternationalRecipients[country_code]["postal_code"],
                )

                self.assertEqual(item["currencyCode"], "GBP")
                self.assertEqual(item["subtotal"], 30.0)
                self.assertEqual(item["shippingCostCharged"], 0.0)

                # Standard OTA international shipment uses DAP in this fixture.
                # Duty is paid by the recipient, so Click & Drop should not receive
                # customsDutyCosts for this order.
                self.assertNotIn("customsDutyCosts", item)
                self.assertEqual(item["total"], 30.0)

                self.assertTrue(item["label"]["includeCN"])
                self.assertEqual(
                    item["postageDetails"]["serviceCode"],
                    "OTA",
                )
                self.assertEqual(
                    item["postageDetails"]["serviceRegisterCode"],
                    "01",
                )
                self.assertEqual(
                    item["postageDetails"]["commercialInvoiceNumber"],
                    "INV-INTL-001",
                )
                self.assertEqual(
                    item["postageDetails"]["commercialInvoiceDate"],
                    "2026-05-15",
                )

                self.assertEqual(package["weightInGrams"], 50)
                self.assertEqual(package["packageFormatIdentifier"], "smallParcel")

                self.assertEqual(content["SKU"], "00003")
                self.assertEqual(content["name"], "ipod")
                self.assertEqual(content["quantity"], 1)
                self.assertEqual(content["unitValue"], 30.0)
                self.assertEqual(content["unitWeightInGrams"], 50)
                self.assertEqual(content["customsDescription"], "test item")
                self.assertEqual(content["extendedCustomsDescription"], "test item")
                self.assertEqual(content["customsCode"], "87654321")
                self.assertEqual(content["originCountryCode"], "CN")
                self.assertEqual(content["customsDeclarationCategory"], "saleOfGoods")

    def test_create_shipment(self):
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = "{}"

            response = karrio.Shipment.create(self.ShipmentRequest).from_(gateway)

            if mock.call_args is None:
                self.fail(
                    "Royal Mail shipment request was not sent. "
                    f"SDK response: {lib.to_dict(response)}"
                )

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders",
            )
            self.assertEqual(mock.call_args[1]["method"], "POST")

    def test_parse_shipment_response(self):
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = InternationalShipmentResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedInternationalShipmentResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = InternationalShipmentErrorResponse

            parsed_response = (
                karrio.Shipment.create(self.ShipmentRequest)
                .from_(gateway)
                .parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedInternationalShipmentErrorResponse,
            )

    def test_create_shipment_request_with_raw_ota_service_code(self):
        payload = copy.deepcopy(InternationalShipmentPayloads["FR"])
        payload["service"] = "OTA"

        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        item = serialized["items"][0]
        package = item["packages"][0]
        content = package["contents"][0]

        self.assertEqual(item["recipient"]["address"]["countryCode"], "FR")
        self.assertEqual(item["postageDetails"]["serviceCode"], "OTA")
        self.assertEqual(item["postageDetails"]["serviceRegisterCode"], "01")

        self.assertTrue(item["label"]["includeCN"])
        self.assertEqual(package["packageFormatIdentifier"], "smallParcel")

        self.assertEqual(content["customsCode"], "87654321")
        self.assertEqual(content["originCountryCode"], "CN")
        self.assertEqual(content["customsDeclarationCategory"], "saleOfGoods")

        # Raw OTA is still the standard non-DDP International Tracked service.
        # Because this fixture uses DAP, customsDutyCosts should not be serialized.
        self.assertNotIn("customsDutyCosts", item)


    def test_create_ddp_shipment_request_includes_customs_duty_costs(self):
        payload = copy.deepcopy(InternationalShipmentPayloads["FR"])
        payload["service"] = "royal_mail_international_business_parcel_tracked_ddp"
        payload["customs"] = copy.deepcopy(InternationalCustoms)
        payload["customs"]["incoterm"] = "DDP"
        payload["customs"]["duty"]["paid_by"] = "sender"

        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )

        serialized = lib.to_dict(request.serialize())

        item = serialized["items"][0]

        self.assertEqual(item["postageDetails"]["serviceCode"], "MPR")
        self.assertEqual(item["postageDetails"]["serviceRegisterCode"], "01")
        self.assertEqual(item["customsDutyCosts"], 30.0)
        self.assertEqual(item["subtotal"], 30.0)
        self.assertEqual(item["shippingCostCharged"], 0.0)
        self.assertEqual(item["total"], 60.0)

if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Shared international fixture data
# ---------------------------------------------------------------------------

GBShipper = {
    "address_line1": "Carnguwch",
    "address_line2": "Llithfaen",
    "city": "Pwllheli",
    "company_name": "Motorsport Tools Ltd",
    "country_code": "GB",
    "email": "richard.simcox@motorsport-tools.com",
    "person_name": "Sales Team",
    "phone_number": "01758750000",
    "postal_code": "LL536NH",
}

InternationalRecipients = {
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
}

InternationalCommodity = {
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

InternationalCustoms = {
    "certify": True,
    "commercial_invoice": True,
    "commodities": [InternationalCommodity],
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
    "options": {},
    "signer": "Sales Team",
}

InternationalLargeLetterParcel = {
    "dimension_unit": "CM",
    "height": 2.5,
    "is_document": False,
    "items": [InternationalCommodity],
    "length": 35.3,
    "package_preset": "royalmail_large_letter",
    "packaging_type": "largeLetter",
    "weight": 50,
    "weight_unit": "G",
    "width": 25,
}

InternationalSmallParcel = {
    "dimension_unit": "CM",
    "height": 8,
    "is_document": False,
    "items": [InternationalCommodity],
    "length": 20,
    "package_preset": "royalmail_small_parcel",
    "packaging_type": "smallParcel",
    "weight": 50,
    "weight_unit": "G",
    "width": 15,
}

INTERNATIONAL_LARGE_LETTER_SERVICE = "royal_mail_international_tracked_large_letter"
INTERNATIONAL_SMALL_PARCEL_SERVICE = "royal_mail_international_tracked_small_parcel"

ExpectedLargeLetterRates = {
    "FR": {"total_charge": 10.98, "transit_days": 7},
    "DE": {"total_charge": 10.98, "transit_days": 7},
    "US": {"total_charge": 12.21, "transit_days": 7},
    "AU": {"total_charge": 12.66, "transit_days": 7},
}


def international_rate_payload(country_code: str) -> dict:
    return {
        "shipper": copy.deepcopy(GBShipper),
        "recipient": copy.deepcopy(InternationalRecipients[country_code]),
        "parcels": [copy.deepcopy(InternationalLargeLetterParcel)],
        "customs": copy.deepcopy(InternationalCustoms),
        "payment": {"paid_by": "sender"},
        "reference": f"RATE-INTL-{country_code}",
        "services": [INTERNATIONAL_LARGE_LETTER_SERVICE],
        "options": {
            "currency": "GBP",
            "shipping_date": "2026-05-15T13:34:00Z",
        },
    }


def international_shipment_payload(country_code: str) -> dict:
    return {
        "shipper": copy.deepcopy(GBShipper),
        "recipient": copy.deepcopy(InternationalRecipients[country_code]),
        "parcels": [copy.deepcopy(InternationalSmallParcel)],
        "customs": copy.deepcopy(InternationalCustoms),
        "label_type": "PDF",
        "payment": {"paid_by": "sender"},
        "reference": f"ORDER-INTL-{country_code}",
        "service": INTERNATIONAL_SMALL_PARCEL_SERVICE,
        "options": {
            "currency": "GBP",
            "shipping_date": "2026-05-15T13:34:00Z",
            "order_date": "2026-05-15T13:34:00Z",
            "order_reference": f"ORDER-INTL-{country_code}",
            "package_format_identifier": "smallParcel",
            "include_label_in_response": True,
        },
    }


InternationalLargeLetterRatePayloads = {
    country_code: international_rate_payload(country_code)
    for country_code in InternationalRecipients
}

InternationalShipmentPayloads = {
    country_code: international_shipment_payload(country_code)
    for country_code in InternationalRecipients
}

ParsedInternationalRateResponse = [
    [
        {
            "carrier_id": "royalmail",
            "carrier_name": "royalmail",
            "service": INTERNATIONAL_LARGE_LETTER_SERVICE,
            "currency": "GBP",
            "total_charge": 9.80,
            "transit_days": 7,
            "meta": {
                "service_name": "International Tracked Large Letter",
                "carrier_service_code": "OTA",
                "shipping_charges": 9.80,
                "shipping_currency": "GBP",
            },
        }
    ],
    [],
]

InternationalRateErrorResponse = {
    "rates": [],
    "messages": [
        {
            "code": "rate_table_error",
            "message": "No matching rate table entry found",
        }
    ],
}

ParsedInternationalRateErrorResponse = [
    [],
    [
        {
            "code": "rate_table_error",
            "message": "No matching rate table entry found",
        }
    ],
]

InternationalShipmentResponse = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 987654321,
            "orderReference": "ORDER-INTL-FR",
            "createdOn": "2026-05-15T13:34:00Z",
            "orderDate": "2026-05-15T13:34:00Z",
            "printedOn": "2026-05-15T13:35:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": "RN123456785GB",
            "packages": [
                {
                    "packageNumber": 1,
                    "trackingNumber": "RN123456785GB",
                }
            ],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ParsedInternationalShipmentResponse = [
    {
        "carrier_id": "royalmail",
        "carrier_name": "royalmail",
        "tracking_number": "RN123456785GB",
        "shipment_identifier": "987654321",
        "label_type": "PDF",
        "docs": ANY,
        "meta": {
            "order_identifier": 987654321,
            "order_reference": "ORDER-INTL-FR",
            "created_on": "2026-05-15T13:34:00Z",
            "order_date": "2026-05-15T13:34:00Z",
            "printed_on": "2026-05-15T13:35:00Z",
            "tracking_numbers": ["RN123456785GB"],
            "package_tracking_numbers": ["RN123456785GB"],
            "generated_documents": ["label"],
            "tracking_number_provided": True,
            "tracking_options": {
                "order_references": {
                    "RN123456785GB": "ORDER-INTL-FR",
                },
                "order_reference": "ORDER-INTL-FR",
            },
            "tracking_lookup": {
                "tracking_number": "RN123456785GB",
                "tracking_numbers": ["RN123456785GB"],
                "order_reference": "ORDER-INTL-FR",
            },
        },
    },
    [],
]

InternationalShipmentErrorResponse = {
    "code": "BadRequest",
    "message": "The request is invalid",
    "details": "One or more validation errors occurred",
}

ParsedInternationalShipmentErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail",
            "carrier_name": "royalmail",
            "code": "BadRequest",
            "message": "The request is invalid",
            "details": {
                "operation": "create_shipment",
                "details": "One or more validation errors occurred",
            },
        }
    ],
]

