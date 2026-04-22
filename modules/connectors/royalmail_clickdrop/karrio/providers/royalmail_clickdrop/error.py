"""Karrio Royal Mail Click and Drop error parser."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.error_response as generic_error
import karrio.schemas.royalmail_clickdrop.label_error_response as label_error
import karrio.schemas.royalmail_clickdrop.manifest_error_response as manifest_error


def _message(
    settings: provider_utils.Settings,
    code: typing.Optional[str] = None,
    message: typing.Optional[str] = None,
    details: typing.Optional[dict] = None,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code=code or "",
        message=message or "",
        details={k: v for k, v in (details or {}).items() if v is not None},
    )


def _is_error_item(item: typing.Any) -> bool:
    return isinstance(item, dict) and any(
        key in item
        for key in [
            "code",
            "message",
            "description",
            "details",
            "errorCode",
            "errorMessage",
            "errors",
            "error",
            "failedOrders",
        ]
    )


def _parse_generic_error_dict(
    response: dict,
    settings: provider_utils.Settings,
    **kwargs,
) -> typing.List[models.Message]:
    if isinstance(response.get("error"), dict):
        response = response["error"]

    if not any(key in response for key in ["code", "message", "description", "details"]):
        return []

    data = lib.to_object(generic_error.ErrorResponseType, response)

    # Generic endpoint errors do not usually include order-level identifiers,
    # so we start with parser context from kwargs, such as
    # `operation="create_return_shipment"`.
    details = {**kwargs}

    # Preserve the carrier-provided top-level `details` field when present.
    # Royal Mail uses this for extra diagnostic text on some endpoints,
    # including return shipment creation errors.
    if data.details not in [None, "", [], {}]:
        details["details"] = data.details

    return [
        _message(
            settings,
            code=data.code or "error",
            message=data.message or response.get("description") or "",
            details=details,
        )
    ]

def _parse_order_error_item(
    item: dict,
    settings: provider_utils.Settings,
    **kwargs,
) -> typing.List[models.Message]:
    if not isinstance(item, dict) or not any(
        key in item for key in ["code", "message", "description", "errorCode", "errorMessage"]
    ):
        return []

    details = dict(kwargs)

    if any(key in item for key in ["accountOrderNumber", "channelOrderReference"]):
        data = lib.to_object(label_error.LabelErrorResponseElementType, item)
        details.update(
            account_order_number=data.accountOrderNumber,
            channel_order_reference=data.channelOrderReference,
        )

        return [
            _message(
                settings,
                code=data.code or "error",
                message=data.message or "",
                details=details,
            )
        ]

    details.update(
        order_identifier=item.get("orderIdentifier"),
        order_reference=item.get("orderReference"),
        account_order_number=item.get("accountOrderNumber"),
        channel_order_reference=item.get("channelOrderReference"),
        field=item.get("fieldName"),
        value=item.get("value"),
    )

    return [
        _message(
            settings,
            code=(
                str(item.get("errorCode"))
                if item.get("errorCode") is not None
                else item.get("code") or "error"
            ),
            message=(
                item.get("errorMessage")
                or item.get("message")
                or item.get("description")
                or ""
            ),
            details=details,
        )
    ]


def _parse_error_collection(
    response: dict,
    settings: provider_utils.Settings,
    context: str = "generic",
    **kwargs,
) -> typing.List[models.Message]:
    messages: typing.List[models.Message] = []

    if context == "manifest" and isinstance(response.get("errors"), list):
        data = lib.to_object(manifest_error.ManifestErrorResponseType, response)

        for item in data.errors or []:
            messages.append(
                _message(
                    settings,
                    code=item.code or "manifest_error",
                    message=item.description or "",
                    details={**kwargs},
                )
            )

        return messages

    for item in response.get("errors", []) or []:
        if context in ["order", "label"]:
            messages.extend(_parse_order_error_item(item, settings, **kwargs))
            continue

        if isinstance(item, dict):
            item_messages = _parse_order_error_item(item, settings, **kwargs)
            if not any(item_messages):
                item_messages = _parse_generic_error_dict(item, settings, **kwargs)

            if not any(item_messages) and any(
                key in item for key in ["errorCode", "errorMessage", "description"]
            ):
                item_messages = [
                    _message(
                        settings,
                        code=(
                            str(item.get("errorCode"))
                            if item.get("errorCode") is not None
                            else item.get("code") or "error"
                        ),
                        message=(
                            item.get("errorMessage")
                            or item.get("message")
                            or item.get("description")
                            or ""
                        ),
                        details={**kwargs},
                    )
                ]

            messages.extend(item_messages)
            continue

        messages.append(
            _message(
                settings,
                code="error",
                message=str(item),
                details={**kwargs},
            )
        )

    return messages


def _parse_failed_orders(
    response: dict,
    settings: provider_utils.Settings,
    **kwargs,
) -> typing.List[models.Message]:
    messages: typing.List[models.Message] = []

    for failed in response.get("failedOrders", []) or []:
        if not isinstance(failed, dict):
            continue

        order = failed.get("order", {}) or {}
        order_details = {
            **kwargs,
            "order_reference": order.get("orderReference"),
        }

        for item in failed.get("errors", []) or []:
            if not isinstance(item, dict):
                continue

            base_code = (
                str(item.get("errorCode"))
                if item.get("errorCode") is not None
                else item.get("code") or "error"
            )
            base_message = (
                item.get("errorMessage")
                or item.get("message")
                or item.get("description")
                or ""
            )
            messages.append(
                _message(
                    settings,
                    code=base_code,
                    message=base_message,
                    details=order_details,
                )
            )

            for field in item.get("fields", []) or []:
                if isinstance(field, dict):
                    messages.append(
                        _message(
                            settings,
                            code=base_code,
                            message=base_message,
                            details={
                                **order_details,
                                "field": field.get("fieldName"),
                                "value": field.get("value"),
                            },
                        )
                    )

    return messages

def parse_tracking_error_response(
    response: dict,
    settings: provider_utils.Settings,
    **kwargs,
) -> typing.List[models.Message]:
    if not isinstance(response, dict):
        return []

    if not any(key in response for key in ["httpCode", "httpMessage"]):
        return []

    details = dict(kwargs)

    if response.get("moreInformation"):
        details["information"] = response.get("moreInformation")

    if response.get("errors"):
        details["errors"] = response.get("errors")

    return [
        _message(
            settings,
            code=str(response.get("httpCode") or "error"),
            message=response.get("httpMessage") or "Tracking error",
            details=details,
        )
    ]

def parse_error_response(
    response: typing.Any,
    settings: provider_utils.Settings,
    context: str = "generic",
    **kwargs,
) -> typing.List[models.Message]:
    messages: typing.List[models.Message] = []

    if response is None:
        return messages

    if isinstance(response, (bytes, bytearray)):
        try:
            response = lib.to_dict(bytes(response).decode("utf-8-sig"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return [
                _message(
                    settings,
                    code="error",
                    message="Unable to parse carrier response",
                    details={**kwargs},
                )
            ]

    if isinstance(response, str):
        try:
            response = lib.to_dict(response)
        except (TypeError, ValueError):
            return [
                _message(
                    settings,
                    code="error",
                    message=response,
                    details={**kwargs},
                )
            ]

    if isinstance(response, list):
        if context in ["order", "label"]:
            if not any(_is_error_item(item) for item in response):
                return []

            for item in response:
                messages.extend(_parse_order_error_item(item, settings, **kwargs))

            return [m for m in messages if (m.code or m.message)]

        for item in response:
            messages.extend(parse_error_response(item, settings, context=context, **kwargs))

        return [m for m in messages if (m.code or m.message)]

    if not isinstance(response, dict):
        return [
            _message(
                settings,
                code="error",
                message=str(response),
                details={**kwargs},
            )
        ]

    messages.extend(_parse_generic_error_dict(response, settings, **kwargs))
    messages.extend(_parse_error_collection(response, settings, context=context, **kwargs))
    messages.extend(_parse_failed_orders(response, settings, **kwargs))

    return [m for m in messages if (m.code or m.message)]