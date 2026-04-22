"""Royal Mail Click and Drop carrier return shipment tests."""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib

from . import fixture


class TestRoyalMailClickandDropReturnShipment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnShipmentRequest = models.ShipmentRequest(**fixture.ReturnShipmentPayload)

    def test_create_return_shipment_request(self):
        """Serialize a Karrio return shipment into the Royal Mail return request payload."""
        request = fixture.gateway.mapper.create_return_shipment_request(
            self.ReturnShipmentRequest
        )

        self.assertEqual(lib.to_dict(request.serialize()), fixture.ReturnShipmentRequest)

    def test_create_return_shipment(self):
        """Verify the proxy sends the return shipment request to POST /returns."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            fixture.gateway.proxy.create_return_shipment(request)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/returns",
            )

    def test_parse_return_shipment_response(self):
        """Parse a successful return creation response into Karrio shipment details."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponse

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_return_shipment_response(response)
            )

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

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedReturnShipmentErrorResponse,
            )

    def test_create_return_shipment_request_invalid_service(self):
        """Reject non-return service selectors when building a Royal Mail return shipment request."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadInvalidService)

        with self.assertRaises(ValueError):
            fixture.gateway.mapper.create_return_shipment_request(shipment)

    def test_create_return_shipment_request_single_name(self):
        """Ensure a single-word person name is split safely into firstName with an empty lastName."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadSingleName)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["shipment"]["shippingAddress"]["firstName"],
            "John",
        )
        self.assertEqual(
            serialized["shipment"]["shippingAddress"].get("lastName"),
            None,
        )

    def test_create_return_shipment_request_us_country_mapping(self):
        """Map US addresses to the expected country name and ISO3 code in the return payload."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadUSCountry)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(serialized["shipment"]["shippingAddress"]["country"], "United States")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["countryIsoCode"], "USA")

    def test_create_return_shipment_request_es_country_mapping(self):
        """Map ES addresses to the expected country name and ISO3 code in the return payload."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadESCountry)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(serialized["shipment"]["shippingAddress"]["country"], "Spain")
        self.assertEqual(serialized["shipment"]["shippingAddress"]["countryIsoCode"], "ESP")

    def test_create_return_shipment_request_uses_return_address_override(self):
        """Prefer payload.return_address over payload.recipient when provided."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadWithReturnAddress)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["shipment"]["returnAddress"]["addressLine1"],
            fixture.ReturnShipmentPayloadWithReturnAddress["return_address"]["address_line1"],
        )

    def test_create_return_shipment_request_uses_order_id_fallback(self):
        """Use top-level order_id when reference is not supplied."""
        shipment = models.ShipmentRequest(**fixture.ReturnShipmentPayloadWithOrderId)
        request = fixture.gateway.mapper.create_return_shipment_request(shipment)
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["shipment"]["customerReference"]["reference"],
            fixture.ReturnShipmentPayloadWithOrderId["order_id"],
        )

    def test_parse_return_shipment_response_without_label(self):
        """Treat a return without an inline label as a valid return shipment with docs set to None."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponseWithoutLabel

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

            self.assertIsNone(parsed[0].docs)

    def test_parse_return_shipment_response_without_shipment(self):
        """Return a parser diagnostic when Royal Mail omits the shipment object in the response."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentResponseWithoutShipment

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

            self.assertListEqual(
                lib.to_dict(parsed),
                fixture.ParsedReturnShipmentWithoutShipmentResponse,
            )

    def test_parse_return_shipment_array_error_response(self):
        """Flatten array-based return shipment errors into Karrio messages."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnShipmentArrayErrorResponse

            request = fixture.gateway.mapper.create_return_shipment_request(
                self.ReturnShipmentRequest
            )
            response = fixture.gateway.proxy.create_return_shipment(request)
            parsed = list(fixture.gateway.mapper.parse_return_shipment_response(response))

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

            self.assertEqual(parsed[0].tracking_number, "no code provided")
            self.assertEqual(parsed[0].shipment_identifier, "0A12345678901234")
            self.assertFalse(parsed[0].meta["tracking_number_provided"])


if __name__ == "__main__":
    unittest.main()