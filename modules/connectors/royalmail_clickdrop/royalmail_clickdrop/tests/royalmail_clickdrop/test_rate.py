"""Royal Mail Click and Drop carrier rating tests."""

import unittest

from .fixture import gateway
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models


class TestRoyalMailClickandDropRating(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RateRequest = models.RateRequest(**RatePayload)

    def test_create_rate_request(self):
        request = gateway.mapper.create_rate_request(self.RateRequest)
        expected = lib.to_dict(self.RateRequest)

        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), expected)

    def test_get_rates(self):
        response = karrio.Rating.fetch(self.RateRequest).from_(gateway).parse()
        rates, messages = lib.to_dict(response)

        print(f"Local rating response count: {len(rates)}")
        self.assertGreater(len(rates), 0)
        self.assertEqual(messages, [])

    def test_parse_rate_response(self):
        parsed_response = gateway.mapper.parse_rate_response(
            lib.Deserializable(RateResponse, lambda x: x)
        )

        print(f"Parsed response: {lib.to_dict(parsed_response)}")
        self.assertListEqual(lib.to_dict(parsed_response), ParsedRateResponse)

    def test_parse_error_response(self):
        parsed_response = gateway.mapper.parse_rate_response(
            lib.Deserializable(ErrorResponse, lambda x: x)
        )

        print(f"Error response: {lib.to_dict(parsed_response)}")
        self.assertListEqual(lib.to_dict(parsed_response), ParsedErrorResponse)


if __name__ == "__main__":
    unittest.main()


RatePayload = {
    "shipper": {
        "postal_code": "SW1A1AA",
        "city": "London",
        "country_code": "GB",
        "address_line1": "123 Test Street",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
    },
    "recipient": {
        "postal_code": "BT11AA",
        "city": "Belfast",
        "country_code": "GB",
        "address_line1": "3 Import Road",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
    },
    "parcels": [
        {
            "weight": 0.5,
            "weight_unit": "KG",
            "length": 25,
            "width": 18,
            "height": 5,
            "dimension_unit": "CM",
            "packaging_type": "small_box",
        }
    ],
    "options": {
        "currency": "GBP",
    },
}

RateResponse = {
    "rates": [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "service": "tpn24_01",
            "currency": "GBP",
            "total_charge": 8.5,
            "transit_days": 1,
            "meta": {
                "service_name": "Royal Mail Tracked 24 (01 / 214708C1)",
                "rate_provider": "rate_table",
            },
        }
    ],
    "messages": [],
}

ErrorResponse = {
    "rates": [],
    "messages": [
        {
            "code": "rate_table_error",
            "message": "No matching rate table entry found",
        }
    ],
}

ParsedRateResponse = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "service": "tpn24_01",
            "currency": "GBP",
            "total_charge": 8.5,
            "transit_days": 1,
            "meta": {
                "service_name": "Royal Mail Tracked 24 (01 / 214708C1)",
                "rate_provider": "rate_table",
            },
        }
    ],
    [],
]

ParsedErrorResponse = [
    [],
    [
        {
            "code": "rate_table_error",
            "message": "No matching rate table entry found",
        }
    ],
]