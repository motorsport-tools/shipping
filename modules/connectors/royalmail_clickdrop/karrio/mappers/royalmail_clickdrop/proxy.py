"""Karrio Royal Mail Click and Drop client proxy."""

import typing
from urllib.parse import urlencode

import karrio.api.proxy as proxy
import karrio.lib as lib
import karrio.mappers.royalmail_clickdrop.settings as provider_settings
import karrio.universal.mappers.rating_proxy as rating_proxy


def _normalize_query(query: typing.Optional[dict]) -> str:
    normalized = {}

    for key, value in (query or {}).items():
        if value is None:
            continue

        if isinstance(value, bool):
            normalized[key] = str(value).lower()
            continue

        if isinstance(value, (list, tuple)):
            normalized[key] = ",".join(str(item) for item in value)
            continue

        normalized[key] = value

    return urlencode(normalized)

def _signature_url(
        settings: provider_settings.Settings,
        tracking_number: str,
        events_data: dict,
    ) -> typing.Optional[str]:
        mail_piece = (events_data or {}).get("mailPieces") or {}
        links = mail_piece.get("links") or {}
        signature_link = (links.get("signature") or {}).get("href")

        if signature_link:
            if signature_link.startswith("http"):
                return signature_link

            return f"{settings.tracking_server_url}{signature_link}"

        signature = mail_piece.get("signature") or {}
        if any(signature.get(key) for key in ["imageId", "recipientName", "signatureDateTime"]):
            return f"{settings.tracking_server_url}/mailpieces/v2/{tracking_number}/signature"

        return None


class Proxy(rating_proxy.RatingMixinProxy, proxy.Proxy):
    settings: provider_settings.Settings


    def get_rates(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        return super().get_rates(request)

    def create_shipment(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/orders",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def create_return_shipment(
        self, request: lib.Serializable
    ) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/returns",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def cancel_shipment(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}",
            trace=self.trace_as("json"),
            method="DELETE",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def create_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/manifests",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/manifests/{payload['manifestIdentifier']}",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def retry_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/manifests/retry/{payload['manifestIdentifier']}",
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_label(self, request: lib.Serializable) -> lib.Deserializable[typing.Any]:
        payload = request.serialize()
        qs = _normalize_query(payload.get("query"))

        url = f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}/label"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("binary"),
            method="GET",
            headers=self.settings.label_headers,
        )
        return lib.Deserializable(response, lambda x: x)

    def update_order_status(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/orders/status",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="PUT",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_order(self, request: lib.Serializable) -> lib.Deserializable[typing.Any]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def list_orders(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        payload = request.serialize()
        qs = _normalize_query(payload)

        url = f"{self.settings.server_url}/orders"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_order_details(self, request: lib.Serializable) -> lib.Deserializable[typing.Any]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}/full",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def list_order_details(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        payload = request.serialize()
        qs = _normalize_query(payload)

        url = f"{self.settings.server_url}/orders/full"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_return_services(self, request: lib.Serializable = None) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/returns/services",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_version(self, request: lib.Serializable = None) -> lib.Deserializable[dict]:
        response = lib.request(
            url=f"{self.settings.server_url}/version",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def authenticate(
        self, request: lib.Serializable = None
    ) -> lib.Deserializable[dict]:
        return lib.Deserializable(
            {
                "access_token": self.settings.api_key,
                "token_type": "Bearer",
            }
        )

    
    def get_tracking(
        self, request: lib.Serializable
    ) -> lib.Deserializable[typing.List[typing.Tuple[str, dict]]]:
        tracking_numbers = request.serialize()
        _trace = self.trace_as("json")

        def _fetch_tracking(tracking_number: str) -> typing.Tuple[str, dict]:
            events_response = lib.request(
                url=f"{self.settings.tracking_server_url}/mailpieces/v2/{tracking_number}/events",
                trace=_trace,
                method="GET",
                headers=self.settings.tracking_headers,
            )

            if events_response is None or not any(str(events_response).strip()):
                return tracking_number, {}

            events_data = lib.to_dict(events_response)
            signature_data = None
            signature_url = _signature_url(self.settings, tracking_number, events_data)

            if signature_url is not None:
                signature_response = lib.request(
                    url=signature_url,
                    trace=_trace,
                    method="GET",
                    headers=self.settings.tracking_headers,
                )

                if signature_response is not None and any(str(signature_response).strip()):
                    signature_payload = lib.to_dict(signature_response)

                    # only keep successful signature payloads; don't let missing POD
                    # turn into tracking errors when /events itself succeeded
                    if isinstance(signature_payload, dict) and signature_payload.get("mailPieces"):
                        signature_data = signature_payload

            return tracking_number, {
                "events": events_data,
                "signature": signature_data,
            }

        responses = lib.run_asynchronously(_fetch_tracking, tracking_numbers)

        return lib.Deserializable(
            responses,
            lambda pairs: [
                (tracking_number, response)
                for tracking_number, response in pairs
                if response is not None
            ],
        )
