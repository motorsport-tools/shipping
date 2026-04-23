import typing
from datetime import datetime

import karrio.core.models as models
import karrio.lib as lib

import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.tracking_events_request as tracking_request_schema
import karrio.schemas.royalmail_clickdrop.tracking_events_response as tracking_response_schema
import karrio.schemas.royalmail_clickdrop.tracking_signature_response as tracking_signature_schema


def tracking_request(
    payload: models.TrackingRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    requests = [
        tracking_request_schema.TrackingEventsRequestType(mailPieceId=tracking_number)
        for tracking_number in (payload.tracking_numbers or [])
        if tracking_number is not None and str(tracking_number).strip() != ""
    ]

    return lib.Serializable(
        requests,
        lambda items: [item.mailPieceId for item in items if item.mailPieceId],
    )


def parse_tracking_response(
    _response: lib.Deserializable[typing.List[typing.Tuple[str, dict]]],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[models.TrackingDetails], typing.List[models.Message]]:
    responses = _response.deserialize()

    messages = sum(
        [
            error.parse_tracking_error_response(
                _events_payload(response),
                settings,
                tracking_number=tracking_number,
            )
            for tracking_number, response in responses
        ],
        start=[],
    )

    details = [
        _extract_detail(response, settings, tracking_number)
        for tracking_number, response in responses
        if isinstance(_events_payload(response), dict)
        and _events_payload(response).get("mailPieces")
    ]

    return details, messages

def _format_tracking_time(value: typing.Optional[str]) -> typing.Optional[str]:
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").strftime("%I:%M %p")

def _events_payload(response: dict) -> dict:
    if isinstance(response, dict) and "events" in response:
        return response.get("events") or {}

    return response or {}


def _signature_payload(response: dict) -> typing.Optional[dict]:
    if isinstance(response, dict) and "signature" in response:
        return response.get("signature")

    return None


def _extract_detail(
    data: dict,
    settings: provider_utils.Settings,
    fallback_tracking_number: str,
) -> models.TrackingDetails:
    events_payload = _events_payload(data)
    signature_payload = _signature_payload(data)

    detail = lib.to_object(
        tracking_response_schema.TrackingEventsResponseType,
        events_payload,
    ).mailPieces or tracking_response_schema.MailPiecesType()

    signature_mail_piece = None
    if isinstance(signature_payload, dict) and signature_payload.get("mailPieces"):
        signature_mail_piece = (
            lib.to_object(
                tracking_signature_schema.TrackingSignatureResponseType,
                signature_payload,
            ).mailPieces
            or tracking_signature_schema.MailPiecesType()
        )

    summary = detail.summary or tracking_response_schema.SummaryType()
    estimated_delivery = detail.estimatedDelivery
    events = detail.events or []
    proof = (
        signature_mail_piece.signature
        if signature_mail_piece and signature_mail_piece.signature
        else detail.signature
    )

    tracking_events = [
        models.TrackingEvent(
            date=lib.fdate(event.eventDateTime, "%Y-%m-%dT%H:%M:%S%z")
            if event.eventDateTime
            else None,
            description=event.eventName or "",
            location=event.locationName,
            code=event.eventCode,
            time=_format_tracking_time(event.eventDateTime),
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
    ]

    pod_event = _extract_pod_event(proof)
    if pod_event is not None and not any(
        e.timestamp == pod_event.timestamp and e.code == pod_event.code
        for e in tracking_events
    ):
        tracking_events.append(pod_event)

    tracking_info = _extract_tracking_info(proof)

    return models.TrackingDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        tracking_number=detail.mailPieceId or fallback_tracking_number,
        delivered=(
            pod_event is not None
            or "delivered" in ((summary.lastEventName or "").lower())
            or (summary.statusCategory or "").upper() == "DELIVERED"
        ),
        estimated_delivery=(
            lib.fdate(estimated_delivery.date, "%Y-%m-%d")
            if estimated_delivery and estimated_delivery.date
            else None
        ),
        events=tracking_events,
        info=tracking_info,
    )


def _extract_pod_event(proof) -> typing.Optional[models.TrackingEvent]:
    if proof is None or not getattr(proof, "signatureDateTime", None):
        return None

    recipient_name = getattr(proof, "recipientName", None)
    description = "Proof of delivery captured"
    if recipient_name:
        description = f"Proof of delivery captured for {recipient_name}"

    return models.TrackingEvent(
        code="POD",
        description=description,
        date=lib.fdate(proof.signatureDateTime, "%Y-%m-%dT%H:%M:%S%z"),
        time=_format_tracking_time(proof.signatureDateTime),
        timestamp=lib.fiso_timestamp(
            proof.signatureDateTime,
            current_format="%Y-%m-%dT%H:%M:%S%z",
        ),
        status="delivered",
    )


def _extract_tracking_info(proof) -> typing.Optional[models.TrackingInfo]:
    recipient_name = getattr(proof, "recipientName", None) if proof else None

    if not recipient_name:
        return None

    return models.TrackingInfo(
        customer_name=recipient_name,
    )