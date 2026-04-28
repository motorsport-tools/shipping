"""Royal Mail Click and Drop identifier formatting edge-case tests."""

import unittest
from unittest.mock import patch

import karrio.providers.royalmail_clickdrop.utils as provider_utils

from . import fixture


class TestRoyalMailClickandDropIdentifierEdges(unittest.TestCase):
    def test_make_order_identifiers_with_multiple_numeric_identifiers(self):
        """Join multiple numeric order identifiers with semicolons without quoting them."""
        serialized = provider_utils.make_order_identifiers([12345678, "87654321"])

        self.assertEqual(serialized, "12345678;87654321")

    def test_make_order_identifiers_with_mixed_identifier_types(self):
        """Keep numeric ids raw while quoting non-numeric order references."""
        serialized = provider_utils.make_order_identifiers([12345678, "ORDER-1001"])

        self.assertEqual(serialized, "12345678;%22ORDER-1001%22")

    def test_make_order_identifiers_treats_explicit_numeric_reference_as_reference(self):
        """Quote digit-only references when the caller explicitly identifies them as references."""
        serialized = provider_utils.make_order_identifiers(
            ["000123"],
            treat_numeric_as_reference=True,
        )

        self.assertEqual(serialized, "%22000123%22")

    def test_make_order_identifiers_supports_exactly_100_entries(self):
        """Allow Royal Mail's documented maximum of 100 order identifiers."""
        identifiers = list(range(10000000, 10000100))

        serialized = provider_utils.make_order_identifiers(identifiers)

        self.assertEqual(len(serialized.split(";")), 100)

    def test_make_order_identifiers_rejects_more_than_100_entries(self):
        """Reject order identifier lists above the Royal Mail API maximum."""
        with self.assertRaisesRegex(ValueError, "maximum of 100 order identifiers"):
            provider_utils.make_order_identifiers(list(range(101)))

    def test_create_get_order_request_with_multiple_identifiers(self):
        """Serialize mixed order identifiers for GET /orders/{orderIdentifiers}."""
        request = fixture.gateway.mapper.create_get_order_request(
            {"order_identifiers": [12345678, "ORDER-1001"]}
        )

        self.assertEqual(
            request.serialize(),
            {"orderIdentifiers": "12345678;%22ORDER-1001%22"},
        )

    def test_create_get_order_details_request_with_multiple_identifiers(self):
        """Serialize mixed order identifiers for GET /orders/{orderIdentifiers}/full."""
        request = fixture.gateway.mapper.create_get_order_details_request(
            {"order_identifiers": [12345678, "ORDER-1001"]}
        )

        self.assertEqual(
            request.serialize(),
            {"orderIdentifiers": "12345678;%22ORDER-1001%22"},
        )

    def test_create_label_request_with_multiple_identifiers(self):
        """Serialize mixed order identifiers for GET /orders/{orderIdentifiers}/label."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "order_identifiers": [12345678, "ORDER-1001"],
                "document_type": "postageLabel",
            }
        )

        self.assertEqual(
            request.serialize()["orderIdentifiers"],
            "12345678;%22ORDER-1001%22",
        )

    def test_get_order_proxy_uses_semicolon_delimited_identifier_path(self):
        """Send the pre-encoded semicolon-delimited identifier list directly in the request path."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "[]"

            request = fixture.gateway.mapper.create_get_order_request(
                {"order_identifiers": [12345678, "ORDER-1001"]}
            )
            fixture.gateway.proxy.get_order(request)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678;%22ORDER-1001%22",
            )
