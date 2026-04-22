 
 
"""Royal Mail Click and Drop carrier shipment cancel tests."""

import unittest
from unittest.mock import patch, ANY
from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropCancel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentCancelRequest = models.ShipmentCancelRequest(**fixture.ShipmentCancelPayload)

    def test_create_cancel_shipment_request(self):
        """Serialize a Karrio shipment-cancel request into the Royal Mail order identifier payload."""
        request = fixture.gateway.mapper.create_cancel_shipment_request(self.ShipmentCancelRequest)
        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), fixture.ShipmentCancelRequest)
        

    def test_cancel_shipment(self):
        """Verify numeric shipment identifiers remain unquoted in DELETE /orders/{orderIdentifiers}."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.cancel(self.ShipmentCancelRequest).from_(fixture.gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/12345678",
            )
        

    def test_parse_cancel_shipment_response(self):
        """Parse a successful cancel response into a Karrio confirmation object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentCancelResponse

            parsed_response = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedShipmentCancelResponse,
            )
        

    def test_parse_error_response(self):
        """Normalize Royal Mail cancel errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentCancelErrorResponse

            parsed_response = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), fixture.ParsedShipmentCancelErrorResponse)
        
    def test_create_cancel_shipment_request_with_reference(self):
        """Encode string order references exactly as Royal Mail expects inside orderIdentifiers."""
        request = models.ShipmentCancelRequest(**fixture.ShipmentCancelReferencePayload)
        serialized = fixture.gateway.mapper.create_cancel_shipment_request(request).serialize()

        print(f"Serialized cancel-by-reference request: {serialized}")
        self.assertEqual(
            serialized,
            {"orderIdentifiers": "%22ORDER-1001%22"},
    )

    def test_parse_cancel_multi_error_response(self):
        """Flatten multiple cancel errors into one Karrio message per failed order."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ShipmentCancelMultiErrorResponse

            parsed = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(fixture.gateway)
                .parse()
            )

            print(f"Parsed cancel multi-error response: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 2)
            self.assertEqual(parsed[1][0].code, "NotFound")
            self.assertEqual(parsed[1][1].code, "Forbidden")
if __name__ == "__main__":
    unittest.main()

