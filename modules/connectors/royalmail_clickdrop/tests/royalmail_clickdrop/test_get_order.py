 
"""Royal Mail Click and Drop carrier get order helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from . import fixture


class TestRoyalMailClickandDropGetOrder(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetOrderRequest = fixture.GetOrderPayload

    def test_create_get_order_request(self):
        """Serialize an order lookup payload into Royal Mail orderIdentifiers format."""
        request = fixture.gateway.mapper.create_get_order_request(self.GetOrderRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.OrderLookupRequest)

    

    def test_get_order(self):
        """Verify the proxy sends the order lookup request to GET /orders/{orderIdentifiers}."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "[]"

            request = fixture.gateway.mapper.create_get_order_request(self.GetOrderRequest)
            fixture.gateway.proxy.get_order(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678",
            )
    

    def test_parse_get_order_response(self):
        """Parse a successful order lookup response into the expected native order list."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetOrderResponse

            request = fixture.gateway.mapper.create_get_order_request(self.GetOrderRequest)
            response = fixture.gateway.proxy.get_order(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_order_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetOrderResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail order lookup errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetOrderErrorResponse

            request = fixture.gateway.mapper.create_get_order_request(self.GetOrderRequest)
            response = fixture.gateway.proxy.get_order(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_order_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetOrderErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()

