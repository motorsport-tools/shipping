"""Karrio Royal Mail Click and Drop order status update implementation."""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.schemas.royalmail_clickdrop.order_status_request as status_req
import karrio.schemas.royalmail_clickdrop.order_status_response as status_res
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

def _validate_item(item: dict) -> None:
    has_identifier = item.get("orderIdentifier") is not None
    has_reference = item.get("orderReference") is not None

    if has_identifier == has_reference:
        raise ValueError(
            "Royal Mail Click & Drop order status items require exactly one of "
            "`orderIdentifier` or `orderReference`"
        )

    if (
        item.get("status") == "despatchedByOtherCourier"
        and item.get("trackingNumber") is not None
    ):
        missing = [
            field
            for field in ["despatchDate", "shippingCarrier", "shippingService"]
            if item.get(field) is None
        ]

        if any(missing):
            raise ValueError(
                "Royal Mail Click & Drop `despatchedByOtherCourier` updates with "
                f"`trackingNumber` also require: {', '.join(missing)}"
            )

def order_status_request(payload, settings: provider_utils.Settings) -> lib.Serializable:
    items = _get(payload, "items", []) or []

    if len(items) == 0:
        raise ValueError(
            "Royal Mail Click & Drop order status requests require at least one item"
        )

    if len(items) > 100:
        raise ValueError(
            "Royal Mail Click & Drop supports a maximum of 100 order status items"
        )

    normalized_items = [_normalize_item(item) for item in items]

    for item in normalized_items:
        _validate_item(item)

    request = status_req.OrderStatusRequestType(
        items=[status_req.ItemType(**item) for item in normalized_items]
    )

    return lib.Serializable(request, lib.to_dict)


def parse_order_status_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ConfirmationDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="update_order_status",
    )

    data = (
        lib.to_object(status_res.OrderStatusResponseType, response)
        if isinstance(response, dict)
        else status_res.OrderStatusResponseType()
    )

    updated_orders = data.updatedOrders or []
    has_updated_orders = len(updated_orders) > 0

    confirmation = (
        models.ConfirmationDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            operation="Update Order Status",
            success=len(messages) == 0,
        )
        if has_updated_orders
        else None
    )

    return confirmation, messages