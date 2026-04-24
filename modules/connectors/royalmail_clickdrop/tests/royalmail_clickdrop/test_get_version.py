 
 
"""Royal Mail Click and Drop carrier version helper tests."""

import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)

class TestRoyalMailClickandDropVersion(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.VersionRequest = fixture.VersionRequest

    def test_create_get_version_request(self):
        """Build the empty request payload required by the version endpoint."""
        request = fixture.gateway.mapper.create_get_version_request(self.VersionRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.VersionRequest)

    def test_get_version(self):
        """Verify the proxy calls GET /version."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_get_version_request(self.VersionRequest)
            fixture.gateway.proxy.get_version(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/version",
            )

    def test_parse_get_version_response(self):
        """Parse a successful version response into the expected native schema object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.VersionResponse

            request = fixture.gateway.mapper.create_get_version_request(self.VersionRequest)
            response = fixture.gateway.proxy.get_version(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_version_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedVersionResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail version endpoint errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.VersionErrorResponse

            request = fixture.gateway.mapper.create_get_version_request(self.VersionRequest)
            response = fixture.gateway.proxy.get_version(request)
            parsed_response = list(fixture.gateway.mapper.parse_get_version_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedVersionErrorResponse,
            )

