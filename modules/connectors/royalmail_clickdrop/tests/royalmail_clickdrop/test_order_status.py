 
 
"""Royal Mail Click and Drop carrier order status update tests."""

import logging
import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropOrderStatus(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.OrderStatusRequest = fixture.OrderStatusPayload

    def test_create_order_status_request(self):
        """Serialize normalized order status items into the Royal Mail bulk status update payload."""
        request = fixture.gateway.mapper.create_order_status_request(self.OrderStatusRequest)

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.OrderStatusRequest)

    def test_update_order_status(self):
        """Verify the proxy sends the status update request to PUT /orders/status."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            fixture.gateway.proxy.update_order_status(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/orders/status",
            )

    def test_parse_order_status_response(self):
        """Parse a successful order status update into a Karrio confirmation object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.OrderStatusResponse

            request = fixture.gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            response = fixture.gateway.proxy.update_order_status(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_order_status_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedOrderStatusResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail order status update errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.OrderStatusErrorResponse

            request = fixture.gateway.mapper.create_order_status_request(
                self.OrderStatusRequest
            )
            response = fixture.gateway.proxy.update_order_status(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_order_status_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedOrderStatusErrorResponse,
            )

    def test_create_order_status_request_other_courier(self):
        """Serialize despatchedByOtherCourier updates with the extra carrier/tracking fields Royal Mail requires."""
        request = fixture.gateway.mapper.create_order_status_request(fixture.OrderStatusOtherCourierPayload)

        print(f"Other courier status request: {request.serialize()}")
        self.assertEqual(
            request.serialize()["items"][0]["shippingCarrier"],
            "Other Carrier",
        )

    def test_parse_order_status_partial_success_response(self):
        """Return a confirmation plus error messages when Royal Mail updates some orders but rejects others."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.OrderStatusPartialSuccessResponse

            request = fixture.gateway.mapper.create_order_status_request(self.OrderStatusRequest)
            response = fixture.gateway.proxy.update_order_status(request)
            parsed = list(fixture.gateway.mapper.parse_order_status_response(response))

            print(f"Parsed order status partial success: {lib.to_dict(parsed)}")
            self.assertIsNotNone(parsed[0])
            self.assertFalse(parsed[0].success)
            self.assertEqual(len(parsed[1]), 1)

    def test_create_order_status_request_requires_items(self):
        """Reject empty order status update payloads before sending them to Royal Mail."""
        with self.assertRaises(ValueError):
            fixture.gateway.mapper.create_order_status_request({"items": []})

    def test_create_order_status_request_validates_other_courier_fields(self):
        """Reject despatchedByOtherCourier updates that provide tracking without the required dispatch metadata."""
        with self.assertRaises(ValueError):
            fixture.gateway.mapper.create_order_status_request(
                {
                    "items": [
                        {
                            "order_identifier": 12345678,
                            "status": "despatchedByOtherCourier",
                            "tracking_number": "OTHER123456",
                        }
                    ]
                }
            )         

