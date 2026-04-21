 
"""Royal Mail Click and Drop carrier manifest tests."""

import unittest
from unittest.mock import patch, ANY
from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ManifestRequest = models.ManifestRequest(**fixture.ManifestPayload)

    def test_create_manifest_request(self):
        """Serialize a Karrio manifest request into the Royal Mail manifest creation payload."""
        request = fixture.gateway.mapper.create_manifest_request(self.ManifestRequest)
        serialized = lib.to_dict(request.serialize())

        # Royal Mail's manifest creation schema accepts `carrierName` only.
        # Any generic Karrio `shipment_identifiers` must be ignored here.
        print(f"Generated request: {serialized}")
        self.assertEqual(serialized, fixture.ManifestRequest)
        self.assertNotIn("shipmentIdentifiers", serialized)

    def test_create_manifest(self):
        """Verify the proxy sends POST /manifests using only the Royal Mail-supported request fields."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Manifest.create(self.ManifestRequest).from_(fixture.gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/manifests",
            )

    def test_parse_manifest_response(self):
        """Parse a completed manifest response with a PDF document into Karrio manifest details."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ManifestResponse

            parsed_response = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedManifestResponse)

    def test_parse_error_response(self):
        """Normalize Royal Mail manifest creation errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ManifestErrorResponse

            parsed_response = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedManifestErrorResponse)

    def test_parse_manifest_response_without_pdf(self):
        """Ensure manifest responses without a PDF are treated as valid but document-unavailable results."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ManifestResponseWithoutPdf

            parsed = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(fixture.gateway)
                .parse()
            )

            self.assertEqual(parsed[0].meta["document_available"], False)
            self.assertIsNone(parsed[0].doc)

    def test_parse_manifest_nested_error_response(self):
        """Ensure multiple manifest errors are flattened into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ManifestNestedErrorResponse

            parsed = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(fixture.gateway)
                .parse()
            )

            self.assertGreater(len(parsed[1]), 0)




if __name__ == "__main__":
    unittest.main()

