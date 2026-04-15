"""Karrio Royal Mail Click and Drop client mapper."""

import typing
import karrio.lib as lib
import karrio.api.mapper as mapper
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop as provider
import karrio.mappers.royalmail_clickdrop.settings as provider_settings
import karrio.universal.providers.rating as universal_provider


class Mapper(mapper.Mapper):
    settings: provider_settings.Settings

    def create_rate_request(self, payload: models.RateRequest) -> lib.Serializable:
        return universal_provider.rate_request(payload, self.settings)

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

    # carrier-specific helpers
    def create_label_request(self, payload) -> lib.Serializable:
        return provider.label_request(payload, self.settings)

    def create_order_status_request(self, payload) -> lib.Serializable:
        return provider.order_status_request(payload, self.settings)

    def parse_cancel_shipment_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[models.ConfirmationDetails, typing.List[models.Message]]:
        return provider.parse_shipment_cancel_response(response, self.settings)

    def parse_shipment_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        return provider.parse_shipment_response(response, self.settings)

    def parse_return_shipment_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        return provider.parse_return_shipment_response(response, self.settings)

    def parse_manifest_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[models.ManifestDetails, typing.List[models.Message]]:
        return provider.parse_manifest_response(response, self.settings)

    # carrier-specific helpers
    def parse_label_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[models.Documents], typing.List[models.Message]]:
        return provider.parse_label_response(response, self.settings)

    def parse_order_status_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[typing.Optional[models.ConfirmationDetails], typing.List[models.Message]]:
        return provider.parse_order_status_response(response, self.settings)

    def parse_rate_response(
        self, response: lib.Deserializable[str]
    ) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
        return universal_provider.parse_rate_response(response, self.settings)
 