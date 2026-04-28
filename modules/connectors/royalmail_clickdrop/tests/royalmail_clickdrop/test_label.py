 
 
 
"""Royal Mail Click and Drop carrier label retrieval tests."""

import logging
import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropLabel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.LabelRequest = fixture.LabelPayload

    def test_create_label_request(self):
        """Serialize a label lookup request with document flags into Royal Mail query parameters."""
        request = fixture.gateway.mapper.create_label_request(self.LabelRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.LabelRequest)

    def test_get_label(self):
        """Verify the proxy calls GET /orders/{orderIdentifiers}/label with the expected query string."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelResponse

            request = fixture.gateway.mapper.create_label_request(self.LabelRequest)
            fixture.gateway.proxy.get_label(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678/label"
                "?documentType=postageLabel&includeReturnsLabel=false&includeCN=true",
            )

    def test_create_label_request_with_string_reference(self):
        """Encode string references as quoted Royal Mail orderIdentifiers."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "reference": "ORDER-1001",
                "document_type": "postageLabel",
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "%22ORDER-1001%22",
                "query": {
                    "documentType": "postageLabel",
                    "includeReturnsLabel": False,
                    "includeCN": None,
                },
            },
        )

    def test_create_label_request_with_numeric_reference(self):
        """Encode numeric-looking references as quoted Royal Mail orderIdentifiers when supplied via reference."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "reference": "000123",
                "document_type": "postageLabel",
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "%22000123%22",
                "query": {
                    "documentType": "postageLabel",
                    "includeReturnsLabel": False,
                    "includeCN": None,
                },
            },
        )

    def test_parse_label_response(self):
        """Parse a PDF label response into base64-encoded Karrio document fields."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelResponse

            request = fixture.gateway.mapper.create_label_request(self.LabelRequest)
            response = fixture.gateway.proxy.get_label(request)
            parsed_response = list(fixture.gateway.mapper.parse_label_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedLabelResponse,
            )

    def test_parse_error_response(self):
        """Normalize JSON label errors returned through the binary endpoint into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelErrorResponse

            request = fixture.gateway.mapper.create_label_request(self.LabelRequest)
            response = fixture.gateway.proxy.get_label(request)
            parsed_response = list(fixture.gateway.mapper.parse_label_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedLabelErrorResponse,
            )


    def test_create_label_request_without_optional_flags(self):
        """Ensure optional label flags fall back to Royal Mail defaults when not supplied by the caller."""
        request = fixture.gateway.mapper.create_label_request(fixture.LabelPayloadWithoutOptionalFlags)

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "12345678",
                "query": {
                    "documentType": "postageLabel",
                    "includeReturnsLabel": False,
                    "includeCN": None,
                },
            },
        )


    def test_create_label_request_with_returns_label(self):
        """Ensure the request can explicitly ask Royal Mail to include a returns label."""
        request = fixture.gateway.mapper.create_label_request(fixture.LabelPayloadWithReturnsLabel)

        self.assertTrue(request.serialize()["query"]["includeReturnsLabel"])

    def test_parse_label_error_response_bytes(self):
        """Ensure JSON error bytes are decoded and surfaced as label messages instead of PDF content."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelErrorResponseBytes

            request = fixture.gateway.mapper.create_label_request(fixture.LabelPayload)
            response = fixture.gateway.proxy.get_label(request)
            parsed = list(fixture.gateway.mapper.parse_label_response(response))

            self.assertGreater(len(parsed[1]), 0)


    def test_parse_label_nested_error_response(self):
        """Parse nested JSON label errors returned by the binary endpoint into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelNestedErrorResponse

            request = fixture.gateway.mapper.create_label_request(fixture.LabelPayload)
            response = fixture.gateway.proxy.get_label(request)
            parsed = list(fixture.gateway.mapper.parse_label_response(response))

            print(f"Parsed label nested errors: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 1)
            self.assertEqual(parsed[1][0].code, "NotFound")


