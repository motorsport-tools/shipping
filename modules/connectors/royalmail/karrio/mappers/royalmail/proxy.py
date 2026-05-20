"""Karrio Royal Mail Click and Drop client proxy."""

import typing
from urllib.parse import urlencode

import attr

import karrio.api.proxy as proxy
import karrio.lib as lib
import karrio.core.models as models
import karrio.mappers.royalmail.settings as provider_settings
import karrio.providers.royalmail.units as provider_units
import karrio.providers.royalmail.utils as provider_utils
import karrio.universal.mappers.rating_proxy as rating_proxy

def _normalize_query(query: typing.Optional[dict]) -> str:
    """Encode non-empty query parameters for Click & Drop URLs."""
    normalized = {}

    for key, value in (query or {}).items():
        if value is None:
            continue

        if isinstance(value, bool):
            normalized[key] = str(value).lower()
            continue

        if isinstance(value, (list, tuple)):
            normalized[key] = ",".join(str(item) for item in value)
            continue

        normalized[key] = value

    return urlencode(normalized, safe=",")


def _signature_url(
    settings: provider_settings.Settings,
    tracking_number: str,
    events_data: dict,
) -> typing.Optional[str]:
    """Build the Royal Mail Tracking API proof-of-delivery signature URL."""
    mail_piece = (events_data or {}).get("mailPieces") or {}
    if isinstance(mail_piece, list):
        mail_piece = next(
            (item for item in mail_piece if isinstance(item, dict)),
            {},
        )

    links = mail_piece.get("links") or {}
    signature_link = (links.get("signature") or {}).get("href")

    if signature_link:
        if signature_link.startswith("http"):
            return signature_link

        return f"{settings.tracking_server_url}{signature_link}"

    signature = mail_piece.get("signature") or {}
    if any(
        signature.get(key)
        for key in ["imageId", "recipientName", "signatureDateTime"]
    ):
        mail_piece_id = _tracking_mailpiece_identifier(
            tracking_number,
            mail_piece=mail_piece,
        )
        return f"{settings.tracking_server_url}/mailpieces/v2/{mail_piece_id}/signature"

    return None


def _chunks(
    values: typing.List[str],
    size: int = 30,
) -> typing.Iterable[typing.List[str]]:
    """Yield fixed-size chunks from an iterable."""
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _summary_url(
    settings: provider_settings.Settings,
    tracking_numbers: typing.List[str],
) -> str:
    """Build the Royal Mail Tracking API summary URL."""
    query = _normalize_query({"mailPieceId": tracking_numbers})
    return f"{settings.tracking_server_url}/mailpieces/v2/summary?{query}"


def _present(value: typing.Any) -> bool:
    """Return true when a value should be treated as present."""
    return value not in [None, "", [], {}]


def _as_list(value: typing.Any) -> typing.List[typing.Any]:
    """Normalize a scalar or collection into a list."""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]


def _mapped_lookup_value(
    value: typing.Any,
    tracking_number: str,
    index: int,
    total: int,
) -> typing.Any:
    """Resolve a scalar/list/dict tracking lookup option.

    Supported examples:

    Single shipment:
        {"order_reference": "ORDER-1001"}

    Multiple shipments:
        {"order_references": ["ORDER-1001", "ORDER-1002"]}

    Explicit mapping:
        {"order_references": {"RM123456789GB": "ORDER-1001"}}
    """

    if isinstance(value, dict):
        for key in [tracking_number, str(tracking_number), "default"]:
            if key in value and _present(value[key]):
                return value[key]

        return None

    values = _as_list(value)

    if len(values) == 0:
        return None

    if len(values) == total and index < len(values):
        return values[index]

    if total == 1:
        return values[0]

    return None


def _first_present(values: typing.Iterable[typing.Any]) -> typing.Any:
    """Return the first non-empty value from an iterable."""
    for value in values:
        if isinstance(value, (list, tuple, set)):
            nested = _first_present(value)
            if _present(nested):
                return nested
            continue

        if _present(value):
            return value

    return None

def _options_for_tracking_number(
    options: typing.Optional[dict],
    tracking_number: str,
) -> dict:
    """Return tracking-number scoped options merged over top-level options.

    Supported shapes:

        {"order_reference": "ORDER-1001"}

        {"order_references": {"RM123456789GB": "ORDER-1001"}}

        {"RM123456789GB": {"order_reference": "ORDER-1001"}}

        {"tracking_options": {"order_reference": "ORDER-1001"}}

        {
            "tracking_options": {
                "order_references": {
                    "RM123456789GB": "ORDER-1001"
                }
            }
        }
    """

    if not isinstance(options, dict):
        return {}

    tracking_options = (
        options.get("tracking_options")
        if isinstance(options.get("tracking_options"), dict)
        else {}
    )

    nested = next(
        (
            source.get(key)
            for source in [options, tracking_options]
            for key in [tracking_number, str(tracking_number)]
            if isinstance(source.get(key), dict)
        ),
        {},
    )

    return {
        **options,
        **tracking_options,
        **nested,
    }

def _tracking_key_candidates(tracking_number: str) -> typing.List[str]:
    """Return likely Karrio/Royal Mail tracking keys for saved lookup.

    Royal Mail Click & Drop can return a consignment-style tracking number with
    `_CON`, while package rows can contain the item barcode without `_CON`.
    We keep the exact key first, then add common alternatives.
    """
    value = str(tracking_number or "").strip()
    if not value:
        return []

    base = value[:-4] if value.endswith("_CON") else value

    return [
        key
        for key in dict.fromkeys(
            [
                value,
                base,
                f"{base}_CON",
            ]
        )
        if key
    ]


def _as_dict(value: typing.Any) -> dict:
    """Return a dict value or an empty dict for non-dicts."""
    return value if isinstance(value, dict) else {}


def _lookup_value_from_source(
    source: typing.Any,
    tracking_number: str,
    scalar_keys: typing.List[str],
    mapped_keys: typing.List[str],
) -> typing.Any:
    """Extract a lookup value from a tracker/shipment source dictionary.

    Supports all shapes used by the connector and by Karrio tracker options:

        {"order_reference": "ABC"}
        {"order_references": {"PK123": "ABC"}}
        {"PK123": {"order_reference": "ABC"}}
        {"tracking_options": {"order_reference": "ABC"}}
        {"tracking_lookup": {"order_identifier": 116962}}
    """
    root = _as_dict(source)
    if not root:
        return None

    keys = _tracking_key_candidates(tracking_number)

    queue = [
        root,
        _as_dict(root.get("tracking_options")),
        _as_dict(root.get("tracking_lookup")),
        _as_dict(root.get("click_and_drop")),
        _as_dict(root.get("royalmail")),
    ]

    containers: typing.List[dict] = []
    seen: typing.Set[int] = set()

    while queue:
        current = _as_dict(queue.pop(0))
        if not current:
            continue

        marker = id(current)
        if marker in seen:
            continue

        seen.add(marker)
        containers.append(current)

        for key in keys:
            nested = current.get(key)
            if isinstance(nested, dict):
                queue.append(nested)

    for container in containers:
        for mapped_key in mapped_keys:
            mapped = container.get(mapped_key)
            for key in keys:
                value = _mapped_lookup_value(mapped, key, 0, 1)
                if _present(value):
                    return value

        for scalar_key in scalar_keys:
            value = container.get(scalar_key)
            if _present(value):
                return value

    return None


def _shipment_identifier_lookup_data(shipment) -> dict:
    """Classify Karrio shipment_identifier as Royal Mail order id/reference.

    Royal Mail Click & Drop order identifiers are numeric. References are
    strings and must be encoded/quoted by `make_order_identifiers`.
    """
    value = getattr(shipment, "shipment_identifier", None)
    if not _present(value):
        return {}

    text = str(value).strip()
    if text.isdigit():
        return {"order_identifier": text}

    return {"order_reference": text}


def _saved_click_and_drop_lookup_for_tracking_number(tracking_number: str) -> dict:
    """Best-effort Karrio server lookup for Click & Drop fallback tracking.

    This keeps the Royal Mail SDK extension usable in two modes:

    1. Pure SDK mode:
       - no Django/Karrio server models are available
       - function returns {}

    2. Karrio server extension mode:
       - lookup the saved tracker/shipment by tracking number
       - recover Royal Mail orderIdentifier/orderReference saved at shipment creation

    This is intentionally defensive because carrier SDK code should not crash if
    it is executed outside the Karrio server process.
    """
    try:
        from karrio.server.manager import models as server_models
    except Exception:
        return {}

    keys = _tracking_key_candidates(tracking_number)

    try:
        tracker = (
            server_models.Tracking.objects.filter(tracking_number__in=keys)
            .select_related("shipment")
            .order_by("-created_at")
            .first()
        )
    except Exception:
        tracker = None

    shipment = getattr(tracker, "shipment", None) if tracker is not None else None

    if shipment is None:
        try:
            shipment = (
                server_models.Shipment.objects.filter(tracking_number__in=keys)
                .order_by("-created_at")
                .first()
            )
        except Exception:
            shipment = None

    if shipment is None:
        # Optional JSON lookup for package-level tracking numbers. Some DB
        # backends may not support JSON contains in the same way, so keep this
        # guarded.
        for key in keys:
            try:
                shipment = (
                    server_models.Shipment.objects.filter(
                        meta__tracking_numbers__contains=[key]
                    )
                    .order_by("-created_at")
                    .first()
                )
                if shipment is not None:
                    break
            except Exception:
                continue

    sources: typing.List[dict] = []

    if tracker is not None:
        sources.extend(
            [
                _as_dict(getattr(tracker, "options", None)),
                _as_dict(getattr(tracker, "meta", None)),
                _as_dict(getattr(tracker, "metadata", None)),
                {"order_reference": getattr(tracker, "reference", None)},
            ]
        )

    if shipment is not None:
        sources.extend(
            [
                _as_dict(getattr(shipment, "options", None)),
                _as_dict(getattr(shipment, "meta", None)),
                _as_dict(getattr(shipment, "metadata", None)),
                _shipment_identifier_lookup_data(shipment),
                {
                    # These are valid only if they were sent to Royal Mail as
                    # orderReference during shipment creation. The current
                    # Royal Mail shipment_request uses payload.reference and
                    # payload.order_id as orderReference fallbacks.
                    "order_reference": getattr(shipment, "reference", None),
                    "order_id": getattr(shipment, "order_id", None),
                },
            ]
        )

    order_reference = _first_present(
        [
            _lookup_value_from_source(
                source,
                tracking_number,
                scalar_keys=[
                    "order_reference",
                    "orderReference",
                    "reference",
                    "order_id",
                    "orderId",
                ],
                mapped_keys=[
                    "order_references",
                    "orderReferences",
                ],
            )
            for source in sources
        ]
    )

    order_identifier = _first_present(
        [
            _lookup_value_from_source(
                source,
                tracking_number,
                scalar_keys=[
                    "order_identifier",
                    "orderIdentifier",
                    "shipment_identifier",
                    "shipmentIdentifier",
                ],
                mapped_keys=[
                    "order_identifiers",
                    "orderIdentifiers",
                ],
            )
            for source in sources
        ]
    )

    return {
        key: value
        for key, value in {
            "order_reference": order_reference,
            "order_identifier": order_identifier,
        }.items()
        if _present(value)
    }

def _click_and_drop_lookup_for_tracking_number(
    tracking_number: str,
    index: int,
    total: int,
    options: dict,
    reference: typing.Optional[str] = None,
) -> typing.Optional[dict]:
    """Resolve the Click & Drop order lookup identifier for a tracking number.

    Royal Mail Click & Drop `/orders/{orderIdentifiers}/full` supports:

    - numeric `orderIdentifier`, e.g. `116962`
    - quoted/encoded `orderReference`, e.g. `%22MY-REF%22`

    Tracking numbers are not valid Click & Drop order lookup identifiers.
    """
    scoped_options = _options_for_tracking_number(options, tracking_number)
    saved_lookup = _saved_click_and_drop_lookup_for_tracking_number(tracking_number)

    order_reference = _first_present(
        [
            _mapped_lookup_value(
                scoped_options.get("order_references"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("order_reference"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("orderReferences"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("orderReference"),
                tracking_number,
                index,
                total,
            ),
            reference if total == 1 else None,
            saved_lookup.get("order_reference"),
        ]
    )

    if _present(order_reference):
        return {
            "value": order_reference,
            # Important:
            # Even if an orderReference is numeric-looking, Royal Mail requires
            # references to be quoted and percent-encoded.
            "treat_numeric_as_reference": True,
            "source": "order_reference",
        }

    order_identifier = _first_present(
        [
            _mapped_lookup_value(
                scoped_options.get("order_identifiers"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("order_identifier"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("orderIdentifiers"),
                tracking_number,
                index,
                total,
            ),
            _mapped_lookup_value(
                scoped_options.get("orderIdentifier"),
                tracking_number,
                index,
                total,
            ),
            saved_lookup.get("order_identifier"),
        ]
    )

    if _present(order_identifier):
        return {
            "value": order_identifier,
            # Numeric Click & Drop orderIdentifier must be passed as-is.
            "treat_numeric_as_reference": False,
            "source": "order_identifier",
        }

    return None

def _format_click_and_drop_lookup(lookup: dict) -> typing.List[str]:
    """Format Click & Drop lookup data for diagnostic messages."""
    serialized = provider_utils.make_order_identifiers(
        lookup.get("value"),
        treat_numeric_as_reference=bool(
            lookup.get("treat_numeric_as_reference", False)
        ),
    )

    return [
        identifier
        for identifier in str(serialized or "").split(";")
        if identifier.strip()
    ]


def _click_and_drop_order_details_url(
    settings: provider_settings.Settings,
    order_identifiers: typing.List[dict],
    ) -> str:
    """Build the Click & Drop order details URL for a resolved lookup."""
    identifiers = [
        identifier
        for lookup in order_identifiers
        if lookup is not None and _present(lookup.get("value"))
        for identifier in _format_click_and_drop_lookup(lookup)
    ]

    identifiers = list(dict.fromkeys(identifiers))

    if len(identifiers) > 100:
        raise ValueError(
            "Royal Mail Click & Drop supports a maximum of 100 order identifiers"
        )

    return f"{settings.server_url}/orders/{';'.join(identifiers)}/full"

def _missing_click_and_drop_lookup_response(tracking_number: str) -> dict:
    """Build a synthetic Click & Drop fallback response when lookup data is missing."""
    return _click_and_drop_tracking_response(
        {
            # Keep this code stable for existing tests/users.
            #
            # Historically the fallback required an orderReference. The fallback
            # now also supports orderIdentifier, but this is still the same
            # user-facing condition: Click & Drop cannot look up full order
            # details from a tracking number alone.
            "code": "missing_order_reference",
            "message": (
                "Royal Mail Click & Drop fallback tracking requires the "
                "orderIdentifier or orderReference saved from shipment creation. "
                "Click & Drop cannot retrieve full order details by tracking "
                "number alone."
            ),
            "details": {
                "tracking_number": tracking_number,
                "required_fields": [
                    "reference",
                    "options.order_reference",
                    "options.order_references",
                    "options.orderReference",
                    "options.orderReferences",
                    "options.order_identifier",
                    "options.order_identifiers",
                    "options.orderIdentifier",
                    "options.orderIdentifiers",
                    "saved shipment.shipment_identifier",
                    "saved shipment.meta.order_identifier",
                    "saved shipment.meta.order_reference",
                ],
            },
        },
        lookup_identifier=tracking_number,
    )


def _summary_piece_keys(mail_piece: dict) -> typing.List[str]:
    """Return possible tracking identifiers from a Tracking API summary mail piece."""
    summary = (mail_piece or {}).get("summary") or {}

    return [
        key
        for key in dict.fromkeys(
            [
                (mail_piece or {}).get("mailPieceId"),
                summary.get("uniqueItemId"),
                summary.get("oneDBarcode"),
            ]
        )
        if key
    ]


def _click_and_drop_order_keys(order: dict) -> typing.List[str]:
    """Return lookup keys that can associate a Click & Drop order to a request item."""

    shipping_details = (order or {}).get("shippingDetails") or {}
    shipping_packages = shipping_details.get("packages") or []
    order_packages = (order or {}).get("packages") or []

    values = [
        (order or {}).get("orderIdentifier"),
        (order or {}).get("orderReference"),
        (order or {}).get("trackingNumber"),
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


def _click_and_drop_tracking_response(
    response: typing.Any = None,
    lookup_identifier: typing.Optional[str] = None,
) -> dict:
    """Wrap a Click & Drop order payload as a tracking fallback response."""
    return {
        "summary": {},
        "events": None,
        "signature": None,
        "click_and_drop": response,
        "lookup_identifier": lookup_identifier,
    }


def _tracking_mailpiece_identifier(
    tracking_number: str,
    summary_piece: typing.Optional[dict] = None,
    mail_piece: typing.Optional[dict] = None,
) -> str:
    """Return the best mail-piece identifier from a tracking request item."""
    summary = (summary_piece or {}).get("summary") or {}
    events_summary = (mail_piece or {}).get("summary") or {}

    return (
        (mail_piece or {}).get("mailPieceId")
        or (summary_piece or {}).get("mailPieceId")
        or events_summary.get("uniqueItemId")
        or events_summary.get("oneDBarcode")
        or summary.get("uniqueItemId")
        or summary.get("oneDBarcode")
        or tracking_number
    )




def _events_url(
    settings: provider_settings.Settings,
    tracking_number: str,
    summary_piece: typing.Optional[dict] = None,
) -> str:
    """Build the Royal Mail Tracking API events URL."""
    links = (summary_piece or {}).get("links") or {}
    events_link = (links.get("events") or {}).get("href")

    if events_link:
        if events_link.startswith("http"):
            return events_link

        return f"{settings.tracking_server_url}{events_link}"

    mail_piece_id = _tracking_mailpiece_identifier(
        tracking_number,
        summary_piece=summary_piece,
    )

    return f"{settings.tracking_server_url}/mailpieces/v2/{mail_piece_id}/events"


def _summary_piece_has_error(summary_piece: typing.Optional[dict]) -> bool:
    """Return whether a summary mail-piece payload represents an error item."""
    return bool((summary_piece or {}).get("error"))

def _state_value(value: typing.Any) -> typing.Any:
    """Return the value from a Karrio state wrapper or raw object."""
    return value.state if hasattr(value, "state") else value


def _request_value(obj: typing.Any, name: str, default=None):
    """Read a value from a request object or its raw data."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _option_value(options: typing.Any, *names: str) -> typing.Any:
    """Read the first available option value by name."""
    if options is None:
        return None

    if isinstance(options, dict):
        normalized = provider_units.normalize_option_keys(options)

        for name in names:
            if name in normalized:
                return normalized[name]

            if name in options:
                return options[name]

        return None

    for name in names:
        value = getattr(options, name, None)

        if value is not None:
            return _state_value(value)

    return None

ROYALMAIL_OPTION_SURCHARGE_DEFINITIONS = [
    {
        "id": provider_units.ROYALMAIL_SIGNATURE_SURCHARGE_ID,
        "name": "Signature on delivery",
        "option_names": (
            "request_signature_upon_delivery",
            "signature_confirmation",
        ),
        "metadata_keys": (
            "signature_surcharge_amount",
            "signature_addon_amount",
            "signature_price",
        ),
    },
    {
        "id": provider_units.ROYALMAIL_AGE_VERIFICATION_SURCHARGE_ID,
        "name": "Age verification",
        "option_names": (
            "royalmail_age_verification",
            "age_verification",
        ),
        "metadata_keys": (
            "age_verification_surcharge_amount",
            "age_verification_addon_amount",
            "age_verification_price",
        ),
    },
    {
        "id": provider_units.ROYALMAIL_ID_VERIFICATION_SURCHARGE_ID,
        "name": "ID verification",
        "option_names": (
            "royalmail_id_verification",
            "id_verification",
        ),
        "metadata_keys": (
            "id_verification_surcharge_amount",
            "id_verification_addon_amount",
            "id_verification_price",
        ),
    },
]


def _option_enabled(options: typing.Any, *names: str) -> bool:
    """Return whether one of the given option names is explicitly enabled."""
    value = _option_value(options, *names)

    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in ["1", "true", "yes", "y", "on"]

    return bool(value)


def _metadata_amount(
    metadata: dict,
    *keys: str,
) -> typing.Optional[float]:
    """Read a positive/zero money amount from service metadata."""
    for key in keys:
        value = metadata.get(key)

        if value in [None, ""]:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


ROYALMAIL_OPTION_SURCHARGE_DEFINITIONS = [
    {
        "id": provider_units.ROYALMAIL_SIGNATURE_SURCHARGE_ID,
        "name": "Signature on delivery",
        "option_names": (
            "request_signature_upon_delivery",
            "signature_confirmation",
        ),
        "metadata_keys": (
            "signature_surcharge_amount",
            "signature_addon_amount",
            "signature_price",
        ),
        "format_metadata_keys": {
            "letter": (
                "signature_surcharge_letter_amount",
                "signature_letter_surcharge_amount",
                "signature_letter_price",
            ),
            "large_letter": (
                "signature_surcharge_large_letter_amount",
                "signature_large_letter_surcharge_amount",
                "signature_large_letter_price",
            ),
            "parcel": (
                "signature_surcharge_parcel_amount",
                "signature_parcel_surcharge_amount",
                "signature_parcel_price",
            ),
        },
    },
    {
        "id": provider_units.ROYALMAIL_AGE_VERIFICATION_SURCHARGE_ID,
        "name": "Age verification",
        "option_names": (
            "royalmail_age_verification",
            "age_verification",
        ),
        "metadata_keys": (
            "age_verification_surcharge_amount",
            "age_verification_addon_amount",
            "age_verification_price",
        ),
    },
    {
        "id": provider_units.ROYALMAIL_ID_VERIFICATION_SURCHARGE_ID,
        "name": "ID verification",
        "option_names": (
            "royalmail_id_verification",
            "id_verification",
        ),
        "metadata_keys": (
            "id_verification_surcharge_amount",
            "id_verification_addon_amount",
            "id_verification_price",
        ),
    },
]


def _option_enabled(options: typing.Any, *names: str) -> bool:
    """Return whether one of the given option names is explicitly enabled."""
    value = _option_value(options, *names)

    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in ["1", "true", "yes", "y", "on"]

    return bool(value)


def _metadata_amount(
    metadata: dict,
    *keys: str,
) -> typing.Optional[float]:
    """Read a positive/zero money amount from service metadata."""
    for key in keys:
        value = metadata.get(key)

        if value in [None, ""]:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def _requested_package_format_kind(
    service: models.ServiceLevel,
    options: typing.Any,
) -> typing.Optional[str]:
    """
    Resolve the package-format kind relevant to optional surcharge pricing.

    This is needed because Royal Mail Tracked signature pricing differs by
    format:

        largeLetter -> £1.10
        parcel      -> £0.70

    If the request does not explicitly provide a package format, fall back to
    the service metadata inferred from services.csv.
    """
    metadata = getattr(service, "metadata", {}) or {}

    package_format = _option_value(
        options,
        "package_format_identifier",
        "packageFormatIdentifier",
    )

    if package_format in [None, ""] and isinstance(metadata, dict):
        package_format = metadata.get("package_format_identifier")

    if package_format not in [None, ""]:
        normalized_format = (
            provider_units.normalize_click_and_drop_package_format_identifier(
                package_format
            )
        )
        package_kind = provider_units._package_format_register_kind(
            normalized_format
        )

        if package_kind not in [None, ""]:
            return package_kind

    if isinstance(metadata, dict):
        return metadata.get("package_format_kind")

    return None


def _metadata_amount_for_definition(
    service: models.ServiceLevel,
    options: typing.Any,
    definition: dict,
) -> typing.Optional[float]:
    """
    Resolve the surcharge amount for a definition.

    Format-specific metadata wins over the generic value. This allows Royal
    Mail Tracked large-letter signature pricing to differ from parcel pricing.
    """
    metadata = getattr(service, "metadata", {}) or {}

    if not isinstance(metadata, dict):
        return None

    package_kind = _requested_package_format_kind(service, options)
    format_metadata_keys = definition.get("format_metadata_keys") or {}

    if package_kind in format_metadata_keys:
        amount = _metadata_amount(
            metadata,
            *format_metadata_keys[package_kind],
        )

        # Explicit 0 should mean included/free, not fallback to generic.
        if amount is not None:
            return amount

    return _metadata_amount(
        metadata,
        *(definition.get("metadata_keys") or []),
    )


def _royalmail_option_surcharges(
    service: models.ServiceLevel,
    options: typing.Any,
) -> typing.List[models.Surcharge]:
    """
    Build option-triggered Royal Mail feature surcharges.

    These are intentionally not loaded into ServiceLevel.surcharges from CSV,
    because they only apply when the user selects the matching Karrio option.

    Example:
        options.signature_confirmation = true
        service.metadata.signature_surcharge_amount = 2.00

    Result:
        + GBP 2.00 Signature on delivery
    """
    metadata = getattr(service, "metadata", {}) or {}

    if not isinstance(metadata, dict):
        return []

    # Royal Mail ID verification includes a signature check according to the
    # price-guide text. If an ID verification charge is configured and requested,
    # do not also add the plain signature add-on.
    id_verification_requested = _option_enabled(
        options,
        "royalmail_id_verification",
        "id_verification",
    )

    surcharges: typing.List[models.Surcharge] = []

    for definition in ROYALMAIL_OPTION_SURCHARGE_DEFINITIONS:
        if (
            definition["id"] == provider_units.ROYALMAIL_SIGNATURE_SURCHARGE_ID
            and id_verification_requested
        ):
            continue

        if not _option_enabled(options, *definition["option_names"]):
            continue

        amount = _metadata_amount_for_definition(
            service,
            options,
            definition,
        )

        # Blank means "not configured / not chargeable for this service".
        # 0 means "included/free" and should not create an extra charge line.
        if amount in [None, 0]:
            continue

        surcharges.append(
            models.Surcharge(
                id=definition["id"],
                name=definition["name"],
                amount=amount,
                surcharge_type="fixed",
                active=True,
            )
        )

    return surcharges

def _raw_parcel_options(raw_parcel: typing.Any) -> dict:
    """Return raw per-parcel options from a parcel payload."""
    options = _request_value(raw_parcel, "options", {}) or {}

    return options if isinstance(options, dict) else {}

def _number_or_none(value: typing.Any) -> typing.Optional[float]:
    """Convert a value to float, returning None when unavailable."""
    if value in [None, ""]:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weight_to_kg(value: typing.Any, unit: typing.Any) -> typing.Optional[float]:
    """Convert a weight value from its source unit to kilograms."""
    number = _number_or_none(value)

    if number is None or unit in [None, ""]:
        return None

    normalized_unit = str(unit).strip().upper()

    if normalized_unit in ["KG", "KGS", "KILOGRAM", "KILOGRAMS"]:
        return number

    if normalized_unit in ["G", "GRAM", "GRAMS"]:
        return number / 1000

    return None


def _dimension_to_cm(value: typing.Any, unit: typing.Any) -> typing.Optional[float]:
    """Convert a dimension value from its source unit to centimetres."""
    number = _number_or_none(value)

    if number is None or unit in [None, ""]:
        return None

    normalized_unit = str(unit).strip().upper()

    if normalized_unit in ["CM", "CMS", "CENTIMETRE", "CENTIMETRES", "CENTIMETER", "CENTIMETERS"]:
        return number

    if normalized_unit in ["MM", "MMS", "MILLIMETRE", "MILLIMETRES", "MILLIMETER", "MILLIMETERS"]:
        return number / 10

    if normalized_unit in ["M", "METRE", "METRES", "METER", "METERS"]:
        return number * 100

    return None



def _normalize_royalmail_dimensions_for_rating(
    length: typing.Optional[float],
    width: typing.Optional[float],
    height: typing.Optional[float],
) -> typing.Tuple[
    typing.Optional[float],
    typing.Optional[float],
    typing.Optional[float],
]:
    """
    Normalize parcel dimensions for Karrio's positional rating checks while
    preserving Royal Mail's orientation-independent package limits.

    The Royal Mail services.csv in this extension stores dimensions as:

        max_length = middle side
        max_width  = longest side
        max_height = shortest/depth side

    Examples:
        Letter:       16.5 x 24.0 x 0.5 cm
        Large Letter: 25.0 x 35.3 x 2.5 cm
        Small Parcel: 35.0 x 45.0 x 16.0 cm

    Karrio universal rating compares fields positionally:

        parcel.length <= service.max_length
        parcel.width  <= service.max_width
        parcel.height <= service.max_height

    Therefore we normalize the request parcel into:

        length = middle side
        width  = longest side
        height = shortest side

    This allows a user to enter 35.3 x 25 x 2.5 cm or 25 x 35.3 x 2.5 cm and
    still match the same Royal Mail Large Letter service.
    """
    values = [length, width, height]

    if any(value is None for value in values):
        return length, width, height

    shortest, middle, longest = sorted(values)

    return middle, longest, shortest

def _normalize_rate_service_dimensions_for_universal_rating(
    service: models.ServiceLevel,
) -> models.ServiceLevel:
    """
    Normalize Royal Mail service dimensions before using Karrio universal rating.

    Royal Mail package dimensions are orientation-independent, but Karrio's
    universal rating engine compares dimensions positionally:

        parcel.length <= service.max_length
        parcel.width  <= service.max_width
        parcel.height <= service.max_height

    The request parcel is normalized as:

        length = middle side
        width  = longest side
        height = shortest side

    Some Royal Mail CSV rows, especially international large-letter rows, are
    stored as longest/middle/shortest instead of middle/longest/shortest. This
    rate-only normalization makes service limits use the same convention as the
    normalized parcel without mutating the service catalog itself.
    """
    dimensions = [service.max_length, service.max_width, service.max_height]

    if any(value is None for value in dimensions):
        return service

    shortest, middle, longest = sorted(dimensions)
    normalized_dimensions = (middle, longest, shortest)
    current_dimensions = (service.max_length, service.max_width, service.max_height)

    if current_dimensions == normalized_dimensions:
        return service

    return attr.evolve(
        service,
        max_length=middle,
        max_width=longest,
        max_height=shortest,
    )

def _rate_request_surcharge_date(rate_request: typing.Any) -> typing.Any:
    """
    Resolve the date used for Royal Mail date-limited surcharges.

    Priority is:

    1. Explicit surcharge/rate date.
    2. Royal Mail planned despatch date.
    3. Generic shipment/ship/shipping date.
    4. Current date, handled later by provider_units.is_peak_surcharge_date().
    """
    options = _request_value(rate_request, "options", {}) or {}

    return (
        _request_value(rate_request, "royalmail_surcharge_date")
        or _request_value(rate_request, "surcharge_date")
        or _request_value(rate_request, "rate_date")
        or _request_value(rate_request, "planned_despatch_date")
        or _request_value(rate_request, "plannedDespatchDate")
        or _request_value(rate_request, "shipment_date")
        or _request_value(rate_request, "shipmentDate")
        or _request_value(rate_request, "ship_date")
        or _request_value(rate_request, "shipDate")
        or _request_value(rate_request, "shipping_date")
        or _request_value(rate_request, "shippingDate")
        or _option_value(
            options,
            "royalmail_surcharge_date",
            "royalmailSurchargeDate",
            "surcharge_date",
            "surchargeDate",
            "rate_date",
            "rateDate",
            "planned_despatch_date",
            "plannedDespatchDate",
            "despatch_date",
            "despatchDate",
            "shipment_date",
            "shipmentDate",
            "ship_date",
            "shipDate",
            "shipping_date",
            "shippingDate",
        )
    )


def _with_active_royalmail_surcharges(
    service: models.ServiceLevel,
    surcharge_date: typing.Any,
    options: typing.Any = None,
) -> models.ServiceLevel:
    """
    Return a service copy with:

    1. Date-active Royal Mail surcharges, such as Peak.
    2. Option-triggered feature surcharges, such as Signature on delivery.

    Important:
    Feature/accessorial prices are not always-on service surcharges.
    They are only appended when the Karrio option is selected.
    """
    metadata = getattr(service, "metadata", {}) or {}

    peak_start_date = (
        metadata.get("peak_surcharge_start_date")
        if isinstance(metadata, dict)
        else None
    )
    peak_end_date = (
        metadata.get("peak_surcharge_end_date")
        if isinstance(metadata, dict)
        else None
    )

    active_surcharges = provider_units.active_royalmail_surcharges(
        getattr(service, "surcharges", []) or [],
        at_date=surcharge_date,
        peak_start_date=peak_start_date,
        peak_end_date=peak_end_date,
    )

    option_surcharges = _royalmail_option_surcharges(
        service,
        options or {},
    )

    return attr.evolve(
        service,
        surcharges=[
            *active_surcharges,
            *option_surcharges,
        ],
    )

def _settings_for_universal_rating(
    settings: provider_settings.Settings,
    rate_request: typing.Any = None,
) -> provider_settings.Settings:
    """
    Return a copy of settings with Royal Mail service dimensions normalized for
    local universal-rating only.

    This also injects option-triggered feature surcharges, e.g.:

        options.signature_confirmation = true
        service.metadata.signature_surcharge_amount = 2.00
        -> add GBP 2.00 Signature on delivery to the local rate.

    Important:
    Do not use `settings.services or DEFAULT_SERVICES`.

    If `settings.services` is an explicit empty list after active filtering, we
    must preserve that empty list. Otherwise inactive rows such as
    active="False" can be filtered out, then accidentally replaced by the full
    default Royal Mail rate table.
    """
    surcharge_date = _rate_request_surcharge_date(rate_request)
    options = _request_value(rate_request, "options", {}) or {}

    raw_services = (
        settings.services
        if settings.services is not None
        else provider_units.DEFAULT_SERVICES
    )

    active_services = provider_units.active_service_levels(raw_services)

    return attr.evolve(
        settings,
        services=[
            _normalize_rate_service_dimensions_for_universal_rating(
                _with_active_royalmail_surcharges(
                    service,
                    surcharge_date,
                    options=options,
                )
            )
            for service in active_services
        ],
    )

def _normalize_rate_parcel_for_universal_rating(parcel: typing.Any) -> dict:
    """
    Normalize Royal Mail metric parcel inputs before using Karrio's universal
    rating engine.

    This handles two Royal Mail/Karrio compatibility issues:

    1. Unit compatibility:
       Karrio universal Package collection treats KG as the safe metric rating
       weight unit. A parcel declared in G can be routed through imperial
       conversions internally, which can cause boundary rounding issues.

    2. Dimension orientation:
       Royal Mail package limits are orientation-independent, while Karrio
       universal rating checks length/width/height positionally. The Royal Mail
       service catalog stores dimensions as middle/longest/shortest, so the
       request parcel is normalized into that same convention before rating.

    The original request is still used later for Royal Mail package-format
    detection and filtering.
    """
    parcel_data = lib.to_dict(parcel, clear_empty=False)

    if not isinstance(parcel_data, dict):
        return parcel

    normalized = dict(parcel_data)

    weight_unit = normalized.get("weight_unit") or normalized.get("weightUnit")
    weight_kg = _weight_to_kg(normalized.get("weight"), weight_unit)

    if weight_kg is not None:
        normalized["weight"] = weight_kg
        normalized["weight_unit"] = "KG"
        normalized.pop("weightUnit", None)

    dimension_unit = normalized.get("dimension_unit") or normalized.get("dimensionUnit")

    if dimension_unit not in [None, ""]:
        converted_dimensions = {}

        for field in ["length", "width", "height"]:
            value_cm = _dimension_to_cm(normalized.get(field), dimension_unit)

            if value_cm is not None:
                converted_dimensions[field] = value_cm
            else:
                converted_dimensions[field] = None

        normalized_length, normalized_width, normalized_height = (
            _normalize_royalmail_dimensions_for_rating(
                converted_dimensions.get("length"),
                converted_dimensions.get("width"),
                converted_dimensions.get("height"),
            )
        )

        if normalized_length is not None:
            normalized["length"] = normalized_length

        if normalized_width is not None:
            normalized["width"] = normalized_width

        if normalized_height is not None:
            normalized["height"] = normalized_height

        normalized["dimension_unit"] = "CM"
        normalized.pop("dimensionUnit", None)

    return normalized


def _normalize_rate_request_for_universal_rating(
    rate_request: typing.Any,
) -> models.RateRequest:
    """
    Return a metric-normalized RateRequest for Karrio universal rating.

    The original request should still be used for Royal Mail-specific
    package-format detection/filtering.
    """
    request_data = lib.to_dict(rate_request, clear_empty=False)

    if not isinstance(request_data, dict):
        return rate_request

    parcels = request_data.get("parcels") or []

    if isinstance(parcels, list):
        request_data["parcels"] = [
            _normalize_rate_parcel_for_universal_rating(parcel)
            for parcel in parcels
        ]

    return models.RateRequest(**request_data)

def _rate_request_package_formats(rate_request: typing.Any) -> typing.List[str]:
    """
    Resolve Royal Mail packageFormatIdentifier values from a rate request.

    Important:
    Do not call `lib.to_packages()` here. At proxy time, the rate request has
    often already been serialized, so parcels are plain dicts, not Karrio Parcel
    objects. `provider_units.resolve_package_format()` already supports raw dict
    parcels, so use that directly.
    """
    parcels = _request_value(rate_request, "parcels", []) or []

    if isinstance(parcels, (list, tuple)):
        raw_parcels = list(parcels)
    else:
        raw_parcels = [parcels]

    request_options = _request_value(rate_request, "options", {}) or {}

    shipment_package_format = _option_value(
        request_options,
        "package_format_identifier",
        "packageFormatIdentifier",
    )

    package_formats = []

    for raw_parcel in raw_parcels:
        parcel_options = _raw_parcel_options(raw_parcel)

        parcel_package_format = _option_value(
            parcel_options,
            "package_format_identifier",
            "packageFormatIdentifier",
        )

        package_format = provider_units.resolve_package_format(
            package=None if isinstance(raw_parcel, dict) else raw_parcel,
            raw_package=raw_parcel,
            explicit=parcel_package_format or shipment_package_format,
        )

        if package_format not in [None, ""]:
            package_formats.append(package_format)

    return package_formats

def _resolve_rate_service_codes(
    service: typing.Any,
    package_formats: typing.Optional[typing.Iterable[str]] = None,
) -> typing.List[str]:
    """
    Resolve a requested Royal Mail rate service selector into active canonical
    Karrio service codes.

    Delegates to provider_units so active filtering is defined in one place.
    """
    return provider_units.resolve_rate_service_codes(
        service,
        package_formats=package_formats,
    )


def _normalize_rate_request_services_for_rating(
    rate_request: typing.Any,
) -> models.RateRequest:
    """
    Normalize RateRequest.services before passing the request to Karrio universal
    rating.

    This keeps canonical Karrio service codes unchanged, but expands raw Royal
    Mail Click & Drop service codes such as `OTA`, `OLA`, `OSA`, etc. using the
    requested package format.
    """
    request_data = lib.to_dict(rate_request, clear_empty=False)

    if not isinstance(request_data, dict):
        return rate_request

    requested_services = request_data.get("services") or []

    if isinstance(requested_services, str):
        requested_services = [requested_services]

    if not any(requested_services):
        return models.RateRequest(**request_data)

    package_formats = _rate_request_package_formats(request_data)

    expanded_services = []

    for service in requested_services:
        expanded_services.extend(
            _resolve_rate_service_codes(
                service,
                package_formats=package_formats,
            )
        )

    request_data["services"] = list(
        dict.fromkeys(
            service
            for service in expanded_services
            if service not in [None, ""]
        )
    )

    return models.RateRequest(**request_data)

def _requested_rate_services(rate_request: typing.Any) -> typing.Set[str]:
    """Return canonical service codes explicitly requested for rating."""
    services = _request_value(rate_request, "services", []) or []

    if isinstance(services, str):
        services = [services]

    package_formats = _rate_request_package_formats(rate_request)
    resolved = set()

    for service in services:
        for resolved_service in _resolve_rate_service_codes(
            service,
            package_formats=package_formats,
        ):
            if resolved_service not in [None, ""]:
                resolved.add(resolved_service)

    return resolved

def _rate_request_insurance_amount(
    rate_request: typing.Any,
) -> typing.Optional[float]:
    """
    Resolve requested Karrio insurance coverage from the rate request.

    Karrio UI sends:

        options.insurance = <coverage value>

    Royal Mail uses services.csv included_compensation to decide which services
    can satisfy that requested coverage.
    """
    options = _request_value(rate_request, "options", {}) or {}

    declared_value = _option_value(
        options,
        "declared_value",
        "declaredValue",
    )

    return provider_units.resolve_insurance_coverage_amount(
        options,
        declared_value=declared_value,
    )


def _with_royalmail_compensation_rate_meta(
    rate: models.RateDetails,
) -> models.RateDetails:
    """
    Add Royal Mail compensation metadata to the returned rate.

    This is useful for UI/API consumers so they can see why an insured service
    was returned.
    """
    service_level = provider_units.resolve_service_level(rate.service)

    if service_level is None:
        return rate

    included_compensation = provider_units.included_compensation_amount(
        service_level
    )

    metadata = getattr(service_level, "metadata", None) or {}

    extra_meta = {
        key: value
        for key, value in {
            "included_compensation": included_compensation,
            "service_register_code": metadata.get("service_register_code"),
            "package_format_identifier": metadata.get("package_format_identifier"),
            "package_format_kind": metadata.get("package_format_kind"),
        }.items()
        if value not in [None, ""]
    }

    if not extra_meta:
        return rate

    return attr.evolve(
        rate,
        meta={
            **(rate.meta or {}),
            **extra_meta,
        },
    )

def _filter_package_rates_by_package_format(
    response: typing.List[typing.Tuple[str, typing.Any]],
    rate_request: typing.Any,
    settings: provider_settings.Settings,
) -> typing.List[typing.Tuple[str, typing.Any]]:
    """
    Remove locally rated services that are incompatible with requested Royal
    Mail package format and requested Karrio insurance coverage.

    Karrio UI insurance flow:
        Add insurance coverage
        Coverage value = 2100

    Payload:
        options.insurance = 2100

    Royal Mail behaviour:
        only return services where services.csv included_compensation >= 2100.
    """
    package_formats = _rate_request_package_formats(rate_request)
    requested_services = _requested_rate_services(rate_request)
    requested_insurance = _rate_request_insurance_amount(rate_request)

    filtered_response = []

    for index, item in enumerate(response):
        reference, package_result = item
        rates, messages = package_result
        messages = list(messages or [])

        package_format = (
            package_formats[index]
            if index < len(package_formats)
            else None
        )

        package_filtered_rates = [
            rate
            for rate in rates
            if provider_units.service_supports_package_format(
                rate.service,
                package_format,
            )
        ]

        filtered_rates = [
            _with_royalmail_compensation_rate_meta(rate)
            for rate in package_filtered_rates
            if provider_units.service_supports_insurance(
                rate.service,
                requested_insurance,
            )
        ]

        filtered_service_codes = {rate.service for rate in filtered_rates}
        package_filtered_service_codes = {
            rate.service for rate in package_filtered_rates
        }

        removed_package_requested_services = [
            rate.service
            for rate in rates
            if rate.service in requested_services
            and rate.service not in package_filtered_service_codes
        ]

        if any(removed_package_requested_services):
            messages.append(
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code="package_format_not_supported",
                    message=(
                        "The requested Royal Mail service is not compatible "
                        f"with package format `{package_format}`: "
                        f"{', '.join(removed_package_requested_services)}"
                    ),
                )
            )

        removed_insurance_requested_services = [
            rate.service
            for rate in package_filtered_rates
            if rate.service in requested_services
            and rate.service not in filtered_service_codes
        ]

        if requested_insurance is not None and any(
            removed_insurance_requested_services
        ):
            messages.append(
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code="insurance_coverage_not_supported",
                    message=(
                        "The requested Royal Mail service does not include "
                        f"enough compensation for insurance coverage "
                        f"`{requested_insurance}`: "
                        f"{', '.join(removed_insurance_requested_services)}"
                    ),
                    details={
                        "requested_coverage": requested_insurance,
                        "operation": "rating",
                    },
                )
            )

        filtered_response.append((reference, (filtered_rates, messages)))

    return filtered_response



class Proxy(rating_proxy.RatingMixinProxy, proxy.Proxy):
    """Royal Mail HTTP proxy that sends serialized Karrio requests to carrier APIs."""
    settings: provider_settings.Settings

    def get_rates(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Rate Royal Mail services locally using Karrio universal rating tables."""
        original_rate_request = request.serialize()

        service_normalized_request = _normalize_rate_request_services_for_rating(
            original_rate_request
        )

        normalized_request = lib.Serializable(
            _normalize_rate_request_for_universal_rating(
                service_normalized_request
            )
        )

        response = rating_proxy.RatingMixinProxy(
            settings=_settings_for_universal_rating(
                self.settings,
                rate_request=original_rate_request,
            ),
        ).get_rates(normalized_request).deserialize()

        return lib.Deserializable(
            _filter_package_rates_by_package_format(
                response,
                original_rate_request,
                self.settings,
            )
        )

    def create_shipment(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Send a Click & Drop order creation request."""
        response = lib.request(
            url=f"{self.settings.server_url}/orders",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def create_return_shipment(
        self,
        request: lib.Serializable,
    ) -> lib.Deserializable[dict]:
        """Send a Royal Mail return shipment request."""
        response = lib.request(
            url=f"{self.settings.server_url}/returns",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def cancel_shipment(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Send a Click & Drop order cancellation request."""
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}",
            trace=self.trace_as("json"),
            method="DELETE",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def create_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Send a Click & Drop manifest creation request."""
        response = lib.request(
            url=f"{self.settings.server_url}/manifests",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Fetch Click & Drop manifest details."""
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/manifests/{payload['manifestIdentifier']}",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def retry_manifest(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Retry a Click & Drop manifest operation."""
        payload = request.serialize()
        response = lib.request(
            url=(
                f"{self.settings.server_url}/manifests/retry/"
                f"{payload['manifestIdentifier']}"
            ),
            trace=self.trace_as("json"),
            method="POST",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_label(self, request: lib.Serializable) -> lib.Deserializable[typing.Any]:
        """Fetch a Click & Drop order label document."""
        payload = request.serialize()
        qs = _normalize_query(payload.get("query"))

        url = f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}/label"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("binary"),
            method="GET",
            headers=self.settings.label_headers,
            # Important: labels are application/pdf. Do not let lib.request decode
            # PDF bytes as UTF-8/ISO text, otherwise base64 encoding later can
            # corrupt the label.
            decoder=lambda content: content,
        )

        return lib.Deserializable(response, lambda x: x)

    def update_order_status(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Update the status of Click & Drop orders."""
        response = lib.request(
            url=f"{self.settings.server_url}/orders/status",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="PUT",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_order(self, request: lib.Serializable) -> lib.Deserializable[typing.Any]:
        """Fetch one Click & Drop order."""
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def list_orders(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """List Click & Drop orders using query parameters."""
        payload = request.serialize()
        qs = _normalize_query(payload)

        url = f"{self.settings.server_url}/orders"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_order_details(
        self,
        request: lib.Serializable,
    ) -> lib.Deserializable[typing.Any]:
        """Fetch detailed Click & Drop order data."""
        payload = request.serialize()
        response = lib.request(
            url=f"{self.settings.server_url}/orders/{payload['orderIdentifiers']}/full",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def list_order_details(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Fetch detailed data for multiple Click & Drop orders."""
        payload = request.serialize()
        qs = _normalize_query(payload)

        url = f"{self.settings.server_url}/orders/full"
        if qs:
            url = f"{url}?{qs}"

        response = lib.request(
            url=url,
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_return_services(
        self,
        request: lib.Serializable = None,
    ) -> lib.Deserializable[dict]:
        """Fetch Click & Drop return service definitions."""
        response = lib.request(
            url=f"{self.settings.server_url}/returns/services",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def get_version(self, request: lib.Serializable = None) -> lib.Deserializable[dict]:
        """Fetch the Click & Drop API version endpoint."""
        response = lib.request(
            url=f"{self.settings.server_url}/version",
            trace=self.trace_as("json"),
            method="GET",
            headers=self.settings.headers,
        )
        return lib.Deserializable(response, lib.to_dict)

    def authenticate(
        self,
        request: lib.Serializable = None,
    ) -> lib.Deserializable[dict]:
        """Return stored tracking credentials without performing an OAuth flow."""
        return lib.Deserializable(
            {
                "access_token": self.settings.api_key,
                "token_type": "Bearer",
            }
        )

    def _get_click_and_drop_tracking(
        self,
        tracking_numbers: typing.List[str],
        options: typing.Optional[dict] = None,
        reference: typing.Optional[str] = None,
    ) -> lib.Deserializable[typing.List[typing.Tuple[str, dict]]]:
        """Fallback tracking through Click & Drop order details.

        The Karrio tracking number remains the Royal Mail tracking number.

        Royal Mail Click & Drop full-order lookup is performed with Karrio's
        saved `orderReference`, quoted and percent-encoded.

        It cannot retrieve `/orders/{orderIdentifiers}/full` by tracking number
        alone. only the royal mail tracking api can do this
        """

        _trace = self.trace_as("json")
        results: typing.Dict[str, dict] = {}
        options = options or {}

        def _is_click_and_drop_error_item(item: typing.Any) -> bool:
            """Return whether a Click & Drop fallback item represents an error."""
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
                ]
            )

        lookup_items = []

        for index, tracking_number in enumerate(tracking_numbers):
            lookup = _click_and_drop_lookup_for_tracking_number(
                tracking_number,
                index,
                len(tracking_numbers),
                options,
                reference=reference,
            )

            if lookup is None:
                results[tracking_number] = _missing_click_and_drop_lookup_response(
                    tracking_number
                )
                continue

            lookup_items.append(
                {
                    "tracking_number": tracking_number,
                    "lookup": lookup,
                }
            )

        for chunk in _chunks(lookup_items, size=100):
            chunk_tracking_numbers = [
                item["tracking_number"]
                for item in chunk
            ]
            chunk_lookups = [
                item["lookup"]
                for item in chunk
            ]

            response = lib.request(
                url=_click_and_drop_order_details_url(self.settings, chunk_lookups),
                trace=_trace,
                method="GET",
                headers=self.settings.headers,
            )

            if response is None or not any(str(response).strip()):
                for tracking_number in chunk_tracking_numbers:
                    results[tracking_number] = _click_and_drop_tracking_response(
                        {},
                        lookup_identifier=tracking_number,
                    )
                continue

            data = lib.to_dict(response)

            if not isinstance(data, list):
                for tracking_number in chunk_tracking_numbers:
                    results[tracking_number] = _click_and_drop_tracking_response(
                        data,
                        lookup_identifier=tracking_number,
                    )
                continue

            orders = [
                item
                for item in data
                if isinstance(item, dict)
                and any(
                    key in item
                    for key in [
                        "orderIdentifier",
                        "orderReference",
                        "orderStatus",
                        "trackingNumber",
                        "shippingDetails",
                    ]
                )
            ]
            error_items = [
                item
                for item in data
                if _is_click_and_drop_error_item(item)
                and item not in orders
            ]

            order_map: typing.Dict[str, dict] = {}

            for order in orders:
                for key in _click_and_drop_order_keys(order):
                    order_map[key] = order

            for item in chunk:
                tracking_number = item["tracking_number"]
                lookup_value = item["lookup"].get("value")

                possible_keys = [
                    tracking_number,
                    lookup_value,
                    str(lookup_value).strip() if lookup_value is not None else None,
                ]

                order = next(
                    (
                        order_map.get(str(key).strip())
                        for key in possible_keys
                        if key is not None and str(key).strip() in order_map
                    ),
                    None,
                )

                if order is None and len(chunk) == 1 and len(orders) == 1:
                    order = orders[0]

                if order is not None:
                    payload = order
                elif any(error_items):
                    payload = error_items
                else:
                    payload = {}

                results[tracking_number] = _click_and_drop_tracking_response(
                    payload,
                    lookup_identifier=tracking_number,
                )

        return lib.Deserializable(
            [
                (tracking_number, results.get(tracking_number, {}))
                for tracking_number in tracking_numbers
            ],
            lambda pairs: [
                (tracking_number, response)
                for tracking_number, response in pairs
                if response is not None
            ],
        )

    def get_tracking(
        self,
        request: lib.Serializable,
    ) -> lib.Deserializable[typing.List[typing.Tuple[str, dict]]]:
        """Fetch tracking using the Tracking API with optional Click & Drop fallback."""
        payload = request.serialize()

        if isinstance(payload, dict):
            tracking_numbers = payload.get("tracking_numbers") or []
            options = payload.get("options") or {}
            reference = payload.get("reference")
        else:
            tracking_numbers = payload or []
            options = {}
            reference = None

        if not self.settings.has_tracking_credentials:
            return self._get_click_and_drop_tracking(
                tracking_numbers,
                options=options,
                reference=reference,
            )

        _trace = self.trace_as("json")
        results: typing.Dict[str, dict] = {}

        for chunk in _chunks(tracking_numbers, size=30):
            summary_response = lib.request(
                url=_summary_url(self.settings, chunk),
                trace=_trace,
                method="GET",
                headers=self.settings.tracking_headers,
            )

            if summary_response is None or not any(str(summary_response).strip()):
                for tracking_number in chunk:
                    results[tracking_number] = {
                        "summary": {},
                        "events": None,
                        "signature": None,
                    }
                continue

            summary_data = lib.to_dict(summary_response)

            if (
                isinstance(summary_data, dict)
                and any(
                    key in summary_data
                    for key in ["httpCode", "httpMessage", "errors"]
                )
                and not summary_data.get("mailPieces")
            ):
                for tracking_number in chunk:
                    results[tracking_number] = {
                        "summary": summary_data,
                        "events": None,
                        "signature": None,
                    }
                continue

            summary_map = {}
            for mail_piece in (summary_data or {}).get("mailPieces", []) or []:
                if not isinstance(mail_piece, dict):
                    continue

                for key in _summary_piece_keys(mail_piece):
                    summary_map[key] = mail_piece

            for tracking_number in chunk:
                summary_piece = summary_map.get(tracking_number)

                results[tracking_number] = {
                    "summary": (
                        {"mailPieces": [summary_piece]}
                        if summary_piece is not None
                        else {"mailPieces": []}
                    ),
                    "events": None,
                    "signature": None,
                }

        for tracking_number in tracking_numbers:
            tracking_data = results.get(tracking_number) or {}
            summary_payload = tracking_data.get("summary") or {}
            summary_piece = next(iter(summary_payload.get("mailPieces") or []), None)

            if isinstance(summary_payload, dict) and any(
                key in summary_payload
                for key in ["httpCode", "httpMessage", "errors"]
            ):
                continue

            if _summary_piece_has_error(summary_piece):
                continue

            events_response = lib.request(
                url=_events_url(self.settings, tracking_number, summary_piece),
                trace=_trace,
                method="GET",
                headers=self.settings.tracking_headers,
            )

            if events_response is None or not any(str(events_response).strip()):
                results[tracking_number] = tracking_data
                continue

            events_data = lib.to_dict(events_response)
            tracking_data["events"] = events_data

            signature_url = _signature_url(self.settings, tracking_number, events_data)
            if signature_url is not None:
                signature_response = lib.request(
                    url=signature_url,
                    trace=_trace,
                    method="GET",
                    headers=self.settings.tracking_headers,
                )

                if signature_response is not None and any(
                    str(signature_response).strip()
                ):
                    signature_payload = lib.to_dict(signature_response)

                    if (
                        isinstance(signature_payload, dict)
                        and signature_payload.get("mailPieces")
                    ):
                        tracking_data["signature"] = signature_payload

            results[tracking_number] = tracking_data

        return lib.Deserializable(
            [
                (tracking_number, results.get(tracking_number, {}))
                for tracking_number in tracking_numbers
            ],
            lambda pairs: [
                (tracking_number, response)
                for tracking_number, response in pairs
                if response is not None
            ],
        )