"""Royal Mail Click and Drop carrier retry manifest helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropRetryManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.RetryManifestRequest = RetryManifestPayload

    def test_create_retry_manifest_request(self):
        request = gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), ManifestIdentifierRequest)

    def test_retry_manifest(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            gateway.proxy.retry_manifest(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/manifests/retry/1002",
            )

    def test_parse_retry_manifest_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = RetryManifestResponse

            request = gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            response = gateway.proxy.retry_manifest(request)
            parsed_response = list(gateway.mapper.parse_retry_manifest_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedRetryManifestResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = RetryManifestErrorResponse

            request = gateway.mapper.create_retry_manifest_request(self.RetryManifestRequest)
            response = gateway.proxy.retry_manifest(request)
            parsed_response = list(gateway.mapper.parse_retry_manifest_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


RetryManifestPayload = {
    "manifest_number": 1002,
}

ManifestIdentifierRequest = {
    "manifestIdentifier": 1002,
}

RetryManifestResponse = """{
  "manifestNumber": 1002
}"""

RetryManifestErrorResponse = """{
  "errors": [
    {
      "code": "BadRequest",
      "description": "Manifest cannot be retried"
    }
  ]
}"""

ParsedRetryManifestResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "meta": {
            "manifest_number": 1002,
            "status": "in_progress",
            "document_available": False,
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
            "code": "BadRequest",
            "message": "Manifest cannot be retried",
            "details": {
                "operation": "manifest",
            },
        }
    ],
]