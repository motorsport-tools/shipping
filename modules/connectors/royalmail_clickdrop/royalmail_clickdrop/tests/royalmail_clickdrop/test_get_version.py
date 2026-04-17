"""Royal Mail Click and Drop carrier version helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropVersion(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.VersionRequest = {}

    def test_create_get_version_request(self):
        request = gateway.mapper.create_get_version_request(self.VersionRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), VersionRequest)

    def test_get_version(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_get_version_request(self.VersionRequest)
            gateway.proxy.get_version(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/version",
            )

    def test_parse_get_version_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = VersionResponse

            request = gateway.mapper.create_get_version_request(self.VersionRequest)
            response = gateway.proxy.get_version(request)
            parsed_response = list(gateway.mapper.parse_get_version_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedVersionResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = VersionErrorResponse

            request = gateway.mapper.create_get_version_request(self.VersionRequest)
            response = gateway.proxy.get_version(request)
            parsed_response = list(gateway.mapper.parse_get_version_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


VersionRequest = {}

VersionResponse = """{
  "commit": "abcdef1234567890",
  "build": "100",
  "release": "1.0.0",
  "releaseDate": "2024-01-01T00:00:00Z"
}"""

VersionErrorResponse = """{
  "code": "Forbidden",
  "message": "Not authorised to view version information"
}"""

ParsedVersionResponse = [
    {
        "commit": "abcdef1234567890",
        "build": "100",
        "release": "1.0.0",
        "releaseDate": "2024-01-01T00:00:00Z",
    },
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Not authorised to view version information",
            "details": {
                "operation": "get_version",
            },
        }
    ],
]