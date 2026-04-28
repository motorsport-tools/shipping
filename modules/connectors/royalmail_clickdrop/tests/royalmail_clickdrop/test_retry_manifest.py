 
 
 
"""Royal Mail Click and Drop carrier retry manifest helper tests."""

import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropRetryManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RetryManifestRequest = fixture.RetryManifestPayload

    def test_create_retry_manifest_request(self):
        """Serialize a manifest retry payload into the Royal Mail manifest identifier format."""
        request = fixture.gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.RetryManifestIdentifierRequest)

    def test_retry_manifest(self):
        """Verify the proxy sends the retry request to POST /manifests/retry/{manifestIdentifier}."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            fixture.gateway.proxy.retry_manifest(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/manifests/retry/1002",
            )

    def test_parse_retry_manifest_response(self):
        """Parse a successful retry response into an in-progress Karrio manifest record."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.RetryManifestResponse

            request = fixture.gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            response = fixture.gateway.proxy.retry_manifest(request)
            parsed_response = list(fixture.gateway.mapper.parse_retry_manifest_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedRetryManifestResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail manifest retry errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.RetryManifestErrorResponse

            request = fixture.gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            response = fixture.gateway.proxy.retry_manifest(request)
            parsed_response = list(fixture.gateway.mapper.parse_retry_manifest_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedRetryManifestErrorResponse,
            )


