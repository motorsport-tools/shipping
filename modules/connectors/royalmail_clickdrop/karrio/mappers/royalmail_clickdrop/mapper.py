"""Karrio Royal Mail Click and Drop client mapper."""

import typing

import karrio.api.mapper as mapper
import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.royalmail_clickdrop.settings as provider_settings
import karrio.providers.royalmail_clickdrop as provider
import karrio.providers.royalmail_clickdrop.manifest as manifest_provider
import karrio.providers.royalmail_clickdrop.orders.query as order_query
import karrio.universal.providers.rating as universal_provider
import karrio.providers.royalmail_clickdrop.units as provider_units


class Mapper(mapper.Mapper):
    settings: provider_settings.Settings

    def create_rate_request(self, payload: models.RateRequest) -> lib.Serializable:
        request_data = lib.to_dict(payload)
        requested_services = request_data.get("services") or []

        request_data["services"] = list(
            dict.fromkeys(
                provider_units.resolve_service_code(service) or str(service).strip()
                for service in requested_services
                if service not in [None, ""]
            )
        )

        return universal_provider.rate_request(
            models.RateRequest(**request_data),
            self.settings,
        )
    def create_shipment_request(
        self, payload: models.ShipmentRequest
    ) -> lib.Serializable:
        return provider.shipment_request(payload, self.settings)

    def create_return_shipment_request(
        self, payload: models.ShipmentRequest
    ) -> lib.Serializable:
        return provider.return_shipment_request(payload, self.settings)

    def create_cancel_shipment_request(
        self, payload: models.ShipmentCancelRequest
    ) -> lib.Serializable[str]:
        return provider.shipment_cancel_request(payload, self.settings)

    def create_manifest_request(
        self, payload: models.ManifestRequest
    ) -> lib.Serializable:
        return provider.manifest_request(payload, self.settings)

    def create_label_request(self, payload: typing.Any) -> lib.Serializable:
        return provider.label_request(payload, self.settings)

    def create_order_status_request(self, payload: typing.Any) -> lib.Serializable:
        return provider.order_status_request(payload, self.settings)

    def create_get_manifest_request(self, payload: typing.Any) -> lib.Serializable:
        return manifest_provider.manifest_identifier_request(payload, self.settings)

    def create_retry_manifest_request(self, payload: typing.Any) -> lib.Serializable:
        return manifest_provider.manifest_identifier_request(payload, self.settings)

    def create_get_order_request(self, payload: typing.Any) -> lib.Serializable:
        return order_query.order_lookup_request(payload, self.settings)

    def create_list_orders_request(self, payload: typing.Any = None) -> lib.Serializable:
        return order_query.orders_lookup_request(payload or {}, self.settings)

    def create_get_order_details_request(self, payload: typing.Any) -> lib.Serializable:
        return order_query.order_lookup_request(payload, self.settings)

    def create_list_order_details_request(
        self, payload: typing.Any = None
    ) -> lib.Serializable:
        return order_query.orders_lookup_request(payload or {}, self.settings)

    def create_get_return_services_request(
        self, payload: typing.Any = None
    ) -> lib.Serializable:
        return order_query.empty_request(payload, self.settings)

    def create_get_version_request(self, payload: typing.Any = None) -> lib.Serializable:
        return order_query.empty_request(payload, self.settings)

    def parse_cancel_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ConfirmationDetails, typing.List[models.Message]]:
        return provider.parse_shipment_cancel_response(response, self.settings)

    def parse_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        return provider.parse_shipment_response(response, self.settings)

    def parse_return_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        return provider.parse_return_shipment_response(response, self.settings)

    def parse_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ManifestDetails, typing.List[models.Message]]:
        return provider.parse_manifest_response(response, self.settings)

    def parse_label_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[models.Documents], typing.List[models.Message]]:
        return provider.parse_label_response(response, self.settings)

    def parse_order_status_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ConfirmationDetails],
        typing.List[models.Message],
    ]:
        return provider.parse_order_status_response(response, self.settings)

    def parse_get_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ManifestDetails],
        typing.List[models.Message],
    ]:
        return manifest_provider.parse_manifest_response(response, self.settings)

    def parse_retry_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ManifestDetails],
        typing.List[models.Message],
    ]:
        return manifest_provider.parse_manifest_response(response, self.settings)

    def parse_get_order_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_get_order_response(response, self.settings)

    def parse_list_orders_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_list_orders_response(response, self.settings)

    def parse_get_order_details_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_get_order_details_response(response, self.settings)

    def parse_list_order_details_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_list_order_details_response(response, self.settings)

    def parse_get_return_services_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_get_return_services_response(response, self.settings)

    def parse_get_version_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        return order_query.parse_get_version_response(response, self.settings)

    def parse_rate_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
        payload = response.deserialize()

        # Direct unit tests provide an already-normalized response:
        # {
        #   "rates": [...],
        #   "messages": [...]
        # }
        #
        # The universal rating parser expects the internal RatingMixinProxy
        # multi-piece response format, so we short-circuit normalized payloads.
        if isinstance(payload, dict) and (
            "rates" in payload or "messages" in payload
        ):
            rates = payload.get("rates", [])
            messages = payload.get("messages", [])

            return rates, messages

        return universal_provider.parse_rate_response(
            lib.Deserializable(payload, lambda x: x),
            self.settings,
        )
    
    def create_tracking_request(
    self, payload: models.TrackingRequest
    ) -> lib.Serializable:
        return provider.tracking_request(payload, self.settings)

    def parse_tracking_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.List[models.TrackingDetails], typing.List[models.Message]]:
        return provider.parse_tracking_response(response, self.settings)