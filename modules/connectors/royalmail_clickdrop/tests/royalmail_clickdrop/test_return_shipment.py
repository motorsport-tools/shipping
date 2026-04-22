 
 
"""Royal Mail Click and Drop carrier return shipment tests."""

import logging
import unittest
from unittest.mock import patch



import karrio.core.models as models
import karrio.lib as lib
from . import fixture

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropReturnShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnShipmentRequest = models.ShipmentRequest(**fixture.ReturnShipmentPayload)

    def test_create_return_shipment_request(self):
        """Serialize a Karrio return shipment into the Royal Mail return request payload."""
        request = fixture.gateway.mapper.create_return_shipment_request(
            self.ReturnShipmentRequest
        )

        print(f"Generated request: {lib.to_dict(request.serialize())}")
        self.assertEqual(lib.to_dict(request.serialize()), fixture.ReturnShipmentRequest)

    def test_create_return_shipment(self):
        """Verify the proxy sends the return shipment request to POST /returns."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            fixture.gateway.proxy.create_return_shipment(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/returns",
            )

    def test_parse_return_shipment_response(self):
        """Parse a successful return creation response into Karrio shipment details, label docs, and QR metadata."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponse

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_return_shipment_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedReturnShipmentResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail return creation errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentErrorResponse

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_return_shipment_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedReturnShipmentErrorResponse,
            )
#  invalid service test
    def test_create_return_shipment_request_invalid_service(self):
        """Reject non-return service selectors when building a Royal Mail return shipment request."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadInvalidService)

        with self.assertRaises(ValueError):
            fixture.gateway.mapper.create_return_shipment_request(shipment)

#  single-name split test

    def test_create_return_shipment_request_single_name(self):
        """Ensure a single-word person name is split safely into firstName with an empty lastName."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadSingleName)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["shipment"]["shippingAddress"]["firstName"],
            "John",
        )

    def test_create_return_shipment_request_us_country_mapping(self):
        """Map US addresses to the expected country name and ISO3 code in the return payload."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadUSCountry)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print(f"US country mapping request: {serialized}")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["country"], "United States")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["countryIsoCode"], "USA")

    def test_create_return_shipment_request_es_country_mapping(self):
        """Map ES addresses to the expected country name and ISO3 code in the return payload."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadESCountry)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        print(f"ES country mapping request: {serialized}")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["country"], "Spain")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["countryIsoCode"], "ESP")

    def test_parse_return_shipment_response_without_label(self):
        """Treat a return without an inline label as a valid return shipment with docs set to None."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponseWithoutLabel

            request = fixture.gateway.mapper.create_return_shipment_request(self.ReturnShipmentRequest)
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

            print(f"Parsed return shipment without label: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0].docs)

def test_parse_return_shipment_response_without_shipment(self):
    """Return a parser diagnostic when Royal Mail omits the shipment object in the response."""
    with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
        mock.return_value = fixture.ReturnShipmentResponseWithoutShipment

        request = fixture.gateway.mapper.create_return_shipment_request(self.ReturnShipmentRequest)
        response = fixture.gateway.proxy.create_return_shipment(request)
        parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

        # A success-shaped response without `shipment` is not a carrier error,
        # but it is not usable as a Karrio shipment result either. We expect a
        # synthetic parser message so the malformed payload is visible.
        print(f"Parsed return shipment without shipment: {lib.to_dict(parsed)}")
        self.assertListEqual(
            lib.to_dict(parsed),
            fixture.ParsedReturnShipmentWithoutShipmentResponse,
        )           

    def test_parse_return_shipment_array_error_response(self):
        """Flatten array-based return shipment errors into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentArrayErrorResponse

            request = fixture.gateway.mapper.create_return_shipment_request(self.ReturnShipmentRequest)
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

            print(f"Parsed return shipment array errors: {lib.to_dict(parsed)}")
            self.assertIsNone(parsed[0])
            self.assertEqual(len(parsed[1]), 1)
            self.assertEqual(parsed[1][0].code, "BadRequest")

    def test_parse_return_shipment_response_without_tracking(self):
        """Default tracking_number when Royal Mail creates a return without a tracking code."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponseWithoutTracking

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

            print(f"Parsed return shipment without tracking: {lib.to_dict(parsed)}")
            self.assertEqual(parsed[0].tracking_number, "no code provided")
            self.assertEqual(parsed[0].shipment_identifier, "0A12345678901234")
            self.assertFalse(parsed[0].meta["tracking_number_provided"])

if __name__ == "__main__":
    unittest.main()