"""Karrio Royal Mail Click and Drop client proxy."""

from urllib.parse import urlencode

import karrio.lib as lib
import karrio.api.proxy as proxy
import karrio.mappers.royalmail_clickdrop.settings as provider_settings
import karrio.universal.mappers.rating_proxy as rating_proxy


class Proxy(rating_proxy.RatingMixinProxy, proxy.Proxy):
    settings: provider_settings.Settings

    def get_rates(self, request: lib.Serializable) -> lib.Deserializable[str]:
        return super().get_rates(request)

    def create_shipment(self, request: lib.Serializable) -> lib.Deserializable[str]:
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
    ) -> lib.Deserializable[str]:
        response = lib.request(
            url=f"{self.settings.server_url}/returns",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def cancel_shipment(self, request: lib.Serializable) -> lib.Deserializable[str]:
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}",
            trace=self.trace_as("json"),
            method="DELETE",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def create_manifest(self, request: lib.Serializable) -> lib.Deserializable[str]:
        response = lib.request(
            url=f"{self.settings.server_url}/manifests",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_label(self, request: lib.Serializable) -> lib.Deserializable:
        payload = request.serialize()
        query = {k: v for k, v in (payload.get("query") or {}).items() if v is not None}
        normalized_query = {
            k: (str(v).lower() if isinstance(v, bool) else v)
            for k, v in query.items()
        }
        qs = urlencode(normalized_query)

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

    def update_order_status(self, request: lib.Serializable) -> lib.Deserializable[str]:
        response = lib.request(
            url=f"{self.settings.server_url}/orders/status",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="PUT",
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
 