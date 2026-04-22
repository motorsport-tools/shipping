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
        """Verify the proxy sends tracking requests to GET /mailpieces/v2/{mailPieceId}/events."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            karrio.Tracking.fetch(
                self._tracking(fixture.TrackingPayload)
            ).from_(fixture.gateway)

            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.tracking_server_url}/mailpieces/v2/{fixture.TrackingRequestJSON[0]}/events",
            )
            self.assertEqual(
                mock.call_args[1]["headers"],
                fixture.gateway.settings.tracking_headers,
            )

    def test_parse_tracking_response(self):
        """Parse a successful Royal Mail tracking events response into Karrio tracking details."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.TrackingResponseJSON

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
        """Normalize Royal Mail tracking API errors into Karrio message objects."""
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
        """Allow YAML-valid mailPieces responses that omit summary."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.TrackingResponseWithoutSummaryJSON

            parsed_response = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                ).from_(fixture.gateway).parse()
            )

            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedTrackingResponseWithoutSummary,
            )


if __name__ == "__main__":
    unittest.main()