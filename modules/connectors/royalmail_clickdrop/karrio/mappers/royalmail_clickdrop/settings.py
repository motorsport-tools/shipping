"""Karrio Royal Mail Click and Drop client settings."""

import attr
import karrio.providers.royalmail_clickdrop.utils as provider_utils


@attr.s(auto_attribs=True)
class Settings(provider_utils.Settings):
    """Royal Mail Click and Drop connection settings."""

    api_key: str
    #for future use of import and export accounts
    account_number: str = None

    id: str = None
    test_mode: bool = False
    carrier_id: str = "royalmail_clickdrop"
    account_country_code: str = None
    metadata: dict = attr.Factory(dict)
    config: dict = attr.Factory(dict)
