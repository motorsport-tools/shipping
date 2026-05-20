"""Karrio Royal Mail Click and Drop client settings."""

import attr
import typing
import jstruct
import karrio.core.models as models
import karrio.providers.royalmail.units as provider_units
import karrio.providers.royalmail.utils as provider_utils
import karrio.universal.mappers.rating_proxy as rating_proxy


@attr.s(auto_attribs=True)
class Settings(provider_utils.Settings, rating_proxy.RatingMixinSettings):
    """Royal Mail Click and Drop connection settings."""

    click_and_drop_api_key: str = attr.ib(metadata={"sensitive": True})

    # Important: use plain `str = None` here, not `typing.Optional[str]`,
    # because Karrio's connection_fields introspection does not currently
    # normalize Optional[...] into "string" for the config UI.
    tracking_client_id: str = None
    tracking_client_secret: str = attr.ib(
        default=None,
        metadata={"sensitive": True},
    )

    id: str = None
    test_mode: bool = False
    carrier_id: str = "royalmail"
    account_country_code: str = None
    services: typing.List[models.ServiceLevel] = jstruct.JList[
        models.ServiceLevel,
        False,
        dict(default=provider_units.DEFAULT_SERVICES),
    ]  # type: ignore

    metadata: dict = {}
    config: dict = {}

    @property
    def configured_shipping_service_codes(self) -> typing.List[str]:
        """
        Normalize configured service selectors from connection config into
        active canonical Karrio `service_code` values.

        Royal Mail Click & Drop carrier service codes are often ambiguous.

        Example:
            OTA -> International Tracked Large Letter
            OTA -> International Tracked Small Parcel
            OTA -> International Tracked Medium Parcel

        For connection-level config we do not know the parcel format yet, so an
        ambiguous raw carrier code expands to all matching active Karrio service
        codes. The proxy later narrows the request by package format.
        """
        configured = self.connection_config.shipping_services.state or []

        if not any(configured):
            return []

        service_codes = []

        for service in configured:
            service_codes.extend(
                provider_units.resolve_rate_service_codes(
                    service,
                    package_formats=None,
                )
            )

        return list(
            dict.fromkeys(
                service_code
                for service_code in service_codes
                if service_code not in [None, ""]
            )
        )

    @property
    def configured_shipping_option_names(self) -> typing.List[str]:
        """
        Normalize configured option selectors from connection config into
        canonical Royal Mail shipping option names.
        """
        configured = self.connection_config.shipping_options.state or []

        if not any(configured):
            return []

        return provider_units.shipping_option_names_initializer(configured)

    @property
    def shipping_services(self) -> typing.List[models.ServiceLevel]:
        """
        Return active shipping services, optionally filtered by
        `config.shipping_services`.

        Important:
        Do not use `self.services or DEFAULT_SERVICES` here.

        An empty service list can be intentional after active filtering. For
        example, if a rate table row arrives with active="False", the runtime
        active filter should produce [] and must not fall back to every default
        Royal Mail service.
        """
        raw_services = (
            self.services
            if self.services is not None
            else provider_units.DEFAULT_SERVICES
        )

        base_services = provider_units.active_service_levels(raw_services)
        configured = self.connection_config.shipping_services.state or []

        if not any(configured):
            return base_services

        allowed_service_codes = set(self.configured_shipping_service_codes)

        return [
            service
            for service in base_services
            if service.service_code in allowed_service_codes
        ]

    @property
    def shipping_option_names(self) -> typing.List[str]:
        """
        Return canonical shipping option names only, optionally filtered by
        `config.shipping_options`.
        """
        if not any(self.connection_config.shipping_options.state or []):
            return sorted(provider_units.canonical_shipping_option_names())

        return self.configured_shipping_option_names

    def is_shipping_service_allowed(self, service: typing.Any) -> bool:
        """
        Check whether a requested service is allowed by `config.shipping_services`.
        Supports canonical Karrio service codes and raw Royal Mail carrier codes.
        """
        configured = self.connection_config.shipping_services.state or []

        if not any(configured):
            return True

        allowed_services = list(self.shipping_services or [])
        allowed_service_codes = {
            item.service_code
            for item in allowed_services
            if provider_units.service_is_active(item)
        }
        allowed_carrier_codes = {
            str(item.carrier_service_code or "").strip().upper()
            for item in allowed_services
            if item.carrier_service_code and provider_units.service_is_active(item)
        }

        resolved_service_code = provider_units.resolve_service_code(service)

        if resolved_service_code in allowed_service_codes:
            return True

        carrier_service_code = provider_units.resolve_carrier_service(service)

        if carrier_service_code and str(carrier_service_code).strip().upper() in allowed_carrier_codes:
            return True

        return False

    def is_shipping_option_allowed(self, option_name: typing.Optional[str]) -> bool:
        """
        Check whether a shipping option is allowed by `config.shipping_options`.
        """
        configured = self.connection_config.shipping_options.state or []

        if not any(configured):
            return True

        normalized_name = provider_units.normalize_shipping_option_name(option_name)

        if normalized_name is None:
            return True

        return normalized_name in set(self.shipping_option_names)