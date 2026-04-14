"""Karrio Royal Mail Click and Drop manifest creation implementation."""

import typing

import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.manifest_request as royalmail_clickdrop_req
import karrio.schemas.royalmail_clickdrop.manifest_response as royalmail_clickdrop_res


def parse_manifest_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ManifestDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    if any(messages):
        return None, messages

    manifest = _extract_details(response, settings)

    return manifest, messages


def _extract_details(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.Optional[models.ManifestDetails]:
    manifest = lib.to_object(royalmail_clickdrop_res.ManifestResponseType, data)

    if manifest.manifestNumber is None:
        return None

    return models.ManifestDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        doc=models.ManifestDocument(
            manifest=manifest.documentPdf
        ) if manifest.documentPdf else None,
        meta=dict(
            manifest_number=manifest.manifestNumber,
            status="completed" if manifest.documentPdf else "in_progress",
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

    if not carrier_name:
        raise ValueError(
            "Royal Mail Click & Drop manifest requests require `carrier_name` "
            "in request options or connection config"
        )

    request = royalmail_clickdrop_req.ManifestRequestType(
        carrierName=carrier_name,
    )

    return lib.Serializable(request, lib.to_dict)
