"""Royal Mail Click and Drop manifest edge-case tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib

from . import fixture


class TestRoyalMailClickandDropManifestEdgeCases(unittest.TestCase):
    def test_create_manifest_request_ignores_single_shipment_identifier(self):
        """Ignore generic shipment identifiers even when only a single identifier is supplied."""
        manifest = models.ManifestRequest(**copy.deepcopy(fixture.ManifestPayloadSingleOrder))
        request = fixture.gateway.mapper.create_manifest_request(manifest)

        self.assertEqual(lib.to_dict(request.serialize()), fixture.ManifestRequest)

    def test_create_get_manifest_request_accepts_reference_alias(self):
        """Accept `reference` as an alias for manifest lookup identifiers."""
        request = fixture.gateway.mapper.create_get_manifest_request({"reference": 1001})

        self.assertEqual(request.serialize(), {"manifestIdentifier": 1001})

    def test_create_retry_manifest_request_accepts_manifest_identifier_alias(self):
        """Accept `manifest_identifier` as a retry lookup alias."""
        request = fixture.gateway.mapper.create_retry_manifest_request(
            {"manifest_identifier": 1002}
        )

        self.assertEqual(request.serialize(), {"manifestIdentifier": 1002})

    def test_create_get_manifest_request_rejects_empty_identifier(self):
        """Reject manifest lookups that do not provide any identifier alias."""
        with self.assertRaisesRegex(ValueError, "manifest lookup requires"):
            fixture.gateway.mapper.create_get_manifest_request({})

    def test_parse_get_manifest_response_with_failed_status(self):
        """Normalize failed manifest lookups into a `failed` manifest meta status."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = {
                "manifestNumber": 1003,
                "status": "Failed",
                "documentPdf": None,
            }

            request = fixture.gateway.mapper.create_get_manifest_request({"reference": 1003})
            response = fixture.gateway.proxy.get_manifest(request)
            parsed = list(fixture.gateway.mapper.parse_get_manifest_response(response))

            self.assertEqual(parsed[0].meta["manifest_number"], 1003)
            self.assertEqual(parsed[0].meta["status"], "failed")
            self.assertFalse(parsed[0].meta["document_available"])
            self.assertIsNone(parsed[0].doc)
