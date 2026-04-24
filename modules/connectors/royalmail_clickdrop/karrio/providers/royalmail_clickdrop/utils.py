import base64
import datetime
import typing
from urllib.parse import quote

import karrio.core.units as units
import karrio.lib as lib
import karrio.core as core


class Settings(core.Settings):
    """Royal Mail Click and Drop connection settings."""

    api_key: str

    tracking_client_id: str = None
    tracking_client_secret: str = None

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

    @property
    def label_type(self) -> str:
        return self.connection_config.label_type.state or "PDF"

    @property
    def default_currency(self) -> typing.Optional[str]:
        if self.account_country_code in SUPPORTED_COUNTRY_CURRENCY:
            return units.CountryCurrency.map(self.account_country_code).value

        return "GBP"

    @property
    def tracking_server_url(self):
        return (
            self.connection_config.tracking_base_url.state
            or "https://api.royalmail.net"
        ).rstrip("/")

    @property
    def tracking_headers(self) -> dict:
        if not all([self.tracking_client_id, self.tracking_client_secret]):
            raise ValueError(
                "Royal Mail tracking requires `tracking_client_id` and `tracking_client_secret`."
            )

        return {
            "Accept": "application/json",
            "X-IBM-Client-Id": self.tracking_client_id,
            "X-IBM-Client-Secret": self.tracking_client_secret,
            "X-Accept-RMG-Terms": "yes",
        }


def clean_payload(value):
    """
    Recursively clean serializer artifacts from generated schema payloads.

    Safe behavior:
    - removes None values from dicts
    - removes None entries from lists
    - converts empty lists to None
    - preserves empty dicts
    - preserves False, 0, and empty strings
    """
    if isinstance(value, dict):
        cleaned = {
            key: clean_payload(item)
            for key, item in value.items()
        }

        return {
            key: item
            for key, item in cleaned.items()
            if item is not None
        }

    if isinstance(value, list):
        cleaned = [clean_payload(item) for item in value]
        cleaned = [item for item in cleaned if item is not None]

        return cleaned or None

    return value


def _format_order_identifier(
    value: typing.Any,
    treat_numeric_as_reference: bool = False,
) -> str:
    """
    Royal Mail orderIdentifiers rules:
    - numeric order identifiers are passed as-is
    - order references must be percent-encoded and wrapped in double quotes

    Karrio commonly stores carrier-generated order identifiers as strings
    (for example "12345678"), so digit-only strings are still treated as
    numeric identifiers by default.

    Use `treat_numeric_as_reference=True` when the caller explicitly supplied
    a Royal Mail order reference, even if that reference only contains digits.
    """
    if value is None:
        return ""

    if isinstance(value, int) and not treat_numeric_as_reference:
        return str(value)

    text = str(value).strip()
    if text == "":
        return ""

    if text.isdigit() and not treat_numeric_as_reference:
        return text

    return quote(f'"{text}"', safe="")


def get_value(obj, name: str, default=None):
    """Return a field from either a dict payload or an object instance."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def to_datetime_string(value):
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        return value.isoformat()

    if isinstance(value, datetime.date):
        return datetime.datetime.combine(
            value,
            datetime.time.min,
            tzinfo=datetime.timezone.utc,
        ).isoformat()

    return value


def make_order_identifiers(
    value: typing.Any,
    treat_numeric_as_reference: bool = False,
) -> str:
    if isinstance(value, (list, tuple, set)):
        identifiers = [
            _format_order_identifier(
                v,
                treat_numeric_as_reference=treat_numeric_as_reference,
            )
            for v in value
            if v is not None
        ]
        identifiers = [v for v in identifiers if v]
        if len(identifiers) > 100:
            raise ValueError(
                "Royal Mail Click & Drop supports a maximum of 100 order identifiers"
            )
        return ";".join(identifiers)

    return _format_order_identifier(
        value,
        treat_numeric_as_reference=treat_numeric_as_reference,
    )


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


NO_TRACKING_NUMBER = "no code provided"


def resolve_tracking_number(*values: typing.Any) -> str:
    for value in values:
        if value is None:
            continue

        if isinstance(value, (list, tuple, set)):
            tracking_number = resolve_tracking_number(*value)
            if tracking_number != NO_TRACKING_NUMBER:
                return tracking_number

            continue

        text = str(value).strip()
        if text:
            return text

    return NO_TRACKING_NUMBER


def get_option(options, name: str, default=None):
    if options is None:
        return default

    if isinstance(options, dict):
        return options.get(name, default)

    if hasattr(options, name):
        value = getattr(options, name)
        return _option_value(value)

    return default


SUPPORTED_COUNTRY_CURRENCY = ["GB"]