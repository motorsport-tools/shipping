"""Karrio Royal Mail Click and Drop shipment cancellation API implementation."""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils


def _extract_order_identifiers(payload: models.ShipmentCancelRequest):
    return payload.shipment_identifier


def parse_shipment_cancel_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ConfirmationDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    deleted_orders = response.get("deletedOrders", []) if isinstance(response, dict) else []
    success = len(deleted_orders) > 0 and len(messages) == 0

    confirmation = (
        models.ConfirmationDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            operation="Cancel Shipment",
            success=success,
        )
        if success
        else None
    )

    return confirmation, messages


def shipment_cancel_request(
    payload: models.ShipmentCancelRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    order_identifiers = provider_utils.make_order_identifiers(_extract_order_identifiers(payload))

    return lib.Serializable(
        {"orderIdentifiers": order_identifiers},
        lambda data: data,
    )
