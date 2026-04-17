"""Royal Mail Click and Drop carrier shipment cancel tests."""

import unittest
from unittest.mock import patch, ANY
from .fixture import gateway
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropCancel(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ShipmentCancelRequest = models.ShipmentCancelRequest(**ShipmentCancelPayload)

    def test_create_cancel_shipment_request(self):
        request = gateway.mapper.create_cancel_shipment_request(self.ShipmentCancelRequest)
        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), ShipmentCancelRequest)

    def test_cancel_shipment(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Shipment.cancel(self.ShipmentCancelRequest).from_(gateway)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/orders/12345678",
            )

    def test_parse_cancel_shipment_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ShipmentCancelResponse

            parsed_response = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedShipmentCancelResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ErrorResponse

            parsed_response = (
                karrio.Shipment.cancel(self.ShipmentCancelRequest)
                .from_(gateway)
                .parse()
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(lib.to_dict(parsed_response), ParsedErrorResponse)


if __name__ == "__main__":
    unittest.main()


ShipmentCancelPayload = {
    "shipment_identifier": "12345678",
}

ShipmentCancelRequest = {
    "orderIdentifiers": "12345678",
}

ShipmentCancelResponse = """{
  "deletedOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "orderInfo": "Deleted successfully"
    }
  ],
  "errors": []
}"""

ErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  }
]"""

ParsedShipmentCancelResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "operation": "Cancel Shipment",
        "success": True,
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
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]