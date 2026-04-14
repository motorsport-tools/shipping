"""Royal Mail Click and Drop carrier label retrieval tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway, LabelPayload, LabelResponse, LabelErrorResponse


class TestRoyalMailClickandDropLabel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.LabelRequest = LabelPayload

    def test_create_label_request(self):
        request = gateway.mapper.create_label_request(self.LabelRequest)
        serialized = request.serialize()

        print("DEBUG create label request:", serialized)

        self.assertEqual(serialized["orderIdentifiers"], "12345678")
        self.assertEqual(serialized["query"]["documentType"], "postageLabel")
        self.assertEqual(serialized["query"]["includeReturnsLabel"], False)
        self.assertEqual(serialized["query"]["includeCN"], True)

    def test_get_label(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            gateway.proxy.get_label(request)

            print("DEBUG get label call args:", mock.call_args)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678/label?documentType=postageLabel&includeReturnsLabel=false&includeCN=true",
            )
            self.assertEqual(mock.call_args[1]["method"], "GET")
            self.assertEqual(
                mock.call_args[1]["headers"]["Authorization"],
                f"Bearer {gateway.settings.api_key}",
            )

    def test_parse_label_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            response = gateway.proxy.get_label(request)
            docs, messages = gateway.mapper.parse_label_response(response)

            print("DEBUG parsed label docs:", lib.to_dict(docs) if docs else None)
            print("DEBUG parsed label messages:", lib.to_dict(messages))

            self.assertIsNotNone(docs)
            self.assertEqual(len(messages), 0)
            self.assertIsNotNone(docs.label)

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = LabelErrorResponse

            request = gateway.mapper.create_label_request(self.LabelRequest)
            response = gateway.proxy.get_label(request)
            docs, messages = gateway.mapper.parse_label_response(response)

            print("DEBUG parsed label error docs:", docs)
            print("DEBUG parsed label error messages:", lib.to_dict(messages))

            self.assertIsNone(docs)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].code, "NotFound")
            self.assertEqual(messages[0].message, "Order not found")


if __name__ == "__main__":
    unittest.main()
