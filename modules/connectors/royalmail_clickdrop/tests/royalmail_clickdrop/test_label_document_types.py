"""Royal Mail Click and Drop label document-type tests."""

import unittest
from unittest.mock import patch

from . import fixture


class TestRoyalMailClickandDropLabelDocumentTypes(unittest.TestCase):
    def test_create_label_request_for_cn22_omits_postage_only_flags(self):
        """Do not send postage-label-only flags for CN22 document requests."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "shipment_identifier": "12345678",
                "document_type": "CN22",
                "include_returns_label": True,
                "include_cn": True,
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "12345678",
                "query": {
                    "documentType": "CN22",
                    "includeReturnsLabel": None,
                    "includeCN": None,
                },
            },
        )

    def test_create_label_request_for_cn23_omits_postage_only_flags(self):
        """Do not send postage-label-only flags for CN23 document requests."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "shipment_identifier": "12345678",
                "document_type": "CN23",
                "include_returns_label": True,
                "include_cn": True,
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "12345678",
                "query": {
                    "documentType": "CN23",
                    "includeReturnsLabel": None,
                    "includeCN": None,
                },
            },
        )

    def test_create_label_request_for_despatch_note_omits_postage_only_flags(self):
        """Do not send postage-label-only flags for despatch note requests."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "shipment_identifier": "12345678",
                "document_type": "despatchNote",
                "include_returns_label": True,
                "include_cn": True,
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "12345678",
                "query": {
                    "documentType": "despatchNote",
                    "includeReturnsLabel": None,
                    "includeCN": None,
                },
            },
        )

    def test_get_label_for_cn22_omits_none_query_parameters(self):
        """Only send documentType in the query string when optional CN/returns flags are not applicable."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.LabelResponse

            request = fixture.gateway.mapper.create_label_request(
                {
                    "shipment_identifier": "12345678",
                    "document_type": "CN22",
                    "include_returns_label": True,
                    "include_cn": True,
                }
            )
            fixture.gateway.proxy.get_label(request)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678/label?documentType=CN22",
            )

    def test_create_label_request_accepts_camel_case_field_names(self):
        """Accept carrier-style camelCase label inputs in addition to snake_case helper inputs."""
        request = fixture.gateway.mapper.create_label_request(
            {
                "shipment_identifier": "12345678",
                "documentType": "postageLabel",
                "includeReturnsLabel": True,
                "includeCN": True,
            }
        )

        self.assertEqual(
            request.serialize(),
            {
                "orderIdentifiers": "12345678",
                "query": {
                    "documentType": "postageLabel",
                    "includeReturnsLabel": True,
                    "includeCN": True,
                },
            },
        )

    def test_create_label_request_rejects_invalid_document_type(self):
        """Reject unsupported Royal Mail document types before sending the request."""
        with self.assertRaisesRegex(
            ValueError,
            r"`document_type` must be one of `postageLabel`, `despatchNote`, `CN22`, or `CN23`",
        ):
            fixture.gateway.mapper.create_label_request(
                {
                    "shipment_identifier": "12345678",
                    "document_type": "invoice",
                }
            )