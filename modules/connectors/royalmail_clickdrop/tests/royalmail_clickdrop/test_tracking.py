"""Royal Mail Click and Drop carrier tracking tests."""

import copy
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import fixture


class TestRoyalMailClickandDropTracking(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _tracking(self, payload):
        return models.TrackingRequest(**copy.deepcopy(payload))

    def test_create_tracking_request(self):
        """Serialize a Karrio tracking request into Royal Mail mail piece identifiers."""
        request = fixture.gateway.mapper.create_tracking_request(
            self._tracking(fixture.TrackingPayload)
        )

        self.assertEqual(
            request.serialize(),
            fixture.TrackingRequestJSON,
        )

    def test_get_tracking(self):
        """Use /summary first, then enrich a single tracking number with /events."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseJSON,
                fixture.TrackingResponseJSON,
            ]

            karrio.Tracking.fetch(
                self._tracking(fixture.TrackingPayload)
            ).from_(fixture.gateway)

            self.assertEqual(mock.call_count, 2)
            self.assertEqual(
                mock.call_args_list[0][1]["url"],
                f"{fixture.gateway.settings.tracking_server_url}/mailpieces/v2/summary?mailPieceId={fixture.TrackingRequestJSON[0]}",
            )
            self.assertEqual(
                mock.call_args_list[1][1]["url"],
                f"{fixture.gateway.settings.tracking_server_url}/mailpieces/v2/{fixture.TrackingRequestJSON[0]}/events",
            )
            self.assertEqual(
                mock.call_args_list[0][1]["headers"],
                fixture.gateway.settings.tracking_headers,
            )

    def test_get_tracking_multiple_numbers_with_event_enrichment(self):
        """Use bulk /summary, then enrich each successful tracking number with /events."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryPartialResponseJSON,
                fixture.TrackingResponseJSON,
            ]

            karrio.Tracking.fetch(
                self._tracking(fixture.TrackingPayloadMulti)
            ).from_(fixture.gateway)

            self.assertEqual(mock.call_count, 2)
            self.assertIn(
                "/mailpieces/v2/summary?mailPieceId=",
                mock.call_args_list[0][1]["url"],
            )
            self.assertEqual(
                mock.call_args_list[1][1]["url"],
                f"{fixture.gateway.settings.tracking_server_url}/mailpieces/v2/{fixture.TrackingRequestJSON[0]}/events",
            )

    def test_parse_tracking_response(self):
        """Parse /summary + /events into Karrio tracking details for a single piece."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseJSON,
                fixture.TrackingResponseJSON,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingResponse,
            )

    def test_parse_tracking_error_response(self):
        """Normalize top-level Royal Mail tracking API errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.TrackingErrorResponseJSON

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingErrorResponse,
            )

    def test_parse_tracking_response_without_summary(self):
        """Allow /events payloads to continue working even when the event response omits summary."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseJSON,
                fixture.TrackingResponseWithoutSummaryJSON,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingResponseWithoutSummary,
            )

    def test_parse_tracking_summary_partial_response(self):
        """Parse bulk /summary responses into successful tracking details plus per-piece errors."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryPartialResponseJSON,
                fixture.TrackingResponseJSON,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayloadMulti)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingSummaryPartialResponse,
            )

    def test_get_tracking_with_proof_of_delivery(self):
        """Fetch /signature after /summary and /events when POD is available."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                fixture.TrackingSignatureResponseJSON,
            ]

            karrio.Tracking.fetch(
                self._tracking(fixture.TrackingPayload)
            ).from_(fixture.gateway)

            self.assertEqual(mock.call_count, 3)
            self.assertEqual(
                mock.call_args_list[2][1]["url"],
                f"{fixture.gateway.settings.tracking_server_url}/mailpieces/v2/{fixture.TrackingRequestJSON[0]}/signature",
            )

    def test_parse_tracking_response_with_proof_of_delivery(self):
        """Merge Royal Mail signature proof-of-delivery into Karrio tracking details."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                fixture.TrackingSignatureResponseJSON,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingResponseWithProofOfDelivery,
            )

    def test_parse_tracking_response_with_proof_of_delivery_image(self):
        """Expose the Royal Mail POD signature image as base64 and a displayable data URI."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                fixture.TrackingSignatureResponseJSON,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            details = lib.to_dict(parsed_response)[0][0]

            self.assertEqual(
                details["images"]["signature_image"],
                "PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
            )
            self.assertEqual(
                details["meta"]["proof_of_delivery"]["base64"],
                "PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
            )
            self.assertEqual(
                details["meta"]["proof_of_delivery"]["data_uri"],
                "data:image/svg+xml;base64,PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
            )

    def test_parse_tracking_response_without_signature_image_keeps_pod_event_only(self):
        """Keep POD event and signatory info even when the signature payload has no image content."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                """{
                  "mailPieces": {
                    "mailPieceId": "090367574000000FE1E1B",
                    "carrierShortName": "RM",
                    "carrierFullName": "Royal Mail Group Ltd",
                    "signature": {
                      "recipientName": "Simon",
                      "signatureDateTime": "2017-03-30T16:15:00+0000",
                      "imageFormat": "image/svg+xml",
                      "imageId": "001234"
                    }
                  }
                }""",
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            details = lib.to_dict(parsed_response)[0][0]

            self.assertEqual(details["info"]["customer_name"], "Simon")
            self.assertEqual(details["events"][1]["code"], "POD")
            self.assertNotIn("images", details)

    def test_create_shipment_request_multi_parcel_customs_only_subtotal(self):
        """Use shipment-level customs commodities for subtotal when multi-parcel items are not parcel-scoped."""
        payload = copy.deepcopy(fixture.ShipmentPayloadMultiParcel)
        payload["recipient"]["country_code"] = "FR"
        payload["recipient"]["postal_code"] = "75001"
        payload["recipient"]["city"] = "Paris"
        payload["recipient"]["person_name"] = "Jean Martin"
        payload["recipient"]["company_name"] = "Example FR"
        payload["recipient"]["email"] = "jean@example.fr"
        payload["reference"] = "ORDER-MULTI-CUSTOMS-ONLY"
        payload["options"]["order_reference"] = "ORDER-MULTI-CUSTOMS-ONLY"
        payload["options"].pop("subtotal", None)
        payload["options"].pop("total", None)
        payload["options"]["shipping_cost_charged"] = 3.5
        payload["options"]["order_tax"] = 1.2

        for parcel in payload["parcels"]:
            parcel.pop("items", None)

        payload["customs"] = {
            "content_type": "merchandise",
            "commodities": [
                {
                    "sku": "SKU-1",
                    "description": "Blue T-Shirt",
                    "quantity": 2,
                    "value_amount": 12.5,
                    "weight": 150,
                    "weight_unit": "G",
                    "hs_code": "610910",
                    "origin_country": "GB",
                }
            ],
        }

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["subtotal"], 25.0)
        self.assertEqual(item["shippingCostCharged"], 3.5)
        self.assertEqual(item["orderTax"], 1.2)
        self.assertEqual(item["total"], 29.7)

    def test_create_shipment_request_notification_target_falls_back_to_sender(self):
        """Default email notifications to the selected contact that actually has an email address."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["recipient"]["email"] = ""
        payload["shipper"]["email"] = "warehouse@example.com"
        payload["options"].pop("send_notifications_to", None)
        payload["options"].pop("receive_email_notification", None)
        payload["options"].pop("email_notification", None)

        serialized = self._serialized_request(payload)
        postage = serialized["items"][0]["postageDetails"]

        self.assertEqual(postage["sendNotificationsTo"], "sender")
        self.assertTrue(postage["receiveEmailNotification"])

    def test_create_shipment_request_fractional_dangerous_goods_quantity(self):
        """Preserve fractional dangerous-goods quantities instead of coercing them to integers."""
        payload = copy.deepcopy(fixture.ShipmentPayloadWithoutBilling)
        payload["options"]["contains_dangerous_goods"] = True
        payload["options"]["dangerous_goods_un_code"] = "1993"
        payload["options"]["dangerous_goods_description"] = "Flammable liquid"
        payload["options"]["dangerous_goods_quantity"] = 0.5

        serialized = self._serialized_request(payload)
        item = serialized["items"][0]

        self.assertEqual(item["dangerousGoodsQuantity"], 0.5)

if __name__ == "__main__":
    unittest.main()