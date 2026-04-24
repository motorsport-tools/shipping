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

    def test_parse_tracking_response_with_png_proof_of_delivery_image(self):
        """Keep Royal Mail PNG proof-of-delivery image payloads as pass-through base64."""
        png_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7YxZQAAAAASUVORK5CYII="
        )
        png_signature_response = f"""{{
          "mailPieces": {{
            "mailPieceId": "090367574000000FE1E1B",
            "carrierShortName": "RM",
            "carrierFullName": "Royal Mail Group Ltd",
            "signature": {{
              "uniqueItemId": "090367574000000FE1E1B",
              "oneDBarcode": "FQ087430672GB",
              "recipientName": "Simon",
              "signatureDateTime": "2017-03-30T16:15:00+0000",
              "imageFormat": "image/png",
              "imageId": "001234",
              "height": 1,
              "width": 1,
              "image": "{png_base64}"
            }}
          }}
        }}"""

        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                png_signature_response,
            ]

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            details = lib.to_dict(parsed_response)[0][0]

            self.assertEqual(details["images"]["signature_image"], png_base64)
            self.assertEqual(
                details["meta"]["proof_of_delivery"]["base64"],
                png_base64,
            )
            self.assertEqual(
                details["meta"]["proof_of_delivery"]["data_uri"],
                f"data:image/png;base64,{png_base64}",
            )

    def test_get_tracking_chunks_summary_requests_over_30_numbers(self):
        """Split Royal Mail summary lookups into chunks of at most 30 tracking numbers."""
        payload = {
            "tracking_numbers": [
                f"RM{i:09d}GB"
                for i in range(31)
            ]
        }

        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingErrorResponseJSON,
                fixture.TrackingErrorResponseJSON,
            ]

            karrio.Tracking.fetch(
                self._tracking(payload)
            ).from_(fixture.gateway)

            self.assertEqual(mock.call_count, 2)

            first_url = mock.call_args_list[0][1]["url"]
            second_url = mock.call_args_list[1][1]["url"]

            self.assertIn("/mailpieces/v2/summary?mailPieceId=", first_url)
            self.assertIn("/mailpieces/v2/summary?mailPieceId=", second_url)

            first_ids = first_url.split("mailPieceId=", 1)[1].split(",")
            second_ids = second_url.split("mailPieceId=", 1)[1].split(",")

            self.assertEqual(len(first_ids), 30)
            self.assertEqual(len(second_ids), 1)

    def test_get_tracking_skips_events_for_summary_piece_errors(self):
        """Do not call /events when Royal Mail summary returns a mail-piece-level error."""
        summary_piece_error_response = """{
          "mailPieces": [
            {
              "mailPieceId": "ZZ000000000GB",
              "status": "404",
              "error": {
                "errorCode": "E2001",
                "errorDescription": "Tracking number not found",
                "errorCause": "The barcode reference isn't recognised",
                "errorResolution": "Please check the tracking number and resubmit"
              }
            }
          ]
        }"""

        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = summary_piece_error_response

            karrio.Tracking.fetch(
                self._tracking({"tracking_numbers": ["ZZ000000000GB"]})
            ).from_(fixture.gateway)

            self.assertEqual(mock.call_count, 1)
            self.assertIn(
                "/mailpieces/v2/summary?mailPieceId=ZZ000000000GB",
                mock.call_args_list[0][1]["url"],
            )

