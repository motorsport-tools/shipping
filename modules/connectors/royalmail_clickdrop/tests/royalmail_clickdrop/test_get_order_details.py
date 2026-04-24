 
 
"""Royal Mail Click and Drop carrier get order details helper tests."""

import unittest
from unittest.mock import patch, ANY
from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropGetOrderDetails(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetOrderDetailsRequest = fixture.GetOrderDetailsPayload

    def test_create_get_order_details_request(self):
        """Serialize an order-details lookup payload into Royal Mail orderIdentifiers format."""
        request = fixture.gateway.mapper.create_get_order_details_request(
            self.GetOrderDetailsRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.OrderLookupRequest)

    def test_get_order_details(self):
        """Verify the proxy sends the detailed order lookup request to GET /orders/{orderIdentifiers}/full."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "[]"

            request = fixture.gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            fixture.gateway.proxy.get_order_details(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678/full",
            )

    def test_parse_get_order_details_response(self):
        """Parse a successful detailed order lookup response into the expected native order detail list."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetOrderDetailsResponse

            request = fixture.gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            response = fixture.gateway.proxy.get_order_details(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_get_order_details_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetOrderDetailsResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail detailed order lookup errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetOrderDetailsErrorResponse

            request = fixture.gateway.mapper.create_get_order_details_request(
                self.GetOrderDetailsRequest
            )
            response = fixture.gateway.proxy.get_order_details(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_get_order_details_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetOrderDetailsErrorResponse,
            )

    def test_create_get_order_details_request_with_string_reference(self):
        """Encode string order references as quoted Royal Mail orderIdentifiers for /full lookup."""
        request = fixture.gateway.mapper.create_get_order_details_request(
            {"reference": "ORDER-1001"}
        )

        self.assertEqual(
            request.serialize(),
            {"orderIdentifiers": "%22ORDER-1001%22"},
        )

    def test_create_get_order_details_request_with_numeric_reference(self):
        """Encode numeric-looking order references as quoted Royal Mail orderIdentifiers for /full lookup."""
        request = fixture.gateway.mapper.create_get_order_details_request(
            {"reference": "000123"}
        )

        self.assertEqual(
            request.serialize(),
            {"orderIdentifiers": "%22000123%22"},
        )


