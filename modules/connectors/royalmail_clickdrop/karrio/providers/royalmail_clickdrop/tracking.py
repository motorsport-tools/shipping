import base64
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
import karrio.schemas.royalmail_clickdrop.tracking_summary_response as tracking_summary_schema


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
            [
                *error.parse_tracking_error_response(
                    _summary_payload(response),
                    settings,
                    tracking_number=tracking_number,
                ),
                *error.parse_tracking_error_response(
                    _events_payload(response),
                    settings,
                    tracking_number=tracking_number,
                ),
            ]
            for tracking_number, response in responses
        ],
        start=[],
    )

    details = [
        _extract_detail(response, settings, tracking_number)
        for tracking_number, response in responses
        if _has_tracking_detail(response)
    ]

    return details, messages


def _format_tracking_time(value: typing.Optional[str]) -> typing.Optional[str]:
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").strftime("%I:%M %p")


def _summary_payload(response: dict) -> dict:
    if isinstance(response, dict) and "summary" in response:
        return response.get("summary") or {}

    return {}


def _events_payload(response: dict) -> dict:
    if isinstance(response, dict) and "events" in response:
        return response.get("events") or {}

    return response or {}


def _signature_payload(response: dict) -> typing.Optional[dict]:
    if isinstance(response, dict) and "signature" in response:
        return response.get("signature")

    return None


def _summary_mail_piece(data: dict):
    payload = _summary_payload(data)

    if not isinstance(payload, dict) or not payload.get("mailPieces"):
        return None

    pieces = lib.to_object(
        tracking_summary_schema.TrackingSummaryResponseType,
        payload,
    ).mailPieces or []

    return next((piece for piece in pieces if piece is not None), None)


def _has_tracking_detail(response: dict) -> bool:
    events_payload = _events_payload(response)
    if isinstance(events_payload, dict) and events_payload.get("mailPieces"):
        return True

    summary_piece = _summary_mail_piece(response)
    if summary_piece is None:
        return False

    if getattr(summary_piece, "error", None) is not None:
        return False

    return getattr(summary_piece, "summary", None) is not None


def _encode_pod_image(
    image: typing.Optional[str],
    image_format: typing.Optional[str] = None,
) -> typing.Optional[str]:
    if not image:
        return None

    mime_type = (image_format or "").lower()
    normalized_image = str(image).strip()

    if "svg" in mime_type or normalized_image.startswith("<svg"):
        return base64.b64encode(normalized_image.encode("utf-8")).decode("utf-8")

    return normalized_image


def _extract_tracking_images(proof) -> typing.Optional[models.Images]:
    signature_image = (
        _encode_pod_image(
            getattr(proof, "image", None),
            getattr(proof, "imageFormat", None),
        )
        if proof
        else None
    )

    if not signature_image:
        return None

    return models.Images(signature_image=signature_image)


def _extract_tracking_meta(proof) -> typing.Optional[dict]:
    if proof is None:
        return None

    image_format = getattr(proof, "imageFormat", None)
    signature_image = _encode_pod_image(
        getattr(proof, "image", None),
        image_format,
    )

    metadata = {
        "proof_of_delivery": {
            "type": "signature",
            "image_format": image_format,
            "image_id": getattr(proof, "imageId", None),
            "recipient_name": getattr(proof, "recipientName", None),
            "signed_at": getattr(proof, "signatureDateTime", None),
            "base64": signature_image,
            "data_uri": (
                f"data:{image_format};base64,{signature_image}"
                if image_format and signature_image
                else None
            ),
        }
    }

    proof_data = metadata["proof_of_delivery"]
    if not any(value is not None for value in proof_data.values()):
        return None

    return metadata


def _extract_summary_event(summary) -> typing.Optional[models.TrackingEvent]:
    event_code = getattr(summary, "lastEventCode", None)
    event_name = getattr(summary, "lastEventName", None)
    event_datetime = getattr(summary, "lastEventDateTime", None)
    event_location = getattr(summary, "lastEventLocationName", None)

    if not any([event_code, event_name, event_datetime, event_location]):
        return None

    return models.TrackingEvent(
        code=event_code,
        description=event_name or "",
        location=event_location,
        date=lib.fdate(event_datetime, "%Y-%m-%dT%H:%M:%S%z") if event_datetime else None,
        time=_format_tracking_time(event_datetime) if event_datetime else None,
        timestamp=(
            lib.fiso_timestamp(event_datetime, current_format="%Y-%m-%dT%H:%M:%S%z")
            if event_datetime
            else None
        ),
        reason=next(
            (
                reason.name
                for reason in list(provider_units.TrackingIncidentReason)
                if event_code in reason.value
            ),
            None,
        ),
    )


def _extract_detail(
    data: dict,
    settings: provider_utils.Settings,
    fallback_tracking_number: str,
) -> models.TrackingDetails:
    events_payload = _events_payload(data)
    signature_payload = _signature_payload(data)
    summary_piece = _summary_mail_piece(data)

    detail = (
        lib.to_object(
            tracking_response_schema.TrackingEventsResponseType,
            events_payload,
        ).mailPieces
        if isinstance(events_payload, dict) and events_payload.get("mailPieces")
        else None
    ) or tracking_response_schema.MailPiecesType()

    signature_mail_piece = None
    if isinstance(signature_payload, dict) and signature_payload.get("mailPieces"):
        signature_mail_piece = (
            lib.to_object(
                tracking_signature_schema.TrackingSignatureResponseType,
                signature_payload,
            ).mailPieces
            or tracking_signature_schema.MailPiecesType()
        )

    summary = (
        detail.summary
        or (summary_piece.summary if summary_piece and summary_piece.summary else None)
        or tracking_response_schema.SummaryType()
    )
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

    if not any(tracking_events):
        summary_event = _extract_summary_event(summary)
        if summary_event is not None:
            tracking_events.append(summary_event)

    pod_event = _extract_pod_event(proof)
    if pod_event is not None and not any(
        e.timestamp == pod_event.timestamp and e.code == pod_event.code
        for e in tracking_events
    ):
        tracking_events.append(pod_event)

    tracking_info = _extract_tracking_info(proof)
    tracking_images = _extract_tracking_images(proof)
    tracking_meta = _extract_tracking_meta(proof)

    return models.TrackingDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        tracking_number=(
            detail.mailPieceId
            or getattr(summary_piece, "mailPieceId", None)
            or fallback_tracking_number
        ),
        delivered=(
            pod_event is not None
            or "delivered" in ((getattr(summary, "lastEventName", None) or "").lower())
            or (getattr(summary, "statusCategory", None) or "").upper() == "DELIVERED"
        ),
        estimated_delivery=(
            lib.fdate(estimated_delivery.date, "%Y-%m-%d")
            if estimated_delivery and estimated_delivery.date
            else None
        ),
        events=tracking_events,
        info=tracking_info,
        images=tracking_images,
        meta=tracking_meta,
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