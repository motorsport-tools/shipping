"""Royal Mail Click and Drop carrier manifest tests."""

import unittest
from unittest.mock import patch, ANY
from .fixture import gateway
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ManifestRequest = models.ManifestRequest(**ManifestPayload)

    def test_create_manifest_request(self):
        request = gateway.mapper.create_manifest_request(self.ManifestRequest)
        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), ManifestRequest)

    def test_create_manifest(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Manifest.create(self.ManifestRequest).from_(gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/manifests",
            )

    def test_parse_manifest_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ManifestResponse

            parsed_response = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), ParsedManifestResponse)

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ErrorResponse

            parsed_response = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), ParsedErrorResponse)


if __name__ == "__main__":
    unittest.main()


ManifestPayload = {
    "shipment_identifiers": ["12345678", "12345679"],
    "address": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
    },
    "options": {
        "carrier_name": "Royal Mail OBA",
    },
}

ManifestRequest = {
    "carrierName": "Royal Mail OBA",
}

ManifestResponse = """{
  "manifestNumber": 1001,
  "documentPdf": "JVBERi0xLjQKJcfs..."
}"""

ErrorResponse = """{
  "errors": [
    {
      "code": "Forbidden",
      "description": "Feature not available"
    }
  ]
}"""

ParsedManifestResponse = [
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
            "message": "Feature not available",
            "details": {
                "operation": "manifest",
            },
        }
    ],
]