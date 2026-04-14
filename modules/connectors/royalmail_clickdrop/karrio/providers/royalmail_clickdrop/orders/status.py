"""Karrio Royal Mail Click and Drop order status update implementation."""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.schemas.royalmail_clickdrop.order_status_request as status_req
import karrio.providers.royalmail_clickdrop.utils as provider_utils


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default) if obj is not None else default


def _normalize_item(item: typing.Any) -> dict:
    result = {
        "orderIdentifier": _get(item, "orderIdentifier") or _get(item, "order_identifier"),
        "orderReference": _get(item, "orderReference") or _get(item, "order_reference"),
        "status": _get(item, "status"),
        "trackingNumber": _get(item, "trackingNumber") or _get(item, "tracking_number"),
        "despatchDate": _get(item, "despatchDate") or _get(item, "despatch_date"),
        "shippingCarrier": _get(item, "shippingCarrier") or _get(item, "shipping_carrier"),
        "shippingService": _get(item, "shippingService") or _get(item, "shipping_service"),
    }
    return {k: v for k, v in result.items() if v is not None}


def order_status_request(payload, settings: provider_utils.Settings) -> lib.Serializable:
    items = _get(payload, "items", []) or []

    request = status_req.OrderStatusRequestType(
        items=[status_req.ItemType(**_normalize_item(item)) for item in items]
    )

    return lib.Serializable(request, lib.to_dict)


def parse_order_status_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ConfirmationDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    updated_orders = response.get("updatedOrders", []) if isinstance(response, dict) else []
    success = len(updated_orders) > 0 and len(messages) == 0

    confirmation = (
        models.ConfirmationDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            operation="Update Order Status",
            success=success,
        )
        if success
        else None
    )

    return confirmation, messages
