"""Royal Mail Click and Drop query parameter boundary tests."""

import unittest
from unittest.mock import patch

from . import fixture


class TestRoyalMailClickandDropQueryBounds(unittest.TestCase):
    def test_create_list_orders_request_accepts_page_size_lower_bound(self):
        """Accept page_size=1 for Royal Mail paged order lookups."""
        request = fixture.gateway.mapper.create_list_orders_request({"page_size": 1})

        self.assertEqual(request.serialize()["pageSize"], 1)

    def test_create_list_orders_request_accepts_page_size_upper_bound(self):
        """Accept page_size=100 for Royal Mail paged order lookups."""
        request = fixture.gateway.mapper.create_list_orders_request({"page_size": 100})

        self.assertEqual(request.serialize()["pageSize"], 100)

    def test_create_list_orders_request_rejects_page_size_zero(self):
        """Reject page sizes below the Royal Mail minimum."""
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            fixture.gateway.mapper.create_list_orders_request({"page_size": 0})

    def test_create_list_orders_request_rejects_page_size_above_100(self):
        """Reject page sizes above the Royal Mail maximum."""
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            fixture.gateway.mapper.create_list_orders_request({"page_size": 101})

    def test_create_list_orders_request_supports_camel_case_aliases(self):
        """Honor the carrier-style camelCase filter names used by the Royal Mail API."""
        request = fixture.gateway.mapper.create_list_orders_request(
            {
                "pageSize": 2,
                "startDateTime": "2024-01-01T00:00:00Z",
                "endDateTime": "2024-01-31T23:59:59Z",
                "continuationToken": "NEXT123",
            }
        )

        self.assertEqual(request.serialize(), fixture.OrdersLookupRequest)

    def test_list_orders_omits_query_string_for_empty_payload(self):
        """Do not append an empty query string when no filters are supplied."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_list_orders_request({})
            fixture.gateway.proxy.list_orders(request)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders",
            )

    def test_list_order_details_supports_continuation_token_only(self):
        """Allow continuation-token pagination without other filters."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_list_order_details_request(
                {"continuation_token": "NEXT123"}
            )
            fixture.gateway.proxy.list_order_details(request)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/full?continuationToken=NEXT123",
            )
