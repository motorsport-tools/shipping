import base64
import typing
from urllib.parse import quote

import karrio.lib as lib
import karrio.core as core


class Settings(core.Settings):
    """Royal Mail Click and Drop connection settings."""

    api_key: str
    #for future use import and export
    account_number: str = None

    @property
    def carrier_name(self):
        return "royalmail_clickdrop"

    @property
    def connection_config(self) -> lib.units.Options:
        from karrio.providers.royalmail_clickdrop.units import ConnectionConfig

        return lib.to_connection_config(
            self.config or {},
            option_type=ConnectionConfig,
        )

    @property
    def server_url(self):
        return (
            self.connection_config.base_url.state
            or "https://api.parcel.royalmail.com/api/v1"
        ).rstrip("/")

    @property
    def shipping_carrier_name(self) -> typing.Optional[str]:
        return self.connection_config.carrier_name.state

    @property
    def authorization(self) -> str:
        return f"Bearer {self.api_key}"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": self.authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def label_headers(self) -> dict:
        return {
            "Authorization": self.authorization,
            "Accept": "application/pdf, application/json",
        }


def _format_order_identifier(value: typing.Any) -> str:
    """
    Royal Mail orderIdentifiers rules:
    - integers are passed as-is
    - string references must be percent-encoded and wrapped in double quotes
    """
    if value is None:
        return ""

    text = str(value).strip()
    if text == "":
        return ""

    if text.isdigit():
        return text

    return f'"{quote(text, safe="")}"'


def make_order_identifiers(value: typing.Any) -> str:
    if isinstance(value, (list, tuple, set)):
        identifiers = [_format_order_identifier(v) for v in value if v is not None]
        identifiers = [v for v in identifiers if v]
        if len(identifiers) > 100:
            raise ValueError("Royal Mail Click & Drop supports a maximum of 100 order identifiers")
        return ";".join(identifiers)

    return _format_order_identifier(value)

# added for later use not finished yet decoding and encoding pdfs
def encode_document(content: bytes) -> str:
    return base64.b64encode(content).decode("utf-8")


def decode_document(content: typing.Optional[str]) -> typing.Optional[bytes]:
    if not content:
        return None

    try:
        return base64.b64decode(content)
    except (TypeError, ValueError):

        return None


def _option_value(option):
    if option is None:
        return None

    if hasattr(option, "state"):
        return option.state

    return option


def get_option(options, name: str, default=None):
    if options is None:
        return default

    if isinstance(options, dict):
        return options.get(name, default)

    if hasattr(options, name):
        value = getattr(options, name)
        return _option_value(value)

    return default
