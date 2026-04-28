"""Karrio Royal Mail Click and Drop order status update implementation."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.order_status_request as status_req
import karrio.schemas.royalmail_clickdrop.order_status_response as status_res


ALLOWED_ORDER_STATUSES = {
    "new",
    "despatched",
    "despatchedByOtherCourier",
}


def _normalize_item(item: typing.Any) -> dict:
    result = {
        "orderIdentifier": provider_utils.get_value(item, "orderIdentifier")
        or provider_utils.get_value(item, "order_identifier"),
        "orderReference": provider_utils.get_value(item, "orderReference")
        or provider_utils.get_value(item, "order_reference"),
        "status": provider_utils.get_value(item, "status"),
        "trackingNumber": provider_utils.get_value(item, "trackingNumber")
        or provider_utils.get_value(item, "tracking_number"),
        "despatchDate": provider_utils.to_datetime_string(
            provider_utils.get_value(item, "despatchDate")
            or provider_utils.get_value(item, "despatch_date")
        ),
        "shippingCarrier": provider_utils.get_value(item, "shippingCarrier")
        or provider_utils.get_value(item, "shipping_carrier"),
        "shippingService": provider_utils.get_value(item, "shippingService")
        or provider_utils.get_value(item, "shipping_service"),
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

    status = item.get("status")
    if status not in ALLOWED_ORDER_STATUSES:
        raise ValueError(
            "Royal Mail Click & Drop `status` must be one of "
            "`new`, `despatched`, or `despatchedByOtherCourier`"
        )

    if (
        status == "despatchedByOtherCourier"
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
    items = provider_utils.get_value(payload, "items", []) or []

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

    request_data = provider_utils.clean_payload(lib.to_dict(request)) or {}

    return lib.Serializable(request_data, lambda data: data)


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