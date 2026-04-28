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

    return urlencode(normalized, safe=",")

def _signature_url(
    settings: provider_settings.Settings,
    tracking_number: str,
    events_data: dict,
) -> typing.Optional[str]:
    mail_piece = (events_data or {}).get("mailPieces") or {}
    if isinstance(mail_piece, list):
        mail_piece = next(
            (item for item in mail_piece if isinstance(item, dict)),
            {},
        )

    links = mail_piece.get("links") or {}
    signature_link = (links.get("signature") or {}).get("href")

    if signature_link:
        if signature_link.startswith("http"):
            return signature_link

        return f"{settings.tracking_server_url}{signature_link}"

    signature = mail_piece.get("signature") or {}
    if any(signature.get(key) for key in ["imageId", "recipientName", "signatureDateTime"]):
        mail_piece_id = _tracking_mailpiece_identifier(
            tracking_number,
            mail_piece=mail_piece,
        )
        return f"{settings.tracking_server_url}/mailpieces/v2/{mail_piece_id}/signature"

    return None

def _chunks(values: typing.List[str], size: int = 30) -> typing.Iterable[typing.List[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _summary_url(
    settings: provider_settings.Settings,
    tracking_numbers: typing.List[str],
) -> str:
    query = _normalize_query({"mailPieceId": tracking_numbers})
    return f"{settings.tracking_server_url}/mailpieces/v2/summary?{query}"


def _summary_piece_keys(mail_piece: dict) -> typing.List[str]:
    summary = (mail_piece or {}).get("summary") or {}

    return [
        key
        for key in dict.fromkeys(
            [
                (mail_piece or {}).get("mailPieceId"),
                summary.get("uniqueItemId"),
                summary.get("oneDBarcode"),
            ]
        )
        if key
    ]

def _tracking_mailpiece_identifier(
    tracking_number: str,
    summary_piece: typing.Optional[dict] = None,
    mail_piece: typing.Optional[dict] = None,
) -> str:
    summary = (summary_piece or {}).get("summary") or {}
    events_summary = (mail_piece or {}).get("summary") or {}

    return (
        (mail_piece or {}).get("mailPieceId")
        or (summary_piece or {}).get("mailPieceId")
        or events_summary.get("uniqueItemId")
        or events_summary.get("oneDBarcode")
        or summary.get("uniqueItemId")
        or summary.get("oneDBarcode")
        or tracking_number
    )


def _events_url(
    settings: provider_settings.Settings,
    tracking_number: str,
    summary_piece: typing.Optional[dict] = None,
) -> str:
    links = (summary_piece or {}).get("links") or {}
    events_link = (links.get("events") or {}).get("href")

    if events_link:
        if events_link.startswith("http"):
            return events_link

        return f"{settings.tracking_server_url}{events_link}"

    mail_piece_id = _tracking_mailpiece_identifier(
        tracking_number,
        summary_piece=summary_piece,
    )

    return f"{settings.tracking_server_url}/mailpieces/v2/{mail_piece_id}/events"


def _summary_piece_has_error(summary_piece: typing.Optional[dict]) -> bool:
    return bool((summary_piece or {}).get("error"))
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
        results: typing.Dict[str, dict] = {}

        for chunk in _chunks(tracking_numbers, size=30):
            summary_response = lib.request(
                url=_summary_url(self.settings, chunk),
                trace=_trace,
                method="GET",
                headers=self.settings.tracking_headers,
            )

            if summary_response is None or not any(str(summary_response).strip()):
                for tracking_number in chunk:
                    results[tracking_number] = {
                        "summary": {},
                        "events": None,
                        "signature": None,
                    }
                continue

            summary_data = lib.to_dict(summary_response)

            if (
                isinstance(summary_data, dict)
                and any(
                    key in summary_data
                    for key in ["httpCode", "httpMessage", "errors"]
                )
                and not summary_data.get("mailPieces")
            ):
                for tracking_number in chunk:
                    results[tracking_number] = {
                        "summary": summary_data,
                        "events": None,
                        "signature": None,
                    }
                continue

            summary_map = {}
            for mail_piece in (summary_data or {}).get("mailPieces", []) or []:
                if not isinstance(mail_piece, dict):
                    continue

                for key in _summary_piece_keys(mail_piece):
                    summary_map[key] = mail_piece

            for tracking_number in chunk:
                summary_piece = summary_map.get(tracking_number)

                results[tracking_number] = {
                    "summary": (
                        {"mailPieces": [summary_piece]}
                        if summary_piece is not None
                        else {"mailPieces": []}
                    ),
                    "events": None,
                    "signature": None,
                }

        for tracking_number in tracking_numbers:
            tracking_data = results.get(tracking_number) or {}
            summary_payload = tracking_data.get("summary") or {}
            summary_piece = next(iter(summary_payload.get("mailPieces") or []), None)

            if isinstance(summary_payload, dict) and any(
                key in summary_payload for key in ["httpCode", "httpMessage", "errors"]
            ):
                continue

            if _summary_piece_has_error(summary_piece):
                continue

            events_response = lib.request(
                url=_events_url(self.settings, tracking_number, summary_piece),
                trace=_trace,
                method="GET",
                headers=self.settings.tracking_headers,
            )

            if events_response is None or not any(str(events_response).strip()):
                results[tracking_number] = tracking_data
                continue

            events_data = lib.to_dict(events_response)
            tracking_data["events"] = events_data

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

                    if (
                        isinstance(signature_payload, dict)
                        and signature_payload.get("mailPieces")
                    ):
                        tracking_data["signature"] = signature_payload

            results[tracking_number] = tracking_data

        return lib.Deserializable(
            [
                (tracking_number, results.get(tracking_number, {}))
                for tracking_number in tracking_numbers
            ],
            lambda pairs: [
                (tracking_number, response)
                for tracking_number, response in pairs
                if response is not None
            ],
        )
