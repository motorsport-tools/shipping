"""Royal Mail Click and Drop carrier label retrieval tests."""

import logging
import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropLabel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.LabelRequest = LabelPayload

    def test_create_label_request(self):
        request = gateway.mapper.create_label_request(self.LabelRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), LabelRequest)

    def test_get_label(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            gateway.proxy.get_label(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678/label"
                "?documentType=postageLabel&includeReturnsLabel=false&includeCN=true",
            )

    def test_parse_label_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            response = gateway.proxy.get_label(request)
            parsed_response = list(gateway.mapper.parse_label_response(response))

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedLabelResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelErrorResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            response = gateway.proxy.get_label(request)
            parsed_response = list(gateway.mapper.parse_label_response(response))

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


LabelPayload = {
    "order_identifiers": [12345678],
    "document_type": "postageLabel",
    "include_cn": True,
}

LabelRequest = {
    "orderIdentifiers": "12345678",
    "query": {
        "documentType": "postageLabel",
        "includeReturnsLabel": False,
        "includeCN": True,
    },
}

LabelResponse = b"%PDF-1.4 test label pdf"

LabelErrorResponse = b'[{"code":"NotFound","message":"Order not found"}]'

ParsedLabelResponse = [
    {
        "label": "JVBERi0xLjQgdGVzdCBsYWJlbCBwZGY=",
        "pdf_label": "JVBERi0xLjQgdGVzdCBsYWJlbCBwZGY=",
    },
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order not found",
            "details": {
                "operation": "get_label",
            },
        }
    ],
]