"""Karrio Royal Mail Click and Drop shipment label retrieval."""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default) if obj is not None else default


def label_request(payload, settings: provider_utils.Settings) -> lib.Serializable:
    order_identifiers = (
        _get(payload, "order_identifiers")
        or _get(payload, "shipment_identifier")
        or _get(payload, "reference")
    )

    resolved_order_identifiers = provider_utils.make_order_identifiers(order_identifiers)

    if not resolved_order_identifiers:
        raise ValueError(
            "Royal Mail Click & Drop label requests require "
            "`order_identifiers`, `shipment_identifier`, or `reference`"
        )

    document_type = _get(payload, "document_type", "postageLabel")
    include_returns_label = _get(payload, "include_returns_label")
    include_cn = _get(payload, "include_cn")

    if document_type == "postageLabel" and include_returns_label is None:
        include_returns_label = False

    request = {
        "orderIdentifiers": resolved_order_identifiers,
        "query": {
            "documentType": document_type,
            "includeReturnsLabel": include_returns_label if document_type == "postageLabel" else None,
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

        # Successful label response
        if normalized.startswith(b"%PDF-"):
            encoded = provider_utils.encode_document(raw)
            return models.Documents(label=encoded, pdf_label=encoded), []

        # Some carrier errors can come back as JSON bytes even when the proxy uses binary trace
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
    return None, messages