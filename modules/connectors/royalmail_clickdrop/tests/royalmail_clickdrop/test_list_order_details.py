 
"""Royal Mail Click and Drop carrier list order details helper tests."""

import unittest
from unittest.mock import patch, ANY

import karrio.lib as lib

from . import fixture


class TestRoyalMailClickandDropListOrderDetails(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ListOrderDetailsRequest = fixture.ListOrderDetailsPayload

    def test_create_list_order_details_request(self):
        """Serialize list-order-details filters into the Royal Mail paging/query payload."""
        request = fixture.gateway.mapper.create_list_order_details_request(
            self.ListOrderDetailsRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.OrdersLookupRequest)

    def test_list_order_details(self):
        """Verify the proxy calls GET /orders/full with the expected query string."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            fixture.gateway.proxy.list_order_details(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/full"
                "?pageSize=2"
                "&startDateTime=2024-01-01T00%3A00%3A00Z"
                "&endDateTime=2024-01-31T23%3A59%3A59Z"
                "&continuationToken=NEXT123",
            )

    def test_parse_list_order_details_response(self):
        """Parse a successful paged detailed-order response into the expected native schema object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ListOrderDetailsResponse

            request = fixture.gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            response = fixture.gateway.proxy.list_order_details(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_list_order_details_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedListOrderDetailsResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail list-order-details errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ListOrderDetailsErrorResponse

            request = fixture.gateway.mapper.create_list_order_details_request(
                self.ListOrderDetailsRequest
            )
            response = fixture.gateway.proxy.list_order_details(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_list_order_details_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedListOrderDetailsErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()
