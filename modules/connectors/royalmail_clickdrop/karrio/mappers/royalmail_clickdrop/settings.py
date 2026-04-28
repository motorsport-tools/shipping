"""Karrio Royal Mail Click and Drop client settings."""

import attr
import typing
import jstruct
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
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

    # Keeping the existing pattern used across connectors for now.
    metadata: dict = {}
    config: dict = {}

    @property
    def shipping_services(self) -> typing.List[models.ServiceLevel]:
        if any(self.services or []):
            return self.services

        return provider_units.DEFAULT_SERVICES