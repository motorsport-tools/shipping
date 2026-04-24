 
 
"""Royal Mail Click and Drop carrier rating tests."""

import unittest

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropRating(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RateRequest = models.RateRequest(**fixture.RatePayload)

    def test_create_rate_request(self):
        """Keep rate request serialization aligned with the universal Karrio rating payload."""
        request = fixture.gateway.mapper.create_rate_request(self.RateRequest)
        expected = lib.to_dict(self.RateRequest)

        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), expected)

    def test_get_rates(self):
        """Verify local rate-table lookup returns at least one rate and no messages for a valid shipment."""
        response = karrio.Rating.fetch(self.RateRequest).from_(fixture.gateway).parse()
        rates, messages = lib.to_dict(response)

        print(f"Local rating response count: {len(rates)}")
        self.assertGreater(len(rates), 0)
        self.assertEqual(messages, [])

    def test_parse_rate_response(self):
        """Parse the local Royal Mail rate response into Karrio rate details."""
        parsed_response = fixture.gateway.mapper.parse_rate_response(
            lib.Deserializable(fixture.RateResponse, lambda x: x)
        )

        print(f"Parsed response: {lib.to_dict(parsed_response)}")
        self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedRateResponse)

    def test_parse_error_response(self):
        """Normalize a no-match rate-table result into Karrio rate messages."""
        parsed_response = fixture.gateway.mapper.parse_rate_response(
            lib.Deserializable(fixture.RateErrorResponse, lambda x: x)
        )

        print(f"Error response: {lib.to_dict(parsed_response)}")
        self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedRateErrorResponse)


