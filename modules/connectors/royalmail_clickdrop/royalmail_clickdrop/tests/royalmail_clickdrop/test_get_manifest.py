"""Royal Mail Click and Drop carrier get manifest helper tests."""

import unittest
from unittest.mock import patch, ANY

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropGetManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.GetManifestRequest = GetManifestPayload

    def test_create_get_manifest_request(self):
        request = gateway.mapper.create_get_manifest_request(self.GetManifestRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), ManifestIdentifierRequest)

    def test_get_manifest(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            gateway.proxy.get_manifest(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/manifests/1001",
            )

    def test_parse_get_manifest_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetManifestResponse

            request = gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            response = gateway.proxy.get_manifest(request)
            parsed_response = list(gateway.mapper.parse_get_manifest_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedGetManifestResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = GetManifestErrorResponse

            request = gateway.mapper.create_get_manifest_request(self.GetManifestRequest)
            response = gateway.proxy.get_manifest(request)
            parsed_response = list(gateway.mapper.parse_get_manifest_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


GetManifestPayload = {
    "manifest_number": 1001,
}

ManifestIdentifierRequest = {
    "manifestIdentifier": 1001,
}

GetManifestResponse = """{
  "manifestNumber": 1001,
  "status": "Completed",
  "documentPdf": "JVBERi0xLjQKJcfs..."
}"""

GetManifestErrorResponse = """{
  "errors": [
    {
      "code": "Forbidden",
      "description": "Manifest not found"
    }
  ]
}"""

ParsedGetManifestResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "doc": ANY,
        "meta": {
            "manifest_number": 1001,
            "status": "completed",
            "document_available": True,
        },
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
            "message": "Manifest not found",
            "details": {
                "operation": "manifest",
            },
        }
    ],
]