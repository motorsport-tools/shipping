"""Royal Mail Click and Drop additional branch-coverage tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.royalmail.units as provider_units

from . import fixture


class TestRoyalMailClickandDropAdditionalBranches(unittest.TestCase):
    def _shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _return_shipment(self, payload):
        return models.ShipmentRequest(**copy.deepcopy(payload))

    def _expected_return_service_codes_from_response(self, response):
        """Resolve expected return service codes from services.csv via units.py.

        services.csv is the source of truth. The Royal Mail API response gives
        raw carrier service codes such as TSS. The parser resolves those to the
        canonical Karrio service_code declared in services.csv.
        """
        return [
            (
                provider_units.resolve_service_code(service.get("serviceCode"))
                or provider_units.resolve_service_code(service.get("serviceName"))
                or service.get("serviceCode")
            )
            for service in response.get("services", [])
            if isinstance(service, dict)
        ]

    def test_create_shipment_request_with_top_level_billing_address_alias(self):
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(fixture.ShipmentPayloadWithBillingAddress)
        )
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(
            serialized["items"][0]["billing"],
            fixture.ShipmentRequestWithBillingAddress["items"][0]["billing"],
        )

    def test_create_shipment_request_with_order_id_fallback(self):
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(fixture.ShipmentPayloadWithOrderIdFallback)
        )
        serialized = lib.to_dict(request.serialize())

        self.assertEqual(serialized["items"][0]["orderReference"], "ORDER-ID-1001")

    def test_create_shipment_request_with_customs_invoice_fallback(self):
        """Source invoice number and date from shipment.customs when shipment options omit them."""
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(fixture.ShipmentPayloadWithCustomsInvoiceFallback)
        )
        serialized = lib.to_dict(request.serialize())
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["commercialInvoiceNumber"], "INV-CUSTOMS-1001")
        self.assertEqual(postage["commercialInvoiceDate"], "2024-01-03T10:00:00Z")

    def test_create_shipment_request_with_importer_fallbacks(self):
        """Build importer VAT, tax, and EORI fields from option fallbacks when no importer object is supplied."""
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(fixture.ShipmentPayloadWithImporterFallbacks)
        )
        serialized = lib.to_dict(request.serialize())
        importer = serialized["items"][0]["importer"]

        self.assertEqual(importer["vatNumber"], "GB123456789")
        self.assertEqual(importer["taxCode"], "TAX-GB-1001")
        self.assertEqual(importer["eoriNumber"], "GB123456789000")

    def test_create_shipment_request_without_importer_omits_importer_block(self):
        """Omit importer when neither importer data nor importer fallback options are provided."""
        request = fixture.gateway.mapper.create_shipment_request(
            self._shipment(fixture.ShipmentPayloadWithoutImporter)
        )
        serialized = lib.to_dict(request.serialize())

        self.assertNotIn("importer", serialized["items"][0])

    def test_parse_shipment_response_created_only(self):
        """Parse created-only order responses even when manifested/shipped timestamps are not yet populated."""
        parsed = fixture.gateway.mapper.parse_shipment_response(
            lib.Deserializable(fixture.ShipmentResponseCreatedOnly, lambda x: x)
        )

        self.assertEqual(parsed[0].shipment_identifier, "12345678")
        self.assertEqual(parsed[0].tracking_number, "RM123456789GB")
        self.assertIsNone(parsed[0].meta["manifested_on"])
        self.assertIsNone(parsed[0].meta["shipped_on"])
        self.assertIsNotNone(parsed[0].docs)

    def test_create_return_shipment_request_raw_service_code_passes_through(self):
        """Allow raw Royal Mail return service codes to pass directly into the return request."""
        request = fixture.gateway.mapper.create_return_shipment_request(
            self._return_shipment(fixture.ReturnShipmentPayloadRawServiceCode)
        )

        self.assertEqual(
            lib.to_dict(request.serialize())["service"]["serviceCode"],
            "TSS",
        )

    def test_create_return_shipment_request_service_option_override(self):
        """Allow options.service_code to override the normalized return service selector."""
        request = fixture.gateway.mapper.create_return_shipment_request(
            self._return_shipment(fixture.ReturnShipmentPayloadWithServiceOptionOverride)
        )

        self.assertEqual(
            lib.to_dict(request.serialize()),
            fixture.ReturnShipmentRequestWithServiceOptionOverride,
        )

    def test_parse_return_services_response_preserves_carrier_service_codes(self):
        """Preserve Royal Mail return service codes from /returns/services."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnServicesResponse

            request = fixture.gateway.mapper.create_get_return_services_request(
                fixture.ReturnServicesRequest
            )
            response = fixture.gateway.proxy.get_return_services(request)
            parsed = list(
                fixture.gateway.mapper.parse_get_return_services_response(response)
            )

            self.assertEqual(
                [service.serviceCode for service in parsed[0].services],
                [
                    service["serviceCode"]
                    for service in fixture.ReturnServicesResponse.get("services", [])
                ],
            )