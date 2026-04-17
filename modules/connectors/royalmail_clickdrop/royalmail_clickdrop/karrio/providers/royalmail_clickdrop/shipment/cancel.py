"""Karrio Royal Mail Click and Drop shipment cancellation API implementation."""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.cancel_response as cancel_res


def _extract_order_identifiers(payload: models.ShipmentCancelRequest):
    return payload.shipment_identifier


def parse_shipment_cancel_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ConfirmationDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings, context="order")

    data = (
        lib.to_object(cancel_res.CancelResponseType, response)
        if isinstance(response, dict)
        else cancel_res.CancelResponseType()
    )

    deleted_orders = data.deletedOrders or []
    has_deleted_orders = len(deleted_orders) > 0

    confirmation = (
        models.ConfirmationDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            operation="Cancel Shipment",
            success=len(messages) == 0,
        )
        if has_deleted_orders
        else None
    )

    return confirmation, messages


def shipment_cancel_request(
    payload: models.ShipmentCancelRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    order_identifiers = provider_utils.make_order_identifiers(
        _extract_order_identifiers(payload)
    )

    if not order_identifiers:
        raise ValueError(
            "Royal Mail Click & Drop cancel requests require `shipment_identifier`"
        )

    return lib.Serializable(
        {"orderIdentifiers": order_identifiers},
        lambda data: data,
    )