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
            "click_and_drop_api_key": "CLICKANDDROP_API_KEY",
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

    def test_get_tracking_without_tracking_credentials_falls_back_to_click_and_drop(self):
        """Use Click & Drop /orders/{orderIdentifiers}/full when Tracking API credentials are absent."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ClickAndDropTrackingResponseJSON

            parsed = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.ClickAndDropTrackingPayload)
                )
                .from_(gateway)
                .parse()
            )

            self.assertEqual(mock.call_count, 1)
            self.assertEqual(
                mock.call_args_list[0][1]["url"],
                f"{gateway.settings.server_url}/orders/%22ORDER-1001%22/full",
            )
            self.assertEqual(
                mock.call_args_list[0][1]["headers"],
                gateway.settings.headers,
            )

        tracking_details, messages = parsed

        self.assertEqual(len(messages), 0)
        self.assertEqual(len(tracking_details), 1)
        self.assertEqual(tracking_details[0].tracking_number, "RM123456789GB")
        self.assertEqual(tracking_details[0].status, "in_transit")
        self.assertEqual(tracking_details[0].delivered, False)
        self.assertEqual(tracking_details[0].events[0].description, "In Transit")
        self.assertEqual(tracking_details[0].events[0].status, "in_transit")
        self.assertEqual(tracking_details[0].meta["source"], "click_and_drop")
        self.assertEqual(tracking_details[0].meta["order_identifier"], 12345678)
        self.assertEqual(tracking_details[0].meta["order_reference"], "ORDER-1001")

    def test_get_tracking_without_tracking_credentials_encodes_click_and_drop_order_reference(self):
        """Click & Drop order references must be quoted and percent-encoded in the path."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ClickAndDropTrackingResponseJSON

            karrio.Tracking.fetch(
                self._tracking(fixture.ClickAndDropTrackingReferencePayload)
            ).from_(gateway)

            self.assertEqual(mock.call_count, 1)
            self.assertEqual(
                mock.call_args_list[0][1]["url"],
                f"{gateway.settings.server_url}/orders/%22ORDER-1001%22/full",
            )

    def test_parse_click_and_drop_tracking_delivered_status(self):
        """Normalize Click & Drop basic tracking status into Karrio TrackingDetails."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ClickAndDropTrackingDeliveredResponseJSON

            details, messages = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.ClickAndDropTrackingPayload)
                )
                .from_(gateway)
                .parse()
            )

        self.assertEqual(len(messages), 0)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].tracking_number, "RM123456789GB")
        self.assertEqual(details[0].status, "delivered")
        self.assertEqual(details[0].delivered, True)
        self.assertEqual(details[0].events[0].description, "Delivered")
        self.assertEqual(details[0].events[0].status, "delivered")

    def test_parse_click_and_drop_tracking_error_response(self):
        """Normalize Click & Drop order lookup errors during fallback tracking."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = fixture.ClickAndDropTrackingErrorResponseJSON

            details, messages = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.ClickAndDropTrackingPayload)
                )
                .from_(gateway)
                .parse()
            )

        self.assertEqual(len(details), 0)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "NotFound")
        self.assertEqual(messages[0].message, "Order not found")
        self.assertEqual(messages[0].details["operation"], "tracking")

    def test_tracking_headers_require_credentials(self):
        """Reject direct Tracking API header access when Royal Mail tracking credentials are missing."""
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
            config={"tracking_api_base_url": "https://tracking.example.test/v2/"},
        )

        self.assertEqual(
            gateway.settings.tracking_server_url,
            "https://tracking.example.test/v2",
        )

    def test_tracking_server_url_accepts_legacy_config_key(self):
        """Remain backward compatible with older `tracking_base_url` config payloads."""
        gateway = self._gateway(
            tracking_client_id="CLIENT_ID",
            tracking_client_secret="CLIENT_SECRET",
            config={"tracking_base_url": "https://tracking-legacy.example.test/v2/"},
        )

        self.assertEqual(
            gateway.settings.tracking_server_url,
            "https://tracking-legacy.example.test/v2",
        )

    def test_get_tracking_sends_tracking_headers_on_summary_and_events_requests(self):
        """Send the same IBM tracking headers on both summary and events calls."""
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
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
        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = ""

            parsed = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                )
                .from_(fixture.gateway)
                .parse()
            )

            self.assertListEqual(lib.to_dict(parsed), [[], []])

    def test_parse_tracking_signature_error_payload_is_ignored_gracefully(self):
        """Ignore non-mailPieces signature payloads and still return the tracking detail."""
        signature_error_response = {
            "httpCode": 404,
            "httpMessage": "Not Found",
            "errors": [
                {
                    "errorCode": "NOT_FOUND",
                    "errorDescription": "Proof of delivery not available",
                }
            ],
        }

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.side_effect = [
                fixture.TrackingSummaryResponseWithProofOfDeliveryJSON,
                fixture.TrackingResponseJSON,
                signature_error_response,
            ]

            parsed = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.TrackingPayload)
                )
                .from_(fixture.gateway)
                .parse()
            )

            details, messages = parsed
            self.assertEqual(len(messages), 0)
            self.assertEqual(len(details), 1)
            self.assertEqual(details[0].tracking_number, "090367574000000FE1E1B")

    def test_click_and_drop_tracking_without_order_lookup_metadata_returns_message(self):
        """Click & Drop fallback cannot look up order details by tracking number alone."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            details, messages = (
                karrio.Tracking.fetch(
                    self._tracking(fixture.ClickAndDropTrackingMissingLookupPayload)
                )
                .from_(gateway)
                .parse()
            )

            self.assertEqual(mock.call_count, 0)

        self.assertEqual(len(details), 0)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "missing_order_reference")
        self.assertIn(
            "Click & Drop cannot retrieve full order details by tracking number alone",
            messages[0].message,
        )
        self.assertEqual(
            messages[0].details["tracking_number"],
            "RM123456789GB",
        )

    def test_click_and_drop_tracking_chunks_order_reference_lookups_over_100(self):
        """Click & Drop /orders/{orderIdentifiers}/full supports a maximum of 100 identifiers."""
        gateway = self._gateway()

        with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
            mock.return_value = "[]"

            karrio.Tracking.fetch(
                self._tracking(fixture.ClickAndDropTrackingChunkedPayload)
            ).from_(gateway)

            self.assertEqual(mock.call_count, 2)

            first_url = mock.call_args_list[0][1]["url"]
            second_url = mock.call_args_list[1][1]["url"]

            first_identifiers = first_url.rsplit("/orders/", 1)[1].split("/full", 1)[0]
            second_identifiers = second_url.rsplit("/orders/", 1)[1].split("/full", 1)[0]

            self.assertEqual(len(first_identifiers.split(";")), 100)
            self.assertEqual(len(second_identifiers.split(";")), 1)

    def test_parse_click_and_drop_shipping_tracking_status_matrix(self):
        """Map Click & Drop shippingTrackingStatus strings to Karrio statuses."""
        gateway = self._gateway()

        cases = [
            ("Sender preparing item", "pending", False),
            ("Label generated", "pending", False),
            ("Postage applied", "pending", False),
            ("In Transit", "in_transit", False),
            ("Received by Royal Mail", "in_transit", False),
            ("We've got it", "in_transit", False),
            ("Manifested", "in_transit", False),
            ("Despatched", "in_transit", False),
            ("Out for Delivery", "out_for_delivery", False),
            ("Due to be delivered today", "out_for_delivery", False),
            ("Ready for Collection", "ready_for_pickup", False),
            ("Available for Collection", "ready_for_pickup", False),
            ("Delivery Attempted", "delivery_failed", False),
            ("Unable to Deliver", "delivery_failed", False),
            ("Not Delivered", "delivery_failed", False),
            ("Delayed", "delivery_delayed", False),
            ("Held", "on_hold", False),
            ("Customs Hold", "on_hold", False),
            ("Returned to Sender", "return_to_sender", False),
            ("Delivered", "delivered", True),
        ]

        for raw_status, expected_status, expected_delivered in cases:
            with self.subTest(raw_status=raw_status):
                response = f"""[
                  {{
                    "orderIdentifier": 12345678,
                    "orderReference": "ORDER-1001",
                    "orderStatus": "shipped",
                    "shippedOn": "2024-01-02T09:00:00Z",
                    "shippingDetails": {{
                      "trackingNumber": "RM123456789GB",
                      "shippingTrackingStatus": "{raw_status}",
                      "serviceCode": "TPN24",
                      "shippingService": "Tracked 24",
                      "shippingCarrier": "Royal Mail",
                      "shippingUpdateSuccessDate": "2024-01-03T14:30:00Z",
                      "packages": [
                        {{
                          "packageNumber": 1,
                          "trackingNumber": "RM123456789GB"
                        }}
                      ]
                    }}
                  }}
                ]"""

                with patch("karrio.mappers.royalmail.proxy.lib.request") as mock:
                    mock.return_value = response

                    details, messages = (
                        karrio.Tracking.fetch(
                            self._tracking(fixture.ClickAndDropTrackingPayload)
                        )
                        .from_(gateway)
                        .parse()
                    )

                self.assertEqual(len(messages), 0)
                self.assertEqual(len(details), 1)
                self.assertEqual(details[0].tracking_number, "RM123456789GB")
                self.assertEqual(details[0].status, expected_status)
                self.assertEqual(details[0].delivered, expected_delivered)
                self.assertEqual(details[0].events[0].description, raw_status)
                self.assertEqual(details[0].events[0].status, expected_status)