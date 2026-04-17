"""Karrio Royal Mail Click and Drop manifest creation and lookup implementation."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.manifest_async_response as manifest_async_res
import karrio.schemas.royalmail_clickdrop.manifest_details_response as manifest_details_res
import karrio.schemas.royalmail_clickdrop.manifest_request as manifest_req
import karrio.schemas.royalmail_clickdrop.manifest_response as manifest_res


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default) if obj is not None else default


def _normalize_status(status: typing.Optional[str], has_document: bool) -> str:
    if status:
        return status.strip().lower().replace(" ", "_")

    return "completed" if has_document else "in_progress"


def parse_manifest_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ManifestDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="manifest",
        operation="manifest",
    )

    if any(messages):
        return None, messages

    manifest = _extract_details(response, settings)

    return manifest, messages


def _extract_details(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.Optional[models.ManifestDetails]:
    if not isinstance(data, dict):
        return None

    manifest_number = None
    document_pdf = None
    status = None

    if "status" in data:
        manifest = lib.to_object(manifest_details_res.ManifestDetailsResponseType, data)
        manifest_number = manifest.manifestNumber
        document_pdf = manifest.documentPdf
        status = _normalize_status(manifest.status, manifest.documentPdf is not None)

    elif "documentPdf" in data:
        manifest = lib.to_object(manifest_res.ManifestResponseType, data)
        manifest_number = manifest.manifestNumber
        document_pdf = manifest.documentPdf
        status = _normalize_status(None, manifest.documentPdf is not None)

    else:
        manifest = lib.to_object(manifest_async_res.ManifestAsyncResponseType, data)
        manifest_number = manifest.manifestNumber
        status = "in_progress"

    if manifest_number is None:
        return None

    return models.ManifestDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        doc=(
            models.ManifestDocument(manifest=document_pdf)
            if document_pdf
            else None
        ),
        meta=dict(
            manifest_number=manifest_number,
            status=status,
            document_available=document_pdf is not None,
        ),
    )


def manifest_request(
    payload: models.ManifestRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    options = payload.options or {}
    carrier_name = (
        provider_utils.get_option(options, "carrier_name")
        or settings.shipping_carrier_name
    )

    request = manifest_req.ManifestRequestType(
        carrierName=carrier_name,
    )

    return lib.Serializable(request, lib.to_dict)


def manifest_identifier_request(
    payload: typing.Any,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    manifest_identifier = (
        payload
        if isinstance(payload, (str, int))
        else _get(payload, "manifest_identifier")
        or _get(payload, "manifestIdentifier")
        or _get(payload, "manifest_number")
        or _get(payload, "manifestNumber")
        or _get(payload, "reference")
    )

    if manifest_identifier in [None, ""]:
        raise ValueError(
            "Royal Mail Click & Drop manifest lookup requires "
            "`manifest_identifier`, `manifestIdentifier`, `manifest_number`, or `reference`"
        )

    return lib.Serializable(
        {"manifestIdentifier": manifest_identifier},
        lambda data: data,
    )