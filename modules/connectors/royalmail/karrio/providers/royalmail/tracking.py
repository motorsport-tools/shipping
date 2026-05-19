"""Karrio Royal Mail Click and Drop order Tracking implementation."""

import base64
import re
import typing
from datetime import datetime

import karrio.core.models as models
import karrio.lib as lib

import karrio.providers.royalmail.error as error
import karrio.providers.royalmail.units as provider_units
import karrio.providers.royalmail.utils as provider_utils
import karrio.schemas.royalmail.tracking_events_response as tracking_response_schema
import karrio.schemas.royalmail.tracking_signature_response as tracking_signature_schema
import karrio.schemas.royalmail.tracking_summary_response as tracking_summary_schema


TRACKING_DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
]

def tracking_request(
    payload: models.TrackingRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    """Build Royal Mail Tracking API and optional Click & Drop fallback requests."""
    tracking_numbers = [
        str(tracking_number).strip()
        for tracking_number in (payload.tracking_numbers or [])
        if tracking_number is not None and str(tracking_number).strip() != ""
    ]

    if len(tracking_numbers) == 0:
        raise ValueError("Royal Mail tracking requires at least one tracking number.")

    request = {
        "tracking_numbers": tracking_numbers,
        "reference": payload.reference,
        "options": payload.options or {},
    }

    return lib.Serializable(
        request,
        lambda data: (
            data
            if any([data.get("reference"), data.get("options")])
            else data["tracking_numbers"]
        ),
    )

def parse_tracking_response(
    _response: lib.Deserializable[typing.List[typing.Tuple[str, dict]]],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[models.TrackingDetails], typing.List[models.Message]]:
    """Parse tracking responses into Karrio TrackingDetails and messages."""
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
                *error.parse_error_response(
                    _click_and_drop_payload(response),
                    settings,
                    context="order",
                    operation="tracking",
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


def _parse_tracking_datetime(value: typing.Optional[str]) -> typing.Optional[datetime]:
    """Parse Royal Mail tracking date/time values into a datetime."""
    if not value:
        return None

    text = str(value).strip()

    for date_format in TRACKING_DATETIME_FORMATS:
        try:
            return datetime.strptime(text, date_format)
        except (TypeError, ValueError):
            continue

    return None


def _format_tracking_time(value: typing.Optional[str]) -> typing.Optional[str]:
    """Format a tracking datetime as a Karrio time string."""
    parsed = _parse_tracking_datetime(value)

    return parsed.strftime("%I:%M %p") if parsed is not None else None


def _format_tracking_date(value: typing.Optional[str]) -> typing.Optional[str]:
    """Format a tracking datetime as a Karrio date string."""
    return lib.fdate(
        value,
        current_format="%Y-%m-%dT%H:%M:%S%z",
        try_formats=TRACKING_DATETIME_FORMATS,
    )


def _format_tracking_timestamp(value: typing.Optional[str]) -> typing.Optional[str]:
    """Format a tracking datetime as a timestamp string."""
    return lib.fiso_timestamp(
        value,
        current_format="%Y-%m-%dT%H:%M:%S%z",
        try_formats=TRACKING_DATETIME_FORMATS,
    )


def _summary_payload(response: dict) -> dict:
    """Return the Tracking API summary payload from a response wrapper."""
    if isinstance(response, dict) and "summary" in response:
        return response.get("summary") or {}

    return {}


def _events_payload(response: dict) -> dict:
    """Return the Tracking API events payload from a response wrapper."""
    if isinstance(response, dict) and "events" in response:
        return response.get("events") or {}

    return response or {}


def _signature_payload(response: dict) -> typing.Optional[dict]:
    """Return the proof-of-delivery signature payload from a response wrapper."""
    if isinstance(response, dict) and "signature" in response:
        return response.get("signature")

    return None


def _click_and_drop_payload(response: dict) -> typing.Any:
    """Return the Click & Drop fallback payload from a response wrapper."""
    if isinstance(response, dict) and "click_and_drop" in response:
        return response.get("click_and_drop")

    return None


def _lookup_identifier(response: dict, fallback: str) -> str:
    """Return the identifier used for a Click & Drop tracking lookup."""
    if isinstance(response, dict) and response.get("lookup_identifier"):
        return str(response.get("lookup_identifier"))

    return fallback


def _summary_mail_piece(data: dict):
    """Return the first mail-piece summary from a Tracking API response."""
    payload = _summary_payload(data)

    if not isinstance(payload, dict) or not payload.get("mailPieces"):
        return None

    pieces = lib.to_object(
        tracking_summary_schema.TrackingSummaryResponseType,
        payload,
    ).mailPieces or []

    return next((piece for piece in pieces if piece is not None), None)


def _is_click_and_drop_order(data: typing.Any) -> bool:
    """Return whether a fallback payload contains Click & Drop order data."""
    if not isinstance(data, dict):
        return False

    return any(
        key in data
        for key in [
            "orderIdentifier",
            "orderReference",
            "orderStatus",
            "trackingNumber",
            "packages",
            "shippingDetails",
        ]
    )


def _has_click_and_drop_detail(response: dict) -> bool:
    """Return whether Click & Drop fallback details are available."""
    data = _click_and_drop_payload(response)
    if not _is_click_and_drop_order(data):
        return False

    shipping_details = data.get("shippingDetails") or {}

    return any(
        [
            data.get("trackingNumber"),
            shipping_details.get("trackingNumber"),
            shipping_details.get("shippingTrackingStatus"),
            data.get("orderStatus"),
        ]
    )


def _has_tracking_detail(response: dict) -> bool:
    """Return whether detailed Tracking API data is available."""
    if _has_click_and_drop_detail(response):
        return True

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
    """Base64-encode a proof-of-delivery image when present."""
    if not image:
        return None

    mime_type = (image_format or "").lower()
    normalized_image = str(image).strip()

    if "svg" in mime_type or normalized_image.startswith("<svg"):
        return base64.b64encode(normalized_image.encode("utf-8")).decode("utf-8")

    return normalized_image


def _extract_tracking_images(proof) -> typing.Optional[models.Images]:
    """Extract proof-of-delivery images from tracking responses."""
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
    """Extract Royal Mail tracking metadata for Karrio details."""
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
    """Build a fallback tracking event from summary status data."""
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
        date=_format_tracking_date(event_datetime),
        time=_format_tracking_time(event_datetime),
        timestamp=_format_tracking_timestamp(event_datetime),
        reason=_tracking_incident_reason(event_code, event_name),
        )
    


def _extract_detail(
    data: dict,
    settings: provider_utils.Settings,
    fallback_tracking_number: str,
) -> models.TrackingDetails:
    """Build Karrio tracking detail from Tracking API payloads."""
    if _has_click_and_drop_detail(data):
        return _extract_click_and_drop_detail(
            _click_and_drop_payload(data),
            settings,
            _lookup_identifier(data, fallback_tracking_number),
        )

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
            date=_format_tracking_date(event.eventDateTime),
            description=event.eventName or "",
            location=event.locationName,
            code=event.eventCode,
            time=_format_tracking_time(event.eventDateTime),
            timestamp=_format_tracking_timestamp(event.eventDateTime),
            reason=_tracking_incident_reason(event.eventCode, event.eventName),
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


CLICK_AND_DROP_STATUS_RULES = [
    {
        "status": "cancelled",
        "phrases": [
            "cancelled",
            "canceled",
            "void",
        ],
    },
    {
        "status": "return_to_sender",
        "phrases": [
            "return to sender",
            "returned to sender",
            "returning to sender",
            "being returned",
            "returned",
        ],
    },
    {
        "status": "delivery_failed",
        "phrases": [
            "delivery attempted",
            "attempted delivery",
            "attempted",
            "not delivered",
            "could not deliver",
            "couldn t deliver",
            "unable to deliver",
            "delivery failed",
            "failed delivery",
            "recipient not available",
            "no answer",
            "not home",
            "refused",
            "address problem",
            "incorrect address",
            "bad address",
            "inaccessible",
            "undeliverable",
        ],
    },
    {
        "status": "on_hold",
        "phrases": [
            "on hold",
            "held",
            "retention",
            "customs hold",
            "awaiting payment",
            "awaiting customs",
            "pending payment",
        ],
    },
    {
        "status": "delivery_delayed",
        "phrases": [
            "delayed",
            "delay",
            "disruption",
            "exception",
        ],
    },
    {
        "status": "ready_for_pickup",
        "phrases": [
            "ready for collection",
            "available for collection",
            "awaiting collection",
            "collect from",
            "collection point",
            "customer service point",
            "post office",
            "local collect",
        ],
    },
    {
        "status": "out_for_delivery",
        "phrases": [
            "out for delivery",
            "due to be delivered",
            "due for delivery",
            "with delivery courier",
            "with your delivery driver",
            "delivery today",
        ],
    },
    {
        "status": "delivered",
        "phrases": [
            "delivered",
            "signed for",
            "proof of delivery",
            "delivered and signed",
            "delivered to",
        ],
    },
    {
        "status": "in_transit",
        "phrases": [
            "in transit",
            "transit",
            "we ve got it",
            "we have got it",
            "received by royal mail",
            "accepted",
            "collected from sender",
            "collected",
            "despatched",
            "dispatched",
            "manifested",
            "shipped",
            "sorted",
            "arrived",
            "departed",
            "forwarded",
            "processed",
            "mail centre",
            "delivery office",
        ],
    },
    {
        "status": "pending",
        "phrases": [
            "new",
            "created",
            "printed",
            "label",
            "postage",
            "postage applied",
            "pre advice",
            "pre advised",
            "pre advised",
            "sender preparing",
            "preparing item",
            "pending",
        ],
    },
]

def _tracking_incident_reason(
    event_code: typing.Optional[str],
    event_name: typing.Optional[str] = None,
) -> typing.Optional[str]:
    """Resolve a Royal Mail tracking event into a normalized Karrio reason."""
    event_code = str(event_code or "").strip()
    event_name_text = _normalize_status_text(event_name)

    incident_reason_enum = getattr(provider_units, "TrackingIncidentReason", None)

    code_reason = (
        next(
            (
                reason.name
                for reason in list(incident_reason_enum)
                if event_code in reason.value
            ),
            None,
        )
        if incident_reason_enum is not None
        else None
    )

    if code_reason is not None:
        return code_reason

    # Text fallback for Royal Mail event names where the code is unknown or new.
    text_rules = [
        (
            "carrier_sorting_error",
            [
                "mis sort",
                "missort",
                "misroute",
                "mis routed",
                "sorting error",
            ],
        ),
        (
            "consignee_not_home",
            [
                "redelivery",
                "ready for collection",
                "no answer",
                "not home",
                "delivery attempted",
            ],
        ),
        (
            "consignee_refused",
            [
                "refused",
            ],
        ),
        (
            "consignee_incorrect_address",
            [
                "incorrect address",
                "bad address",
                "address problem",
            ],
        ),
        (
            "consignee_access_restricted",
            [
                "no access",
                "access restricted",
                "inaccessible",
            ],
        ),
        (
            "customs_delay",
            [
                "customs",
                "customs hold",
                "awaiting customs",
            ],
        ),
        (
            "carrier_damaged_parcel",
            [
                "damaged",
            ],
        ),
        (
            "carrier_parcel_lost",
            [
                "lost",
            ],
        ),
        (
            "weather_delay",
            [
                "weather",
            ],
        ),
    ]

    return next(
        (
            reason
            for reason, phrases in text_rules
            if _contains_any(event_name_text, phrases)
        ),
        None,
    )

def _normalize_status_text(value: typing.Optional[str]) -> str:
    """Normalize free-text status values for matching."""
    text = str(value or "").strip()

    if text == "":
        return ""

    # Convert common camelCase values such as despatchedByOtherCourier.
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)

    # Normalize punctuation and apostrophes:
    # "couldn't deliver" -> "couldn t deliver"
    # "pre-advice" -> "pre advice"
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)

    return re.sub(r"\s+", " ", text).strip().lower()


def _contains_any(text: str, phrases: typing.Iterable[str]) -> bool:
    """Return whether text contains any of the supplied status tokens."""
    return any(phrase in text for phrase in phrases)


def _normalize_click_and_drop_status(
    status: typing.Optional[str],
) -> typing.Optional[str]:
    """Map Click & Drop order status text to Karrio tracking status."""
    text = _normalize_status_text(status)

    if text == "":
        return None

    for rule in CLICK_AND_DROP_STATUS_RULES:
        if _contains_any(text, rule["phrases"]):
            return rule["status"]

    return "unknown"


def _click_and_drop_status_reason(
    status: typing.Optional[str],
) -> typing.Optional[str]:
    """Return a human-readable reason for a Click & Drop status."""
    text = _normalize_status_text(status)

    if text == "":
        return None

    reason_rules = [
        (
            "customs_delay",
            [
                "customs",
                "customs hold",
                "awaiting customs",
            ],
        ),
        (
            "consignee_refused",
            [
                "refused",
            ],
        ),
        (
            "consignee_not_home",
            [
                "no answer",
                "not home",
                "recipient not available",
                "delivery attempted",
                "attempted delivery",
            ],
        ),
        (
            "consignee_incorrect_address",
            [
                "incorrect address",
                "bad address",
                "address problem",
            ],
        ),
        (
            "consignee_access_restricted",
            [
                "inaccessible",
                "access restricted",
                "no access",
            ],
        ),
        (
            "delivery_exception_hold",
            [
                "on hold",
                "held",
                "retention",
            ],
        ),
        (
            "delivery_exception_undeliverable",
            [
                "undeliverable",
                "unable to deliver",
                "could not deliver",
                "not delivered",
            ],
        ),
        (
            "carrier_parcel_lost",
            [
                "lost",
            ],
        ),
        (
            "carrier_damaged_parcel",
            [
                "damaged",
            ],
        ),
        (
            "carrier_sorting_error",
            [
                "mis sort",
                "missort",
                "misroute",
                "mis routed",
            ],
        ),
    ]

    return next(
        (
            reason
            for reason, phrases in reason_rules
            if _contains_any(text, phrases)
        ),
        None,
    )


def _click_and_drop_status_code(
    status: typing.Optional[str],
) -> typing.Optional[str]:
    """Return a Karrio status code for a Click & Drop status."""
    text = str(status or "").strip()

    if text == "":
        return None

    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper() or text


def _extract_click_and_drop_tracking_numbers(order: dict) -> typing.List[str]:
    """Extract tracking numbers from Click & Drop order package data."""
    shipping_details = (order or {}).get("shippingDetails") or {}
    shipping_packages = shipping_details.get("packages") or []
    order_packages = (order or {}).get("packages") or []

    values = [
        order.get("trackingNumber"),
        shipping_details.get("trackingNumber"),
        *[
            package.get("trackingNumber")
            for package in shipping_packages
            if isinstance(package, dict)
        ],
        *[
            package.get("trackingNumber")
            for package in order_packages
            if isinstance(package, dict)
        ],
    ]

    return [
        str(value).strip()
        for value in dict.fromkeys(values)
        if value is not None and str(value).strip() != ""
    ]

def _click_and_drop_event_datetime(order: dict, shipping_details: dict) -> str:
    """Resolve the best event datetime for a Click & Drop order."""
    return next(
        (
            value
            for value in [
                shipping_details.get("shippingUpdateSuccessDate"),
                order.get("shippedOn"),
                order.get("despatchedByOtherCourierOn"),
                order.get("manifestedOn"),
                order.get("postageAppliedOn"),
                order.get("printedOn"),
                order.get("createdOn"),
                order.get("orderDate"),
            ]
            if value
        ),
        None,
    )


def _extract_click_and_drop_info(
    order: dict,
    shipping_details: dict,
) -> typing.Optional[models.TrackingInfo]:
    """Extract tracking metadata from Click & Drop order data."""
    packages = shipping_details.get("packages") or []
    shipping_info = order.get("shippingInfo") or {}

    return models.TrackingInfo(
        order_id=(
            str(order.get("orderIdentifier"))
            if order.get("orderIdentifier") is not None
            else order.get("orderReference")
        ),
        shipment_service=(
            shipping_details.get("shippingService")
            or shipping_details.get("serviceCode")
        ),
        shipment_package_count=(
            str(len(packages))
            if isinstance(packages, list) and len(packages) > 0
            else None
        ),
        shipment_delivery_date=_format_tracking_date(order.get("shippedOn")),
        shipping_date=_format_tracking_date(order.get("shippedOn")),
        shipment_destination_country=shipping_info.get("countryCode"),
        shipment_destination_postal_code=shipping_info.get("postcode"),
        source="royalmail_click_and_drop",
    )


def _extract_click_and_drop_detail(
    order: dict,
    settings: provider_utils.Settings,
    fallback_tracking_number: str,
) -> models.TrackingDetails:
    """Build Karrio tracking detail from Click & Drop fallback data."""
    shipping_details = order.get("shippingDetails") or {}
    tracking_numbers = _extract_click_and_drop_tracking_numbers(order)
    tracking_number = provider_utils.resolve_tracking_number(
        tracking_numbers,
        fallback_tracking_number,
    )

    status_description = (
        shipping_details.get("shippingTrackingStatus")
        or order.get("shippingTrackingStatus")
        or order.get("trackingStatus")
        or order.get("orderStatus")
        or "Order found"
    )
    normalized_status = _normalize_click_and_drop_status(status_description)
    status_reason = _click_and_drop_status_reason(status_description)
    event_datetime = _click_and_drop_event_datetime(order, shipping_details)

    events = []
    if any([status_description, event_datetime]):
        events.append(
            models.TrackingEvent(
                date=_format_tracking_date(event_datetime),
                description=status_description,
                code=_click_and_drop_status_code(status_description),
                time=_format_tracking_time(event_datetime),
                timestamp=_format_tracking_timestamp(event_datetime),
                status=normalized_status,
                reason=status_reason,
            )
        )

    meta = {
        "source": "click_and_drop",
        "lookup_identifier": fallback_tracking_number,
        "order_identifier": order.get("orderIdentifier"),
        "order_reference": order.get("orderReference"),
        "order_status": order.get("orderStatus"),
        "created_on": order.get("createdOn"),
        "printed_on": order.get("printedOn"),
        "shipped_on": order.get("shippedOn"),
        "postage_applied_on": order.get("postageAppliedOn"),
        "manifested_on": order.get("manifestedOn"),
        "shipping_tracking_status": shipping_details.get("shippingTrackingStatus"),
        "service_code": shipping_details.get("serviceCode"),
        "shipping_service": shipping_details.get("shippingService"),
        "shipping_carrier": shipping_details.get("shippingCarrier"),
        "tracking_numbers": tracking_numbers or None,
        "packages": shipping_details.get("packages"),
    }

    return models.TrackingDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        tracking_number=tracking_number,
        delivered=normalized_status == "delivered",
        status=normalized_status,
        events=events,
        info=_extract_click_and_drop_info(order, shipping_details),
        meta={key: value for key, value in meta.items() if value not in [None, [], {}]},
    )


def _extract_pod_event(proof) -> typing.Optional[models.TrackingEvent]:
    """Build a proof-of-delivery event when a signature image exists."""
    if proof is None or not getattr(proof, "signatureDateTime", None):
        return None

    recipient_name = getattr(proof, "recipientName", None)
    description = "Proof of delivery captured"
    if recipient_name:
        description = f"Proof of delivery captured for {recipient_name}"

    return models.TrackingEvent(
        code="POD",
        description=description,
        date=_format_tracking_date(proof.signatureDateTime),
        time=_format_tracking_time(proof.signatureDateTime),
        timestamp=_format_tracking_timestamp(proof.signatureDateTime),
        status="delivered",
    )


def _extract_tracking_info(proof) -> typing.Optional[models.TrackingInfo]:
    """Combine summary, event, signature, and fallback metadata."""
    recipient_name = getattr(proof, "recipientName", None) if proof else None

    if not recipient_name:
        return None

    return models.TrackingInfo(
        customer_name=recipient_name,
    )