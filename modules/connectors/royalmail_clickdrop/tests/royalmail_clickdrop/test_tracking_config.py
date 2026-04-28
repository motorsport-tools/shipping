"""Royal Mail Click and Drop tracking configuration and auth-header tests."""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import fixture


class TestRoyalMailClickandDropTrackingConfig(unittest.TestCase):
    def _gateway(self, **kwargs):
        payload = {
            "id": "123456789",
            "carrier_id": "royalmail",
            "api_key": "CLICKDROP_API_KEY",
            "tracking_client_id": kwargs.get("tracking_client_id"),
            "tracking_client_secret": kwargs.get("tracking_client_secret"),
            "config": kwargs.get("config", {}),
        }
        return karrio.gateway["royalmail"].create(payload)

    def _tracking(self, payload):
        return models.TrackingRequest(**payload)

    def test_tracking_headers_include_ibm_credentials_and_terms_header(self):
        """Build the full Royal Mail Tracking API IBM gateway header set."""
        gateway = self._gateway(
            tracking_client_id="CLIENT_ID",
            tracking_client_secret="CLIENT_SECRET",
        )

        self.assertEqual(
            gateway.settings.tracking_headers,
            {
                "Accept": "application/json",
                "X-IBM-Client-Id": "CLIENT_ID",
                "X-IBM-Client-Secret": "CLIENT_SECRET",
                "X-Accept-RMG-Terms": "yes",
            },
        )

    def test_tracking_headers_require_credentials(self):
        """Reject tracking usage when the separate Royal Mail tracking credentials are missing."""
        gateway = self._gateway()

        with self.assertRaisesRegex(
            ValueError,
            "tracking_client_id` and `tracking_client_secret",
        ):
            _ = gateway.settings.tracking_headers

    def test_tracking_server_url_uses_connection_config_override(self):
        """Honor connection-config overrides for the tracking API base URL."""
        gateway = self._gateway(
            tracking_client_id="CLIENT_ID",
            tracking_client_secret="CLIENT_SECRET",
            config={"tracking_base_url": "https://tracking.example.test/v2/"},
        )

        self.assertEqual(
            gateway.settings.tracking_server_url,
            "https://tracking.example.test/v2",
        )

    def test_get_tracking_sends_tracking_headers_on_summary_and_events_requests(self):
        """Send the same IBM tracking headers on both summary and events calls."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseJSON,
                fixture.TrackingResponseJSON,
            ]

            karrio.Tracking.fetch(
                self._tracking(fixture.TrackingPayload)
            ).from_(fixture.gateway)

            self.assertEqual(
                mock.call_args_list[0][1]["headers"],
                fixture.gateway.settings.tracking_headers,
            )
            self.assertEqual(
                mock.call_args_list[1][1]["headers"],
                fixture.gateway.settings.tracking_headers,
            )

    def test_parse_tracking_blank_summary_response(self):
        """Treat blank Royal Mail summary responses as an empty successful lookup."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ""

            parsed = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(lib.to_dict(parsed), [[], []])

    def test_parse_tracking_signature_error_payload_is_ignored_gracefully(self):
        """Ignore non-mailPieces signature payloads and still return the tracking detail."""
        signature_error_response = {
            "httpCode": 404,
            "httpMessage": "Not Found",
            "errors": [
                {
                    "errorCode": "E2002",
                    "errorDescription": "No signature available",
                }
            ],
        }

        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseWithProofOfDeliveryJSON,
                signature_error_response,
            ]

            parsed = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            details = parsed[0][0]
            self.assertEqual(details.tracking_number, fixture.TrackingPayload["tracking_numbers"][0])
            self.assertIsNone(details.images)
