"""Royal Mail Click and Drop carrier manifest tests."""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

from .fixture import gateway, ManifestPayload, ManifestResponse, ManifestErrorResponse


class TestRoyalMailClickandDropManifest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ManifestRequest = models.ManifestRequest(**ManifestPayload)

    def test_create_manifest_request(self):
        request = gateway.mapper.create_manifest_request(self.ManifestRequest)
        serialized = request.serialize()

        print("DEBUG create manifest request:", serialized)

        self.assertEqual(
            serialized,
            {
                "carrierName": "Royal Mail OBA"
            },
        )

    def test_create_manifest(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Manifest.create(self.ManifestRequest).from_(gateway)

            print("DEBUG create manifest call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/manifests",
            )
            self.assertEqual(mock.call_args[1]["method"], "POST")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )

    def test_parse_manifest_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ManifestResponse

            manifest, messages = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed manifest:", lib.to_dict(manifest) if manifest else None)
            print("DEBUG parsed manifest messages:", lib.to_dict(messages))

            self.assertIsNotNone(manifest)
            self.assertEqual(len(messages), 0)
            self.assertEqual(manifest.carrier_id, "royalmail_clickdrop")
            self.assertEqual(manifest.meta["manifest_number"], 1001)
            self.assertEqual(manifest.meta["status"], "completed")
            self.assertEqual(manifest.doc.manifest, "JVBERi0xLjQKJcfs...")

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ManifestErrorResponse

            manifest, messages = (
                karrio.Manifest.create(self.ManifestRequest)
                .from_(gateway)
                .parse()
            )

            print("DEBUG parsed manifest error manifest:", manifest)
            print("DEBUG parsed manifest error messages:", lib.to_dict(messages))

            self.assertIsNone(manifest)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "Forbidden")
            self.assertEqual(messages[0].message, "Feature not available")


if __name__ == "__main__":
    unittest.main()
