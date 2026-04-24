"""Karrio Royal Mail Click and Drop order and diagnostics query helpers."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.order_details_response as order_details_res
import karrio.schemas.royalmail_clickdrop.order_info_response as order_info_res
import karrio.schemas.royalmail_clickdrop.orders_details_response as orders_details_res
import karrio.schemas.royalmail_clickdrop.orders_response as orders_res
import karrio.schemas.royalmail_clickdrop.return_services_response as return_services_res
import karrio.schemas.royalmail_clickdrop.version_response as version_res


def empty_request(
    payload: typing.Any,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    return lib.Serializable({}, lambda data: data)


def order_lookup_request(
    payload: typing.Any,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    reference = None if isinstance(payload, (str, int, list, tuple, set)) else provider_utils.get_value(payload, "reference")
    order_identifiers = (
        payload
        if isinstance(payload, (str, int, list, tuple, set))
        else provider_utils.get_value(payload, "order_identifiers")
        or provider_utils.get_value(payload, "orderIdentifiers")
        or provider_utils.get_value(payload, "shipment_identifier")
        or provider_utils.get_value(payload, "shipmentIdentifier")
        or reference
    )

    resolved_order_identifiers = provider_utils.make_order_identifiers(
        order_identifiers,
        treat_numeric_as_reference=(
            reference not in [None, ""]
            and order_identifiers == reference
        ),
    )

    if not resolved_order_identifiers:
        raise ValueError(
            "Royal Mail Click & Drop order lookup requires "
            "`order_identifiers`, `orderIdentifiers`, `shipment_identifier`, or `reference`"
        )

    return lib.Serializable(
        {"orderIdentifiers": resolved_order_identifiers},
        lambda data: data,
    )

def orders_lookup_request(
    payload: typing.Any,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    page_size = provider_utils.get_value(payload, "page_size") or provider_utils.get_value(payload, "pageSize")
    start_date_time = (
        provider_utils.get_value(payload, "start_date_time")
        or provider_utils.get_value(payload, "startDateTime")
        or provider_utils.get_value(payload, "start_datetime")
    )
    end_date_time = (
        provider_utils.get_value(payload, "end_date_time")
        or provider_utils.get_value(payload, "endDateTime")
        or provider_utils.get_value(payload, "end_datetime")
    )
    continuation_token = (
        provider_utils.get_value(payload, "continuation_token")
        or provider_utils.get_value(payload, "continuationToken")
    )

    if page_size is not None:
        page_size = int(page_size)
        if page_size < 1 or page_size > 100:
            raise ValueError("Royal Mail Click & Drop page_size must be between 1 and 100")

    request = {
        "pageSize": page_size,
        "startDateTime": provider_utils.to_datetime_string(start_date_time),
        "endDateTime": provider_utils.to_datetime_string(end_date_time),
        "continuationToken": continuation_token,
    }

    return lib.Serializable(request, lambda data: data)


def parse_get_order_response(
    _response: lib.Deserializable[typing.Any],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[typing.List[order_info_res.OrderInfoResponseElementType]],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="get_order",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, list):
        return [], []

    orders = [
        lib.to_object(order_info_res.OrderInfoResponseElementType, item)
        for item in response
        if isinstance(item, dict)
    ]

    return orders, []


def parse_list_orders_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[orders_res.OrdersResponseType],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="generic",
        operation="list_orders",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, dict):
        return None, []

    data = lib.to_object(orders_res.OrdersResponseType, response)

    return data, []


def parse_get_order_details_response(
    _response: lib.Deserializable[typing.Any],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[typing.List[order_details_res.OrderDetailsResponseElementType]],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="get_order_details",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, list):
        return [], []

    orders = [
        lib.to_object(order_details_res.OrderDetailsResponseElementType, item)
        for item in response
        if isinstance(item, dict)
    ]

    return orders, []


def parse_list_order_details_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[orders_details_res.OrdersDetailsResponseType],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="generic",
        operation="list_order_details",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, dict):
        return None, []

    data = lib.to_object(orders_details_res.OrdersDetailsResponseType, response)

    return data, []


def parse_get_return_services_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[return_services_res.ReturnServicesResponseType],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="generic",
        operation="get_return_services",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, dict):
        return None, []

    data = lib.to_object(return_services_res.ReturnServicesResponseType, response)

    return data, []


def parse_get_version_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[version_res.VersionResponseType],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="generic",
        operation="get_version",
    )

    if any(messages):
        return None, messages

    if not isinstance(response, dict):
        return None, []

    data = lib.to_object(version_res.VersionResponseType, response)

    return data, []