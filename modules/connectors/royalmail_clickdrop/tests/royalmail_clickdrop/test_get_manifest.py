 
 
"""Royal Mail Click and Drop carrier get manifest helper tests."""

import unittest
from unittest.mock import patch, ANY

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropGetManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetManifestRequest = fixture.GetManifestPayload

    def test_create_get_manifest_request(self):
        """Serialize a manifest lookup payload into the Royal Mail manifest identifier format."""
        request = fixture.gateway.mapper.create_get_manifest_request(self.GetManifestRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.ManifestIdentifierRequest)
    

    def test_get_manifest(self):
        """Verify the proxy sends the manifest lookup request to GET /manifests/{manifestIdentifier}."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            fixture.gateway.proxy.get_manifest(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/manifests/1001",
            )
    

    def test_parse_get_manifest_response(self):
        """Parse a successful manifest lookup response into Karrio manifest details."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetManifestResponse

            request = fixture.gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            response = fixture.gateway.proxy.get_manifest(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_manifest_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetManifestResponse,
            )
    

    def test_parse_error_response(self):
        """Normalize Royal Mail manifest lookup errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.GetManifestErrorResponse

            request = fixture.gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            response = fixture.gateway.proxy.get_manifest(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_manifest_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedGetManifestErrorResponse,
            )
    


