"""Karrio Royal Mail Click and Drop shipment label retrieval."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils


ALLOWED_DOCUMENT_TYPES = {"postageLabel", "despatchNote", "CN22", "CN23"}


def label_request(payload, settings: provider_utils.Settings) -> lib.Serializable:
    reference = (
        None
        if isinstance(payload, (str, int, list, tuple, set))
        else provider_utils.get_value(payload, "reference")
    )
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
            "Royal Mail Click & Drop label requests require "
            "`order_identifiers`, `orderIdentifiers`, `shipment_identifier`, `shipmentIdentifier`, or `reference`"
        )

    document_type = (
        provider_utils.get_value(payload, "document_type")
        or provider_utils.get_value(payload, "documentType")
        or "postageLabel"
    )

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError(
            "Royal Mail Click & Drop `document_type` must be one of "
            "`postageLabel`, `despatchNote`, `CN22`, or `CN23`"
        )

    include_returns_label = (
        provider_utils.get_value(payload, "include_returns_label")
        if provider_utils.get_value(payload, "include_returns_label") is not None
        else provider_utils.get_value(payload, "includeReturnsLabel")
    )
    include_cn = (
        provider_utils.get_value(payload, "include_cn")
        if provider_utils.get_value(payload, "include_cn") is not None
        else provider_utils.get_value(payload, "includeCN")
    )

    if document_type == "postageLabel" and include_returns_label is None:
        include_returns_label = False

    request = {
        "orderIdentifiers": resolved_order_identifiers,
        "query": {
            "documentType": document_type,
            "includeReturnsLabel": (
                include_returns_label
                if document_type == "postageLabel"
                else None
            ),
            "includeCN": include_cn if document_type == "postageLabel" else None,
        },
    }

    return lib.Serializable(request, lambda data: data)


def parse_label_response(
    _response: lib.Deserializable[typing.Any],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.Documents], typing.List[models.Message]]:
    response = _response.deserialize()

    if isinstance(response, (bytes, bytearray)):
        raw = bytes(response)
        normalized = raw.lstrip()

        if normalized.startswith(b"%PDF-"):
            encoded = provider_utils.encode_document(raw)
            return models.Documents(label=encoded, pdf_label=encoded), []

        try:
            response = lib.to_dict(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, TypeError, ValueError):
            return None, [
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code="label_error",
                    message="Unable to parse label response",
                    details={"operation": "get_label"},
                )
            ]

    if isinstance(response, str):
        stripped = response.lstrip()

        if stripped.startswith("%PDF-"):
            encoded = provider_utils.encode_document(response.encode("utf-8"))
            return models.Documents(label=encoded, pdf_label=encoded), []

        try:
            response = lib.to_dict(response)
        except (TypeError, ValueError):
            return None, [
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code="label_error",
                    message="Unable to parse label response",
                    details={"operation": "get_label"},
                )
            ]

    messages = error.parse_error_response(
        response,
        settings,
        context="label",
        operation="get_label",
    )

    if any(messages):
        return None, messages

    return None, [
        models.Message(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            code="label_error",
            message="Unable to parse label response",
            details={"operation": "get_label"},
        )
    ]