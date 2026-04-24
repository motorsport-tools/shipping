 
 
"""Royal Mail Click and Drop carrier list orders helper tests."""

import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropListOrders(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ListOrdersRequest = fixture.ListOrdersPayload

    def test_create_list_orders_request(self):
        """Serialize list-orders filters into the Royal Mail paging/query payload."""
        request = fixture.gateway.mapper.create_list_orders_request(self.ListOrdersRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.OrdersLookupRequest)

    def test_list_orders(self):
        """Verify the proxy calls GET /orders with the expected query string."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            fixture.gateway.proxy.list_orders(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders"
                "?pageSize=2"
                "&startDateTime=2024-01-01T00%3A00%3A00Z"
                "&endDateTime=2024-01-31T23%3A59%3A59Z"
                "&continuationToken=NEXT123",
            )

    def test_parse_list_orders_response(self):
        """Parse a successful paged orders response into the expected native schema object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ListOrdersResponse

            request = fixture.gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            response = fixture.gateway.proxy.list_orders(request)
            parsed_response = list(fixture.gateway.mapper.parse_list_orders_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedListOrdersResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail list-orders errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ListOrdersErrorResponse

            request = fixture.gateway.mapper.create_list_orders_request(self.ListOrdersRequest)
            response = fixture.gateway.proxy.list_orders(request)
            parsed_response = list(fixture.gateway.mapper.parse_list_orders_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedListOrdersErrorResponse,
            )


