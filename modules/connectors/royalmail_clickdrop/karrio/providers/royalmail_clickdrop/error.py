"""Karrio Royal Mail Click and Drop error parser."""

import typing
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.utils as provider_utils


def _message(
    settings: provider_utils.Settings,
    code: str = None,
    message: str = None,
    details: dict = None,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code=code or "",
        message=message or "",
        details=details or {},
    )


def parse_error_response(
    response: typing.Any,
    settings: provider_utils.Settings,
    **kwargs,
) -> typing.List[models.Message]:
    messages: typing.List[models.Message] = []

    if response is None:
        return messages

    if isinstance(response, list):
        for item in response:
            messages.extend(parse_error_response(item, settings, **kwargs))
        return messages

    if not isinstance(response, dict):
        return [
            _message(
                settings,
                code="error",
                message=str(response),
                details={**kwargs},
            )
        ]

    # Handle nested {"error": {...}}
    if isinstance(response.get("error"), dict):
        err = response["error"]
        messages.append(
            _message(
                settings,
                code=err.get("code"),
                message=err.get("message") or err.get("description"),
                details={"details": err.get("details"), **kwargs}
                if err.get("details") is not None or kwargs
                else {},
            )
        )

    # Handle generic top-level error object
    elif any(k in response for k in ["code", "message", "details", "description"]):
        messages.append(
            _message(
                settings,
                code=response.get("code"),
                message=response.get("message") or response.get("description"),
                details={"details": response.get("details"), **kwargs}
                if response.get("details") is not None or kwargs
                else {},
            )
        )

    # Handle {"errors": [...]}
    for item in response.get("errors", []) or []:
        if not isinstance(item, dict):
            messages.append(_message(settings, code="error", message=str(item), details={**kwargs}))
            continue

        details = {**kwargs}
        if item.get("orderIdentifier") is not None:
            details["order_identifier"] = item.get("orderIdentifier")
        if item.get("orderReference") is not None:
            details["order_reference"] = item.get("orderReference")
        if item.get("accountOrderNumber") is not None:
            details["account_order_number"] = item.get("accountOrderNumber")
        if item.get("channelOrderReference") is not None:
            details["channel_order_reference"] = item.get("channelOrderReference")

        messages.append(
            _message(
                settings,
                code=item.get("code") or item.get("errorCode"),
                message=item.get("message") or item.get("errorMessage") or item.get("description"),
                details=details,
            )
        )

    # Handle create order failedOrders
    for failed in response.get("failedOrders", []) or []:
        if not isinstance(failed, dict):
            continue

        order = failed.get("order", {}) or {}
        for item in failed.get("errors", []) or []:
            if not isinstance(item, dict):
                continue

            details = {**kwargs}
            if order.get("orderReference") is not None:
                details["order_reference"] = order.get("orderReference")

            messages.append(
                _message(
                    settings,
                    code=str(item.get("errorCode")) if item.get("errorCode") is not None else "",
                    message=item.get("errorMessage"),
                    details=details,
                )
            )

            for field in item.get("fields", []) or []:
                if isinstance(field, dict):
                    messages.append(
                        _message(
                            settings,
                            code=str(item.get("errorCode")) if item.get("errorCode") is not None else "",
                            message=item.get("errorMessage"),
                            details={
                                **details,
                                "field": field.get("fieldName"),
                                "value": field.get("value"),
                            },
                        )
                    )

    return [m for m in messages if (m.code or m.message)]
