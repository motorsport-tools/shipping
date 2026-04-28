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


def _serialise_fields(fields: typing.Iterable[dict]) -> typing.List[dict]:
    return [
        {
            "field": field.get("fieldName"),
            "value": field.get("value"),
        }
        for field in (fields or [])
        if isinstance(field, dict) and field.get("fieldName")
    ]


def _field_issue_message(
    field_name: typing.Optional[str],
    value: typing.Any = None,
) -> typing.Optional[str]:
    if not field_name:
        return None

    if value in [None, "", [], {}]:
        return f"field '{field_name}' is required"

    return f"field '{field_name}' has invalid value '{value}'"


def _compose_field_message(
    base_message: typing.Optional[str],
    field_name: typing.Optional[str] = None,
    value: typing.Any = None,
) -> str:
    issue = _field_issue_message(field_name, value)

    if issue and base_message:
        return f"{base_message} — {issue}"

    if issue:
        return issue

    return base_message or ""


def _compose_fields_summary_message(
    base_message: typing.Optional[str],
    fields: typing.Iterable[dict],
) -> str:
    field_names = [
        field.get("fieldName")
        for field in (fields or [])
        if isinstance(field, dict) and field.get("fieldName")
    ]

    if not any(field_names):
        return base_message or ""

    visible = field_names[:5]
    suffix = ", ..." if len(field_names) > 5 else ""
    summary = ", ".join(visible) + suffix

    if base_message:
        return f"{base_message} — check required fields: {summary}"

    return f"Check required fields: {summary}"


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
    details = {**kwargs}

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

    base_message = (
        item.get("errorMessage")
        or item.get("message")
        or item.get("description")
        or ""
    )

    return [
        _message(
            settings,
            code=(
                str(item.get("errorCode"))
                if item.get("errorCode") is not None
                else item.get("code") or "error"
            ),
            message=_compose_field_message(
                base_message,
                item.get("fieldName"),
                item.get("value"),
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
                        message=_compose_field_message(
                            item.get("errorMessage")
                            or item.get("message")
                            or item.get("description")
                            or "",
                            item.get("fieldName"),
                            item.get("value"),
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
            fields = [field for field in (item.get("fields") or []) if isinstance(field, dict)]
            serialised_fields = _serialise_fields(fields)

            summary_details = dict(order_details)
            if any(serialised_fields):
                summary_details["fields"] = serialised_fields

            messages.append(
                _message(
                    settings,
                    code=base_code,
                    message=_compose_fields_summary_message(base_message, fields),
                    details=summary_details,
                )
            )

            for field in fields:
                field_name = field.get("fieldName")
                field_value = field.get("value")

                messages.append(
                    _message(
                        settings,
                        code=base_code,
                        message=_compose_field_message(base_message, field_name, field_value),
                        details={
                            **order_details,
                            "field": field_name,
                            "value": field_value,
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

    messages: typing.List[models.Message] = []

    if any(key in response for key in ["httpCode", "httpMessage"]):
        details = dict(kwargs)

        if response.get("moreInformation"):
            details["information"] = response.get("moreInformation")

        if response.get("moreinformation"):
            details["information"] = response.get("moreinformation")

        if response.get("errors"):
            details["errors"] = response.get("errors")

        messages.append(
            _message(
                settings,
                code=str(response.get("httpCode") or "error"),
                message=response.get("httpMessage") or "Tracking error",
                details=details,
            )
        )

    if response.get("errors") and not any(
        key in response for key in ["httpCode", "httpMessage"]
    ):
        for item in response.get("errors") or []:
            if not isinstance(item, dict):
                continue

            messages.append(
                _message(
                    settings,
                    code=(
                        str(item.get("errorCode"))
                        if item.get("errorCode") is not None
                        else item.get("code") or "tracking_error"
                    ),
                    message=(
                        item.get("errorDescription")
                        or item.get("errorMessage")
                        or item.get("message")
                        or "Tracking error"
                    ),
                    details={
                        **kwargs,
                        "cause": item.get("errorCause"),
                        "resolution": item.get("errorResolution"),
                    },
                )
            )

    for item in response.get("mailPieces", []) or []:
        if not isinstance(item, dict) or not isinstance(item.get("error"), dict):
            continue

        item_error = item.get("error") or {}
        messages.append(
            _message(
                settings,
                code=item_error.get("errorCode") or str(item.get("status") or "error"),
                message=item_error.get("errorDescription") or "Tracking error",
                details={
                    **kwargs,
                    "tracking_number": item.get("mailPieceId") or kwargs.get("tracking_number"),
                    "status": item.get("status"),
                    "cause": item_error.get("errorCause"),
                    "resolution": item_error.get("errorResolution"),
                },
            )
        )

    return messages


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

    collection_messages = _parse_error_collection(
        response, settings, context=context, **kwargs
    )
    failed_order_messages = _parse_failed_orders(response, settings, **kwargs)

    messages.extend(collection_messages)
    messages.extend(failed_order_messages)

    # Only fall back to bland generic messages if no richer structure exists.
    if not any(messages):
        messages.extend(_parse_generic_error_dict(response, settings, **kwargs))

    return [m for m in messages if (m.code or m.message)]