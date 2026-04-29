"""Royal Mail Click and Drop server hooks."""

from __future__ import annotations

import copy
import typing

from django.db import transaction
from django.db.models.signals import post_save

from karrio.providers.royalmail_clickdrop.utils import (
    DEFAULT_CLICK_AND_DROP_API_BASE_URL,
    DEFAULT_LABEL_TYPE,
    DEFAULT_TRACKING_API_BASE_URL,
)


_REGISTERED = False
_TRACKING_CAPABILITY = "tracking"
_TRACKING_FIELDS = ("tracking_client_id", "tracking_client_secret")
_DEFAULT_CONNECTION_CONFIG = {
    "include_label_in_response": True,
    "include_return_label_in_response": False,
    "click_and_drop_api_base_url": DEFAULT_CLICK_AND_DROP_API_BASE_URL,
    "tracking_api_base_url": DEFAULT_TRACKING_API_BASE_URL,
    "carrier_name": "Royal Mail",
    "label_type": DEFAULT_LABEL_TYPE,
}


def _get_credentials(instance) -> dict:
    getter = getattr(instance, "get_credentials", None)
    if callable(getter):
        try:
            return dict(getter() or {})
        except Exception:
            pass

    return dict(getattr(instance, "credentials", None) or {})


def _has_tracking_credentials(instance) -> bool:
    credentials = _get_credentials(instance)

    return all(
        str(credentials.get(field) or "").strip()
        for field in _TRACKING_FIELDS
    )


def _merge_tracking_capability(
    capabilities: typing.Iterable[str],
    enabled: bool,
) -> typing.List[str]:
    items = [
        capability
        for capability in list(capabilities or [])
        if capability and capability != _TRACKING_CAPABILITY
    ]

    if enabled:
        items.append(_TRACKING_CAPABILITY)

    return items


def get_default_connection_config() -> dict:
    import karrio.providers.royalmail_clickdrop.units as units

    discovered_defaults = {
        option.name: copy.deepcopy(option.value.default)
        for option in list(units.ConnectionConfig)
        if getattr(option.value, "default", None) is not None
    }

    return {
        **copy.deepcopy(_DEFAULT_CONNECTION_CONFIG),
        **discovered_defaults,
    }


def _populate_default_config(sender, connection_id):
    instance = sender.objects.filter(pk=connection_id).first()
    if instance is None or getattr(instance, "carrier_code", None) != "royalmail":
        return

    current_config = dict(getattr(instance, "config", None) or {})
    default_config = get_default_connection_config()
    merged_config = {**default_config, **current_config}

    if merged_config != current_config:
        sender.objects.filter(pk=connection_id).update(config=merged_config)


def _sync_tracking_capability(sender, connection_id):
    instance = sender.objects.filter(pk=connection_id).first()
    if instance is None or getattr(instance, "carrier_code", None) != "royalmail":
        return

    current = list(getattr(instance, "capabilities", None) or [])
    updated = _merge_tracking_capability(
        current,
        enabled=_has_tracking_credentials(instance),
    )

    if updated != current:
        sender.objects.filter(pk=connection_id).update(capabilities=updated)


def populate_default_config(
    sender,
    instance,
    created=False,
    raw=False,
    update_fields=None,
    **kwargs,
):
    """Backfill Royal Mail connection config defaults after save."""
    if raw or instance is None or getattr(instance, "pk", None) is None:
        return

    transaction.on_commit(lambda: _populate_default_config(sender, instance.pk))


def sync_tracking_capability(
    sender,
    instance,
    created=False,
    raw=False,
    update_fields=None,
    **kwargs,
):
    """Enable tracking only when Royal Mail Tracking API credentials are configured."""
    if raw or instance is None or getattr(instance, "pk", None) is None:
        return

    transaction.on_commit(lambda: _sync_tracking_capability(sender, instance.pk))


def register():
    global _REGISTERED

    if _REGISTERED:
        return

    from karrio.server.providers.models import CarrierConnection, SystemConnection

    for model, suffix in [
        (CarrierConnection, "carrier"),
        (SystemConnection, "system"),
    ]:
        post_save.connect(
            populate_default_config,
            sender=model,
            dispatch_uid=f"royalmail_clickdrop_populate_default_config_{suffix}",
            weak=False,
        )
        post_save.connect(
            sync_tracking_capability,
            sender=model,
            dispatch_uid=f"royalmail_clickdrop_sync_tracking_capability_{suffix}",
            weak=False,
        )

    _REGISTERED = True