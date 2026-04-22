import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.tracking_response as tracking_schema


def tracking_request(
    payload: models.TrackingRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    return lib.Serializable(payload.tracking_numbers)


def parse_tracking_response(
    _response: lib.Deserializable[typing.List[typing.Tuple[str, dict]]],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[models.TrackingDetails], typing.List[models.Message]]:
    responses = _response.deserialize()

    messages = sum(
        [
            error.parse_tracking_error_response(
                response,
                settings,
                tracking_number=tracking_number,
            )
            for tracking_number, response in responses
        ],
        start=[],
    )

    details = [
        _extract_detail(response["mailPieces"], settings, tracking_number)
        for tracking_number, response in responses
        if isinstance(response, dict) and response.get("mailPieces")
    ]

    return details, messages


def _extract_detail(
    data: dict,
    settings: provider_utils.Settings,
    fallback_tracking_number: str,
) -> models.TrackingDetails:
    detail = lib.to_object(tracking_schema.MailPieces, data)
    summary = detail.summary or tracking_schema.Summary()
    estimated_delivery = detail.estimatedDelivery
    events = detail.events or []

    return models.TrackingDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        tracking_number=detail.mailPieceId or fallback_tracking_number,
        delivered=(
            "delivered" in ((summary.lastEventName or "").lower())
            or (summary.statusCategory or "").upper() == "DELIVERED"
        ),
        estimated_delivery=(
            lib.fdate(estimated_delivery.date, "%Y-%m-%d")
            if estimated_delivery and estimated_delivery.date
            else None
        ),
        events=[
            models.TrackingEvent(
                date=lib.fdate(event.eventDateTime, "%Y-%m-%dT%H:%M:%S%z")
                if event.eventDateTime
                else None,
                description=event.eventName or "",
                location=event.locationName,
                code=event.eventCode,
                time=lib.flocaltime(event.eventDateTime, "%Y-%m-%dT%H:%M:%S%z")
                if event.eventDateTime
                else None,
                timestamp=lib.fiso_timestamp(
                    event.eventDateTime,
                    current_format="%Y-%m-%dT%H:%M:%S%z",
                )
                if event.eventDateTime
                else None,
                reason=next(
                    (
                        reason.name
                        for reason in list(provider_units.TrackingIncidentReason)
                        if event.eventCode in reason.value
                    ),
                    None,
                ),
            )
            for event in events
        ],
    )