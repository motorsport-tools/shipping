"""Karrio Royal Mail Click and Drop shipment API Creat Order implementation."""

import datetime
import typing
from decimal import Decimal, ROUND_HALF_UP

import karrio.core.errors as errors
import karrio.core.models as models
import karrio.core.units as units
import karrio.lib as lib

import karrio.providers.royalmail.error as error
import karrio.providers.royalmail.units as provider_units
import karrio.providers.royalmail.utils as provider_utils
import karrio.schemas.royalmail.shipment_request as royalmail_req
import karrio.schemas.royalmail.shipment_response as royalmail_res


def _attr(obj, name, default=None):
    """Read an attribute from an object with a default fallback."""
    return getattr(obj, name, default) if obj is not None else default


def _coalesce(*values):
    """Return the first value that is not None."""
    for value in values:
        if value is not None:
            return value

    return None


def _text(value, max=None):
    """Return a stripped string value or None when empty."""
    return lib.text(value, max=max) if value is not None else None


def _first_present(*values):
    """Return the first value that is not blank."""
    for value in values:
        if value not in [None, ""]:
            return value

    return None


def _value(source, *keys, default=None):
    """Read a field from a dict or object payload."""
    for key in keys:
        value = provider_utils.get_value(source, key)
        if value not in [None, ""]:
            return value

    return default

def _option_state(source, name):
    """Read an option state value from Karrio options."""
    option = getattr(source, name, None) if source is not None else None
    return getattr(option, "state", None)




def _option_present(options, *names: str) -> bool:
    """Return whether an option was explicitly provided."""
    content = getattr(options, "content", {}) or {}
    return any(name in content for name in names)


def _explicit_option_value(options, *names: str):
    """Return an option value only when the option was explicitly set."""
    if not _option_present(options, *names):
        return None

    values = [
        getattr(getattr(options, name, None), "state", None)
        for name in names
    ]

    return _first_present(*values)

def _requested_insurance_coverage_amount(
    raw_options: dict,
) -> typing.Optional[float]:
    """
    Resolve Karrio's generic insurance option from shipment payload.options.

    Karrio UI sends:
        options.insurance = <coverage amount>

    Royal Mail Click & Drop field:
        postageDetails.consequentialLoss
    """
    declared_value = (
        provider_utils.get_option(raw_options, "declared_value")
        or provider_utils.get_option(raw_options, "declaredValue")
    )

    return provider_units.resolve_insurance_coverage_amount(
        raw_options,
        declared_value=declared_value,
    )


def _validate_selected_service_compensation(
    selected_service: typing.Optional[str],
    requested_coverage: typing.Optional[float],
):
    """
    Prevent creating a Royal Mail shipment with a service that does not include
    enough compensation for the requested Karrio insurance value.

    Rating should normally prevent this by returning only eligible services.
    This validation protects direct shipment creation / API bypass flows.
    """
    if requested_coverage is None or selected_service in [None, ""]:
        return

    service_level = provider_units.resolve_service_level(selected_service)

    # Unknown/custom services are not blocked locally.
    if service_level is None:
        return

    if provider_units.service_supports_insurance(
        service_level,
        requested_coverage,
    ):
        return

    included_compensation = provider_units.included_compensation_amount(
        service_level
    )

    raise ValueError(
        "Royal Mail Click & Drop selected service "
        f"`{service_level.service_code}` only includes compensation cover "
        f"`{included_compensation or 0}` but insurance coverage "
        f"`{requested_coverage}` was requested. Select a Royal Mail service "
        "with sufficient `included_compensation`, such as the appropriate "
        "Parcelforce Comp 1, Comp 2, or Comp 3 service."
    )

def _service_selector(service) -> typing.Optional[str]:
    """Resolve the shipment service selector from service and option fields."""
    if service in [None, ""]:
        return None

    if isinstance(service, dict):
        for key in [
            "service_code",
            "carrier_service_code",
            "code",
            "name",
            "id",
        ]:
            value = service.get(key)
            if value not in [None, ""]:
                return str(value).strip()

    for attr in [
        "service_code",
        "carrier_service_code",
        "code",
        "id",
        "value_or_key",
        "name_or_key",
        "value",
        "name",
    ]:
        value = getattr(service, attr, None)
        if value not in [None, ""]:
            return str(value).strip()

    selector = str(service).strip()
    return selector or None

def _validate_allowed_shipping_options(
    raw_options: dict,
    settings: provider_utils.Settings,
    context: str = "payload.options",
):
    """
    Enforce `config.shipping_options` for recognized Royal Mail shipment options.
    Unknown/unrelated keys are ignored here; only recognized Royal Mail/Karrio
    shipping options are checked.
    """
    configured = settings.connection_config.shipping_options.state or []
    if not any(configured):
        return

    normalized_keys = set(provider_units.normalize_option_keys(raw_options or {}).keys())
    recognized_keys = sorted(
        key for key in normalized_keys if key in provider_units.KNOWN_SHIPPING_OPTION_KEYS
    )
    blocked_keys = sorted(
        key for key in recognized_keys if not settings.is_shipping_option_allowed(key)
    )

    if any(blocked_keys):
        raise ValueError(
            f"Royal Mail Click & Drop {context} contains disallowed shipping option(s): "
            f"{', '.join(blocked_keys)}."
        )

def _raw_package_options(raw_package) -> dict:
    """Return raw per-package options from the original parcel payload."""
    options = provider_utils.get_value(raw_package, "options")
    return options if isinstance(options, dict) else {}


def _package_shipping_options(raw_package):
    """Merge shipment-level and parcel-level Royal Mail package options."""
    return provider_units.shipping_options_initializer(_raw_package_options(raw_package))


def _resolve_package_explicit_format(
    raw_package,
    shipment_explicit_package_format: typing.Optional[str] = None,
) -> typing.Optional[str]:
    """
    Parcel-level `package_format_identifier` overrides the shipment-level default.
    """
    package_options = _package_shipping_options(raw_package)

    return _first_present(
        package_options.package_format_identifier.state,
        shipment_explicit_package_format,
    )


def _validate_package_level_options(raw_parcels):
    """
    Royal Mail Click & Drop only supports `package_format_identifier` as a
    parcel-level Royal Mail shipping option.

    All other Royal Mail shipping options are shipment/order/postage-level and
    must be provided in `payload.options`.
    """
    errors = []

    for index, raw_package in enumerate(raw_parcels or []):
        raw_options = _raw_package_options(raw_package)
        if not raw_options:
            continue

        normalized_keys = set(provider_units.normalize_option_keys(raw_options).keys())
        recognized_royalmail_keys = sorted(
            key
            for key in normalized_keys
            if key in provider_units.KNOWN_SHIPPING_OPTION_KEYS
        )

        unsupported_keys = sorted(
            key
            for key in recognized_royalmail_keys
            if key not in provider_units.PACKAGE_LEVEL_OPTION_KEYS
        )

        if unsupported_keys:
            errors.append(
                f"parcel[{index}].options contains unsupported Royal Mail "
                f"package-level option(s): {', '.join(unsupported_keys)}. "
                "Only `package_format_identifier` is supported at parcel level."
            )

    if any(errors):
        raise ValueError(" ".join(errors))

def _package_format_kind(package_format: typing.Optional[str]) -> typing.Optional[str]:
    """
    Collapse package formats into the Royal Mail service-register grouping:
    - letter
    - large_letter
    - parcel

    This uses provider_units.normalize_click_and_drop_package_format_identifier()
    so aliases/case variants such as MediumParcel are treated as mediumParcel.
    """
    if package_format in [None, ""]:
        return None

    value = provider_units.normalize_click_and_drop_package_format_identifier(
        package_format
    )

    if value == provider_units.PackagingType.letter.value:
        return "letter"

    if value == provider_units.PackagingType.large_letter.value:
        return "large_letter"

    if value in [
        provider_units.PackagingType.small_parcel.value,
        provider_units.PackagingType.medium_parcel.value,
        provider_units.PackagingType.large_parcel.value,
        provider_units.PackagingType.parcel.value,
    ]:
        return "parcel"

    # Preserve unknown/custom package format identifiers.
    return value or None


def _resolve_package_formats(
    packages,
    raw_parcels,
    explicit_package_format: typing.Optional[str] = None,
) -> typing.List[str]:
    """Resolve the Royal Mail package format for each shipment parcel."""
    return [
        provider_units.resolve_package_format(
            package=package,
            raw_package=raw_parcels[index] if index < len(raw_parcels) else None,
            explicit=explicit_package_format,
        )
        for index, package in enumerate(packages)
    ]

def _validate_selected_service_package_formats(
    selected_service: typing.Optional[str],
    package_formats: typing.List[str],
):
    """
    Validate Royal Mail service/package compatibility before sending the order
    to Click & Drop.

    Compatibility is driven by the service metadata loaded from services.csv:

    - explicit package_format_identifier:
        enforce the exact configured package band

        Example:
            royal_mail_48_Small_Parcel + smallParcel  -> valid
            royal_mail_48_Small_Parcel + largeLetter  -> invalid
            royal_mail_48_LargeLetter + largeLetter   -> valid

    - blank package_format_identifier on known flexible services:
        allow Click & Drop packageFormatIdentifier to disambiguate the shipment

        Example:
            royal_mail_tracked_24 / TPN24 + letter      -> valid
            royal_mail_tracked_24 / TPN24 + largeLetter -> valid
            royal_mail_tracked_24 / TPN24 + parcel      -> valid

    - blank package_format_identifier on non-flexible services:
        enforce the inferred package kind so that letters are not treated as
        parcels, and parcels are not treated as letters.
    """
    if selected_service in [None, ""]:
        return

    resolved_service_code = provider_units.resolve_service_code(selected_service)

    # If this is an unknown custom selector, do not block it locally.
    if resolved_service_code is None:
        return

    incompatible_formats = [
        package_format
        for package_format in package_formats
        if not provider_units.service_supports_package_format(
            resolved_service_code,
            package_format,
        )
    ]

    if any(incompatible_formats):
        raise ValueError(
            "Royal Mail Click & Drop selected service "
            f"`{resolved_service_code}` is not compatible with package format(s): "
            f"{', '.join(str(value) for value in incompatible_formats)}."
        )

def _validate_selected_service_ddp_compatibility(
    selected_service: typing.Optional[str],
    duty_paid_requested: bool,
):
    """
    Enforce Royal Mail DDP/DTP service compatibility.

    Royal Mail Click & Drop supports `customsDutyCosts` only on DDP-capable
    services. Royal Mail / Parcelforce DTP products are treated as duty-paid
    products for the same filtering purpose.

    Rules:
    - DDP/DTP requests require a DDP/DTP-capable service.
    - DDP/DTP services require explicit duty-paid intent.
    """
    if selected_service in [None, ""]:
        return

    service_is_duty_paid = provider_units.service_supports_ddp(selected_service)

    if duty_paid_requested and not service_is_duty_paid:
        raise ValueError(
            "Royal Mail Click & Drop duty-paid DDP/DTP shipments require a "
            "DDP/DTP-capable Royal Mail service. The selected service "
            f"`{selected_service}` does not support DDP/DTP."
        )

    if service_is_duty_paid and not duty_paid_requested:
        raise ValueError(
            "Royal Mail Click & Drop DDP/DTP services can only be used when "
            "duty-paid customs handling is requested. Set "
            "`customs.incoterm` to `DDP` or `DTP`, provide meaningful "
            "`customs.duty` details, or set `options.duty_paid` to `true`."
        )

def _validate_multi_package_rules(package_formats: typing.List[str], package_count: int):
    """
    Royal Mail Click & Drop rule:
    - letters / large letters must be single-piece shipments
    - multi-package shipments are only valid for parcel package kinds
    """
    if package_count <= 1:
        return

    package_kinds = {
        _package_format_kind(package_format)
        for package_format in package_formats
        if package_format not in [None, ""]
    }

    if package_kinds != {"parcel"}:
        raise ValueError(
            "Royal Mail Click & Drop only supports multi-package shipments for "
            "parcel package formats. Letters and large letters must be sent as "
            "single-piece shipments."
        )

def _resolve_selected_service(payload, options):
    """Resolve the selected Karrio service into Royal Mail postage details."""
    explicit_selector = _service_selector(options.service_code.state)
    if explicit_selector is not None:
        return provider_units.resolve_service_code(explicit_selector) or explicit_selector

    preferred_selector = _service_selector(
        provider_utils.get_option(options, "preferred_service")
        or provider_utils.get_option(options, "preferredService")
    )
    if preferred_selector is not None:
        return provider_units.resolve_service_code(preferred_selector) or preferred_selector

    requested_services = (
        getattr(payload, "services", None)
        or ([payload.service] if getattr(payload, "service", None) else [])
    )

    selector = next(
        (
            resolved
            for resolved in (
                _service_selector(service) for service in requested_services
            )
            if resolved not in [None, ""]
        ),
        None,
    )

    if selector is None:
        return None

    return provider_units.resolve_service_code(selector) or selector

def _is_northern_ireland(address) -> bool:
    """Return whether an address is in Northern Ireland."""
    postcode = (
        (
            provider_utils.get_value(address, "postal_code")
            or provider_utils.get_value(address, "postcode")
            or ""
        )
        .replace(" ", "")
        .upper()
    )
    return postcode.startswith("BT")


def _is_gb_to_northern_ireland(shipper, recipient) -> bool:
    """Return whether the shipment is a GB-to-Northern-Ireland movement."""
    return (
        (provider_utils.get_value(shipper, "country_code") or "").upper() == "GB"
        and (provider_utils.get_value(recipient, "country_code") or "").upper()
        == "GB"
        and not _is_northern_ireland(shipper)
        and _is_northern_ireland(recipient)
    )

def _to_int(value, default=None):
    """Convert a value to int when possible."""
    if value in [None, ""]:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_decimal(value, default=None) -> typing.Optional[Decimal]:
    """Convert a value to Decimal when possible."""
    if value in [None, ""]:
        return default

    try:
        return Decimal(str(value))
    except Exception:
        return default


def _to_float(value, default=None):
    """Convert a value to float when possible."""
    decimal_value = _to_decimal(value, None)
    if decimal_value is None:
        return default

    return float(decimal_value)


def _quantize_money(
    value,
    field: str,
    default=None,
    minimum: typing.Optional[Decimal] = Decimal("0.00"),
    maximum: typing.Optional[Decimal] = Decimal("999999.00"),
) -> typing.Optional[float]:
    """Round a monetary value to Royal Mail's expected precision."""
    amount = _to_decimal(value, None)
    if amount is None:
        return default

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if minimum is not None and amount < minimum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be greater than or equal to {minimum}."
        )

    if maximum is not None and amount > maximum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be less than or equal to {maximum}."
        )

    return float(amount)


def _bounded_int(
    value,
    field: str,
    default=None,
    minimum: typing.Optional[int] = None,
    maximum: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a value to int and enforce Royal Mail min/max bounds."""
    number = _to_int(value, default)
    if number is None:
        return default

    if minimum is not None and number < minimum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be greater than or equal to {minimum}."
        )

    if maximum is not None and number > maximum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be less than or equal to {maximum}."
        )

    return number


def _to_bool(value, default=None):
    """Normalize common truthy and falsey option values."""
    if value in [None, ""]:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ["true", "1", "yes", "y"]:
            return True
        if normalized in ["false", "0", "no", "n"]:
            return False

    return bool(value)

def _parse_error_message(
    settings: provider_utils.Settings,
    code: str,
    message: str,
    operation: str,
) -> models.Message:
    """Extract a readable message from a Click & Drop error payload."""
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code=code,
        message=message,
        details={"operation": operation},
    )

def _validate_billing_address(billing, source_label="billing"):
    """Validate the minimum billing address fields required by Click & Drop."""
    if not billing:
        return

    address = provider_utils.get_value(billing, "address") or {}
    missing = []

    for field in ["addressLine1", "city", "countryCode"]:
        if provider_utils.get_value(address, field) in [None, ""]:
            missing.append(f"{source_label}.address.{field}")

    if missing:
        raise ValueError(
            "Royal Mail Click & Drop shipment validation failed. "
            f"Missing required billing field(s): {', '.join(missing)}"
        )


def _resolve_billing(payload, raw_options):
    """Resolve billing address data from payload and options."""
    option_billing = provider_utils.get_value(raw_options, "billing")
    if option_billing:
        _validate_billing_address(option_billing, "options.billing")
        return option_billing

    billing_address = getattr(payload, "billing_address", None)
    if billing_address is None:
        return None

    billing = lib.to_address(billing_address)
    resolved = {
        "address": {
            "fullName": billing.person_name,
            "companyName": billing.company_name,
            "addressLine1": billing.address_line1,
            "addressLine2": billing.address_line2,
            "addressLine3": billing.address_line3,
            "city": billing.city,
            "county": billing.state_code or billing.state_name,
            "postcode": billing.postal_code,
            "countryCode": billing.country_code,
        },
        "phoneNumber": billing.phone_number,
        "emailAddress": billing.email,
    }

    _validate_billing_address(resolved, "billing_address")
    return resolved

def _billing_email_address(billing) -> typing.Optional[str]:
    """Resolve the billing email address sent to Click & Drop."""
    return _first_present(
        provider_utils.get_value(billing, "emailAddress"),
        provider_utils.get_value(billing, "email_address"),
    )



def _normalize_notification_target(value) -> typing.Optional[str]:
    """Normalize notification target aliases to Royal Mail enum values."""
    if value in [None, ""]:
        return None

    normalized = str(value).strip()
    mapped = provider_units.NotificationTarget.map(normalized)

    if getattr(mapped, "enum", None) is None:
        mapped = provider_units.NotificationTarget.map(normalized.lower())

    if getattr(mapped, "enum", None) is None:
        return None

    return mapped.value_or_key


def _resolve_notification_target(
    raw_options,
    options,
    recipient,
    shipper,
    billing,
) -> typing.Optional[str]:
    """
    Resolve only the explicit Royal Mail `send_notifications_to` target.

    Important:
    - this does NOT infer email intent
    - this does NOT fall back to email_notification_to
    - this does NOT auto-pick recipient/sender/billing
    """
    explicit_target = _first_present(
        _value(raw_options, "send_notifications_to", "sendNotificationsTo"),
        _explicit_option_value(options, "send_notifications_to"),
    )

    if explicit_target in [None, ""]:
        return None

    normalized_target = _normalize_notification_target(explicit_target)

    if normalized_target is None:
        raise ValueError(
            "Royal Mail Click & Drop `send_notifications_to` must be one of "
            "`recipient`, `sender`, or `billing`."
        )

    return normalized_target

def _resolve_email_notification_target(
    raw_options,
    options,
    recipient,
    shipper,
    billing,
) -> typing.Optional[str]:
    """
    Resolve standard Karrio `email_notification_to` into one of the Royal Mail
    supported notification targets:
    - recipient
    - sender
    - billing

    Direct arbitrary email addresses are not supported by Royal Mail Click & Drop.
    """
    explicit_email_target = _first_present(
        _value(raw_options, "email_notification_to", "emailNotificationTo"),
        _explicit_option_value(options, "email_notification_to"),
    )

    if explicit_email_target in [None, ""]:
        return None

    normalized_target = _normalize_notification_target(explicit_email_target)
    if normalized_target is not None:
        return normalized_target

    lookup = {
        (recipient.email or "").strip().lower(): "recipient",
        (shipper.email or "").strip().lower(): "sender",
        (_billing_email_address(billing) or "").strip().lower(): "billing",
    }
    resolved = lookup.get(str(explicit_email_target).strip().lower())

    if resolved is None:
        raise ValueError(
            "Royal Mail Click & Drop does not support arbitrary "
            "`email_notification_to` addresses. Use `send_notifications_to` "
            "or provide an email matching recipient, sender, or billing."
        )

    return resolved


def _default_email_notification_target(
    recipient,
    shipper,
    billing,
) -> typing.Optional[str]:
    """
    Fallback target for explicitly enabled email notifications when the caller
    did not provide a target. Prefer the first entity that actually has an email.
    """
    for target, email in [
        ("recipient", recipient.email),
        ("sender", shipper.email),
        ("billing", _billing_email_address(billing)),
    ]:
        if email not in [None, ""]:
            return target

    return None

def _notification_target_has_phone(target, recipient, shipper, billing) -> bool:
    """Return whether the notification target requires a phone number."""
    phone_by_target = {
        "recipient": recipient.phone_number,
        "sender": shipper.phone_number,
        "billing": _first_present(
            provider_utils.get_value(billing, "phoneNumber"),
            provider_utils.get_value(billing, "phone_number"),
        ),
    }

    return phone_by_target.get(target) not in [None, ""]



def _resolve_notification_settings(
    raw_options,
    options,
    service,
    recipient,
    shipper,
    billing,
):
    """
    Resolve Royal Mail notification settings from shipping options.

    Rules:
    - `send_notifications_to` selects the Royal Mail target but does not enable
      any channel by itself
    - `email_notification_to` implies email notification unless email was
      explicitly disabled
    - SMS notifications require an explicit `send_notifications_to` target
    - if no notification channel is enabled, all notification fields are omitted
    """
    explicit_target = _resolve_notification_target(
        raw_options,
        options,
        recipient,
        shipper,
        billing,
    )
    explicit_email_target = _resolve_email_notification_target(
        raw_options,
        options,
        recipient,
        shipper,
        billing,
    )

    explicit_email = _to_bool(
        _explicit_option_value(
            options,
            "receive_email_notification",
            "email_notification",
        )
    )
    explicit_sms = _to_bool(
        _explicit_option_value(
            options,
            "receive_sms_notification",
            "sms_notification",
        )
    )

    carrier_service_code = (
        provider_units.resolve_carrier_service(service)
        or str(service or "").strip()
    )

    wants_email = (
        explicit_email is True
        or (
            explicit_email is not False
            and explicit_email_target not in [None, ""]
        )
    )
    wants_sms = explicit_sms is True

    resolved_target = None
    receive_email_notification = None
    receive_sms_notification = None

    if wants_email:
        if not provider_units.service_supports_email_notification(service):
            raise ValueError(
                f"Royal Mail Click & Drop service '{carrier_service_code}' "
                "does not support email notifications."
            )

        email_target = (
            explicit_target
            or explicit_email_target
            or _default_email_notification_target(recipient, shipper, billing)
        )

        if email_target is None:
            raise ValueError(
                "Royal Mail Click & Drop email notifications were requested, "
                "but no notification recipient could be resolved. "
                "Provide `send_notifications_to` (`recipient`, `sender`, or `billing`), "
                "`email_notification_to`, or an email address on the recipient, "
                "sender, or billing contact."
            )

        if not _notification_target_has_email(email_target, recipient, shipper, billing):
            raise ValueError(
                f"Royal Mail Click & Drop target '{email_target}' does not have an "
                "email address for email notifications."
            )

        resolved_target = email_target
        receive_email_notification = True

    if wants_sms:
        sms_target = explicit_target

        if sms_target is None:
            raise ValueError(
                "Royal Mail Click & Drop SMS notifications require an explicit "
                "`send_notifications_to` target."
            )

        if not _notification_target_has_phone(sms_target, recipient, shipper, billing):
            raise ValueError(
                f"Royal Mail Click & Drop target '{sms_target}' does not have a "
                "phone number for SMS notifications."
            )

        if resolved_target not in [None, sms_target]:
            raise ValueError(
                "Royal Mail Click & Drop uses a single `sendNotificationsTo` "
                "target for notifications. Use the same target for email and SMS."
            )

        resolved_target = sms_target
        receive_sms_notification = True

    return resolved_target, receive_email_notification, receive_sms_notification



def _notification_target_has_email(target, recipient, shipper, billing) -> bool:
    """Return whether the notification target requires an email address."""
    email_by_target = {
        "recipient": recipient.email,
        "sender": shipper.email,
        "billing": _billing_email_address(billing),
    }

    return email_by_target.get(target) not in [None, ""]


def _build_billing_type(billing):
    """Build the Click & Drop billing address object."""
    if billing is None:
        return None

    billing_address = provider_utils.get_value(billing, "address") or {}

    return royalmail_req.BillingType(
        address=royalmail_req.AddressType(
            fullName=_text(
                provider_utils.get_value(billing_address, "fullName"), max=210
            ),
            companyName=_text(
                provider_utils.get_value(billing_address, "companyName"), max=100
            ),
            addressLine1=_text(
                provider_utils.get_value(billing_address, "addressLine1"), max=100
            ),
            addressLine2=_text(
                provider_utils.get_value(billing_address, "addressLine2"), max=100
            ),
            addressLine3=_text(
                provider_utils.get_value(billing_address, "addressLine3"), max=100
            ),
            city=_text(provider_utils.get_value(billing_address, "city"), max=100),
            county=_text(provider_utils.get_value(billing_address, "county"), max=100),
            postcode=_text(
                provider_utils.get_value(billing_address, "postcode"), max=20
            ),
            countryCode=_text(
                provider_utils.get_value(billing_address, "countryCode"), max=3
            ),
        ),
        phoneNumber=_text(provider_utils.get_value(billing, "phoneNumber"), max=25),
        emailAddress=_text(
            provider_utils.get_value(billing, "emailAddress"), max=254
        ),
    )


def _has_importer_data(importer, options, customs=None) -> bool:
    """Return whether importer-of-record details were supplied."""
    customs_options = getattr(customs, "options", None) if customs is not None else None

    return any(
        [
            importer,
            options.importer_vat_number.state,
            options.importer_tax_code.state,
            options.importer_eori_number.state,
            _option_state(customs_options, "vat_registration_number"),
            _option_state(customs_options, "eori_number"),
        ]
    )


def _resolve_importer_country(importer) -> typing.Optional[str]:
    """Resolve the importer country code for customs data."""
    country = _value(importer, "country", "country_name")
    if country not in [None, ""]:
        return country

    country_code = _value(importer, "countryCode", "country_code")
    if country_code in [None, ""]:
        return None

    try:
        return units.Country.map(country_code).value
    except Exception:
        return str(country_code)


def _build_importer_type(importer, options, customs=None):
    """Build the Click & Drop importer object when importer data is present."""
    if not _has_importer_data(importer, options, customs):
        return None

    importer = importer or {}
    customs_options = getattr(customs, "options", None) if customs is not None else None

    return royalmail_req.ImporterType(
        companyName=_text(
            _value(importer, "companyName", "company_name"),
            max=100,
        ),
        addressLine1=_text(
            _value(importer, "addressLine1", "address_line1"),
            max=100,
        ),
        addressLine2=_text(
            _value(importer, "addressLine2", "address_line2"),
            max=100,
        ),
        addressLine3=_text(
            _value(importer, "addressLine3", "address_line3"),
            max=100,
        ),
        city=_text(_value(importer, "city"), max=100),
        postcode=_text(
            _value(importer, "postcode", "postal_code"),
            max=20,
        ),
        country=_text(
            _resolve_importer_country(importer),
            max=100,
        ),
        businessName=_text(
            _value(importer, "businessName", "business_name"),
            max=100,
        ),
        contactName=_text(
            _value(importer, "contactName", "contact_name"),
            max=100,
        ),
        phoneNumber=_text(
            _value(importer, "phoneNumber", "phone_number"),
            max=25,
        ),
        emailAddress=_text(
            _value(importer, "emailAddress", "email"),
            max=254,
        ),
        vatNumber=_text(
            _value(
                importer,
                "vatNumber",
                "vat_number",
                default=_first_present(
                    options.importer_vat_number.state,
                    _option_state(customs_options, "vat_registration_number"),
                ),
            ),
            max=15,
        ),
        taxCode=_text(
            _value(
                importer,
                "taxCode",
                "tax_code",
                default=options.importer_tax_code.state,
            ),
            max=25,
        ),
        eoriNumber=_text(
            _value(
                importer,
                "eoriNumber",
                "eori_number",
                default=_first_present(
                    options.importer_eori_number.state,
                    _option_state(customs_options, "eori_number"),
                ),
            ),
            max=18,
        ),
    )

def _item_metadata(item) -> dict:
    """Return metadata attached to a Karrio commodity item."""
    metadata = provider_utils.get_value(item, "metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _item_value(item, *keys, default=None):
    """Read a commodity value from common Karrio item fields."""
    metadata = _item_metadata(item)
    return _value(
        item,
        *keys,
        default=_value(metadata, *keys, default=default),
    )


def _normalize_country_code(value, max_length: int = 3) -> typing.Optional[str]:
    """Normalize a country value to a two-letter country code when possible."""
    if value in [None, ""]:
        return None

    text = str(value).strip()
    if text == "":
        return None

    for candidate in [text, text.upper()]:
        mapped = units.Country.map(candidate)
        if getattr(mapped, "enum", None) is not None:
            return mapped.name

    return None


def _resolve_sku(item) -> typing.Optional[str]:
    """Resolve the item SKU sent to Click & Drop."""
    return _text(
        _coalesce(
            _item_value(item, "SKU", "sku"),
            _item_value(item, "product_id", "productId"),
            _item_value(item, "variant_id", "variantId"),
            _item_value(item, "id"),
        ),
        max=100,
    )


def _resolve_item_name(item) -> typing.Optional[str]:
    """Resolve the item name sent to Click & Drop."""
    return _text(
        _coalesce(
            _item_value(item, "name"),
            _item_value(item, "title"),
            _item_value(item, "description"),
        ),
        max=800,
    )


def _resolve_customs_description(item) -> typing.Optional[str]:
    """Resolve the customs description for an item."""
    return _text(
        _coalesce(
            _item_value(item, "customs_description", "customsDescription"),
            _item_value(item, "description"),
            _item_value(item, "name"),
            _item_value(item, "title"),
        ),
        max=50,
    )

def _resolve_extended_customs_description(item) -> typing.Optional[str]:
    """Resolve the extended customs description for an item."""
    return _text(
        _coalesce(
            _item_value(
                item,
                "extended_customs_description",
                "extendedCustomsDescription",
            ),
            _item_value(item, "description"),
            _item_value(item, "name"),
            _item_value(item, "title"),
            _item_value(item, "customs_description", "customsDescription"),
        ),
        max=300,
    )


def _resolve_customs_code(item) -> typing.Optional[str]:
    """Resolve the HS/customs code for an item."""
    return _text(
        _coalesce(
            _item_value(item, "customs_code", "customsCode"),
            _item_value(item, "hs_code", "hsCode"),
            _item_value(item, "commodity_code", "commodityCode"),
            _item_value(item, "harmonized_code", "harmonizedCode"),
        ),
        max=10,
    )


def _resolve_origin_country_code(item) -> typing.Optional[str]:
    """Resolve the country of origin for an item."""
    return _normalize_country_code(
        _coalesce(
            _item_value(item, "origin_country_code", "originCountryCode"),
            _item_value(item, "origin_country", "originCountry"),
            _item_value(item, "country_of_origin", "countryOfOrigin"),
        ),
        max_length=3,
    )


def _resolve_item_customs_category(item, customs) -> typing.Optional[str]:
    """Resolve the Royal Mail customs category for an item."""
    return provider_units.normalize_customs_category(
        _coalesce(
            _item_value(
                item,
                "customs_declaration_category",
                "customsDeclarationCategory",
            ),
            provider_units.resolve_customs_category(customs),
        )
    )


def _resolve_unit_value(item) -> typing.Optional[float]:
    """Resolve the declared unit value for an item."""
    return _quantize_money(
        _coalesce(
            _item_value(item, "unit_value", "unitValue"),
            _item_value(item, "value_amount", "valueAmount"),
            _item_value(item, "value"),
        ),
        field="unitValue",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )


def _resolve_unit_weight_in_grams(
    item,
    default_weight_unit: typing.Optional[str] = None,
) -> typing.Optional[int]:
    """Resolve an item unit weight in grams."""
    direct_value = _bounded_int(
        _item_value(item, "unitWeightInGrams"),
        field="unitWeightInGrams",
        default=None,
        minimum=0,
        maximum=999999,
    )
    if direct_value is not None:
        return direct_value

    raw_item_weight = _item_value(item, "weight")
    raw_item_weight_unit = _first_present(
        _item_value(item, "weight_unit", "weightUnit"),
        default_weight_unit,
    )
    raw_item_weight_in_grams = (
        provider_units.weight_to_grams(raw_item_weight, raw_item_weight_unit)
        if raw_item_weight is not None and raw_item_weight_unit is not None
        else None
    )

    item_weight = getattr(item, "weight", None) if not isinstance(item, dict) else None
    return _bounded_int(
        _coalesce(
            raw_item_weight_in_grams,
            provider_units.weight_in_grams(item_weight, default=None),
        ),
        field="unitWeightInGrams",
        default=None,
        minimum=0,
        maximum=999999,
    )


def _resolve_requires_export_licence(item) -> typing.Optional[bool]:
    """Resolve whether the item requires an export licence."""
    return _to_bool(
        _item_value(
            item,
            "requires_export_licence",
            "requiresExportLicence",
        ),
        None,
    )


def _resolve_use_origin_preference(item) -> typing.Optional[bool]:
    """Resolve whether origin preference should be declared for the item."""
    return _to_bool(
        _item_value(
            item,
            "use_origin_preference",
            "useOriginPreference",
        ),
        None,
    )


def _resolve_supplementary_units(item) -> typing.Optional[str]:
    """Resolve customs supplementary units for an item."""
    value = _item_value(item, "supplementary_units", "supplementaryUnits")
    if value in [None, ""]:
        return None

    return _text(str(value), max=17)

def _build_item(
    item,
    customs,
    default_weight_unit: typing.Optional[str] = None,
) -> royalmail_req.ContentType:
    """Build a Click & Drop customs item from a Karrio commodity."""
    return royalmail_req.ContentType(
        SKU=_resolve_sku(item),
        name=_resolve_item_name(item),
        quantity=_bounded_int(
            _coalesce(_item_value(item, "quantity"), 1),
            field="quantity",
            default=1,
            minimum=1,
            maximum=999999,
        ),
        unitValue=_resolve_unit_value(item),
        unitWeightInGrams=_resolve_unit_weight_in_grams(
            item,
            default_weight_unit=default_weight_unit,
        ),
        customsDescription=_resolve_customs_description(item),
        extendedCustomsDescription=_resolve_extended_customs_description(item),
        customsCode=_resolve_customs_code(item),
        originCountryCode=_resolve_origin_country_code(item),
        customsDeclarationCategory=_resolve_item_customs_category(item, customs),
        requiresExportLicence=_resolve_requires_export_licence(item),
        stockLocation=_text(
            _item_value(item, "stock_location", "stockLocation"),
            max=50,
        ),
        useOriginPreference=_resolve_use_origin_preference(item),
        supplementaryUnits=_resolve_supplementary_units(item),
        licenseNumber=_text(
            _item_value(item, "license_number", "licenseNumber"),
            max=41,
        ),
        certificateNumber=_text(
            _item_value(item, "certificate_number", "certificateNumber"),
            max=41,
        ),
    )

def _resolve_special_instructions(options):
    """Resolve package-level special delivery instructions."""
    return _text(
        _first_present(
            options.special_instructions.state,
            options.shipment_note.state,
            options.shipper_instructions.state,
            options.recipient_instructions.state,
        ),
        max=500,
    )


def _explicit_package_items(package, raw_package) -> typing.List[typing.Any]:
    """Return items explicitly attached to a specific parcel."""
    return list(
        provider_utils.get_value(raw_package, "items")
        or getattr(package, "items", None)
        or []
    )

def _shipment_items(
    packages,
    raw_parcels=None,
    customs=None,
) -> typing.List[typing.Any]:
    """Return all shipment-level commodity items."""
    customs_items = list(getattr(customs, "commodities", None) or []) if customs else []
    if any(customs_items):
        return customs_items

    return [
        item
        for index, package in enumerate(packages or [])
        for item in _explicit_package_items(
            package,
            raw_parcels[index] if raw_parcels and index < len(raw_parcels) else None,
        )
    ]

def _resolve_package_items(
    package,
    raw_package,
    customs,
    package_count: int = 1,
) -> typing.List[typing.Any]:
    """Resolve the customs items that belong to a package."""
    package_items = _explicit_package_items(package, raw_package)

    if any(package_items):
        return package_items

    if package_count == 1 and customs:
        return list(getattr(customs, "commodities", None) or [])

    return []

def _package_weight_in_grams(package, raw_package) -> typing.Optional[int]:
    """
    Resolve the package-level weight in grams using the same precedence as the
    outbound Click & Drop package serializer.

    Prefer the raw parcel weight/unit when present because it preserves the
    caller's original unit, e.g. 9 G. Fall back to Karrio's normalized package
    weight object.
    """
    raw_weight = provider_utils.get_value(raw_package, "weight")
    raw_weight_unit = _value(raw_package, "weight_unit", "weightUnit")

    if raw_weight is not None and raw_weight_unit is not None:
        return provider_units.weight_to_grams(
            raw_weight,
            raw_weight_unit,
            default=None,
        )

    return provider_units.weight_in_grams(
        getattr(package, "weight", None),
        default=None,
    )


def _item_quantity(item) -> int:
    """Resolve the declared quantity for a customs item."""
    return _bounded_int(
        _coalesce(_item_value(item, "quantity"), 1),
        field="quantity",
        default=1,
        minimum=1,
        maximum=999999,
    )


def _contents_weight_in_grams(
    items: typing.List[typing.Any],
    default_weight_unit: typing.Optional[str] = None,
) -> typing.Optional[int]:
    """
    Resolve the total known contents weight in grams.

    Royal Mail Click & Drop's content model uses `unitWeightInGrams`, so the
    total contents weight is:

        sum(unitWeightInGrams * quantity)

    If no item weights are present, return None so we do not reject a request
    based on incomplete information.

    If some item weights are missing, compare using the known item weights only.
    That is safe because if the package is already lighter than the known
    contents, it is definitely invalid.
    """
    total = 0
    has_weight = False

    for item in items or []:
        unit_weight = _resolve_unit_weight_in_grams(
            item,
            default_weight_unit=default_weight_unit,
        )

        if unit_weight is None:
            continue

        has_weight = True
        total += unit_weight * _item_quantity(item)

    return total if has_weight else None


def _validate_package_weight_not_less_than_contents(
    packages,
    raw_parcels,
    customs,
    settings: provider_utils.Settings,
):
    """
    Validate that each package weighs at least as much as its declared contents.

    Example invalid payload:

        parcel.weight = 9 G
        parcel.items[0].weight = 13 G

    This should fail before we send the shipment to Click & Drop because the
    package cannot physically weigh less than the contents declared inside it.
    """
    messages = []

    for index, package in enumerate(packages or []):
        raw_package = raw_parcels[index] if index < len(raw_parcels or []) else None

        package_items = _resolve_package_items(
            package,
            raw_package,
            customs,
            package_count=len(packages or []),
        )

        if not any(package_items):
            continue

        package_weight = _package_weight_in_grams(package, raw_package)

        fallback_item_weight_unit = _first_present(
            _value(raw_package, "weight_unit", "weightUnit"),
            getattr(getattr(package, "weight", None), "unit", None),
        )

        contents_weight = _contents_weight_in_grams(
            package_items,
            default_weight_unit=fallback_item_weight_unit,
        )

        if package_weight is None or contents_weight is None:
            continue

        if package_weight < contents_weight:
            messages.append(
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code="package_weight_less_than_contents",
                    message=(
                        "Package weight cannot be less than the total weight "
                        f"of its contents. Parcel {index + 1} weighs "
                        f"{package_weight} g but its contents weigh "
                        f"{contents_weight} g."
                    ),
                    details={
                        "operation": "create_shipment",
                        "field": f"parcels[{index}].weight",
                        "package_index": index,
                        "package_weight_in_grams": package_weight,
                        "contents_weight_in_grams": contents_weight,
                        "minimum_package_weight_in_grams": contents_weight,
                    },
                )
            )

    if any(messages):
        raise errors.ParsedMessagesError(messages)

def _resolve_currency_code(
    payload: models.ShipmentRequest,
    packages,
    raw_parcels,
    customs,
    options,
    settings: provider_utils.Settings,
):
    """Resolve the shipment currency code."""
    payment = getattr(payload, "payment", None)
    duty = getattr(customs, "duty", None) if customs else None

    package_items = _shipment_items(
        packages,
        raw_parcels,
        customs,
    )
    item_currency = next(
        (
            _value(item, "value_currency", "valueCurrency", "currencyCode", "currency")
            for item in package_items
            if _value(item, "value_currency", "valueCurrency", "currencyCode", "currency")
            not in [None, ""]
        ),
        None,
    )

    return _first_present(
        options.currency.state,
        provider_utils.get_value(payment, "currency"),
        provider_utils.get_value(duty, "currency"),
        item_currency,
        settings.default_currency,
    )


def _build_package(
    package,
    raw_package,
    customs,
    explicit_package_format: typing.Optional[str] = None,
    package_count: int = 1,
    selected_service: typing.Optional[str] = None,
) -> royalmail_req.PackageType:
    """Build one Click & Drop package object from a Karrio parcel."""
    raw_weight = provider_utils.get_value(raw_package, "weight")
    raw_weight_unit = _value(raw_package, "weight_unit", "weightUnit")
    package_items = _resolve_package_items(
        package,
        raw_package,
        customs,
        package_count=package_count,
    )

    raw_weight_in_grams = (
        provider_units.weight_to_grams(raw_weight, raw_weight_unit)
        if raw_weight is not None and raw_weight_unit is not None
        else None
    )

    fallback_item_weight_unit = _first_present(
        _value(raw_package, "weight_unit", "weightUnit"),
        getattr(getattr(package, "weight", None), "unit", None),
    )

    resolved_explicit_package_format = _resolve_package_explicit_format(
        raw_package,
        shipment_explicit_package_format=explicit_package_format,
    )

    resolved_package_format = provider_units.resolve_package_format(
        package=package,
        raw_package=raw_package,
        explicit=resolved_explicit_package_format,
    )

    click_and_drop_package_format = (
        provider_units.resolve_click_and_drop_package_format_identifier(
            selected_service,
            resolved_package_format,
        )
    )

    return royalmail_req.PackageType(
        weightInGrams=_bounded_int(
            _coalesce(
                raw_weight_in_grams,
                provider_units.weight_in_grams(package.weight, default=1),
                1,
            ),
            field="weightInGrams",
            default=1,
            minimum=1,
            maximum=30000,
        ),
        packageFormatIdentifier=click_and_drop_package_format,
        dimensions=provider_units.build_dimensions(
            package,
            royalmail_req.DimensionsType,
            raw_package=raw_package,
        ),
        contents=[
            _build_item(
                item,
                customs,
                default_weight_unit=fallback_item_weight_unit,
            )
            for item in package_items
        ],
    )

def _sum_items_value(packages, raw_parcels=None, customs=None) -> typing.Optional[float]:
    """Sum declared item values for a package or shipment."""
    total = Decimal("0.00")
    has_items = False

    for item in _shipment_items(packages, raw_parcels, customs):
        has_items = True
        qty = Decimal(
            str(
                _bounded_int(
                    _item_value(item, "quantity"),
                    field="quantity",
                    default=1,
                    minimum=1,
                    maximum=999999,
                )
            )
        )
        value = _to_decimal(
            _coalesce(
                _item_value(item, "unit_value", "unitValue"),
                _item_value(item, "value_amount", "valueAmount"),
                _item_value(item, "value"),
            ),
            None,
        )

        if value is None:
            return None

        total += qty * value

    if not has_items:
        return None

    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _shipment_response_payload(data: dict) -> dict:
    """
    Return only the keys that belong to the successful Click & Drop shipment
    response schema.

    Royal Mail error responses may contain keys such as `errors`. Passing those
    through `ShipmentResponseType` causes jstruct/attrs "unknown arguments"
    warnings. Sanitising the payload keeps success parsing strict without
    polluting test output for error responses.
    """
    if not isinstance(data, dict):
        return {}

    return {
        key: data.get(key)
        for key in [
            "successCount",
            "errorsCount",
            "createdOrders",
            "failedOrders",
        ]
        if key in data
    }


def _has_created_orders(data: typing.Any) -> bool:
    """Return true only when the response contains at least one created order."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("createdOrders"), list)
        and len(data.get("createdOrders") or []) > 0
    )

def parse_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ShipmentDetails], typing.List[models.Message]]:
    """Parse a Click & Drop shipment response into a Karrio shipment result."""
    response = _response.deserialize()

    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="create_shipment",
    )

    # Error-only responses such as {"errors": [...]} should not be deserialized
    # through the successful ShipmentResponseType schema. Doing so causes noisy
    # "unknown arguments {'errors': ...}" warnings.
    if not _has_created_orders(response):
        if any(messages):
            return None, messages

        return None, [
            _parse_error_message(
                settings,
                code="shipment_parse_error",
                message="Unable to parse Royal Mail Click & Drop shipment response",
                operation="create_shipment",
            )
        ]

    shipment = _extract_details(response, settings)
    messages += _extract_label_messages(response, settings)

    if shipment is None and any(messages):
        return None, messages

    if shipment is None:
        return None, [
            _parse_error_message(
                settings,
                code="shipment_parse_error",
                message="Unable to parse Royal Mail Click & Drop shipment response",
                operation="create_shipment",
            )
        ]

    return shipment, messages

def _extract_details(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.Optional[models.ShipmentDetails]:
    """Extract order, label, and tracking details from a shipment response."""
    response = lib.to_object(
        royalmail_res.ShipmentResponseType,
        _shipment_response_payload(data),
    )
    created_orders = response.createdOrders or []

    if len(created_orders) == 0:
        return None

    order = created_orders[0]
    packages = order.packages or []

    package_tracking_numbers = [
        str(package.trackingNumber).strip()
        for package in packages
        if getattr(package, "trackingNumber", None)
    ]

    tracking_numbers = [
        str(value).strip()
        for value in dict.fromkeys(
            [
                order.trackingNumber,
                *package_tracking_numbers,
            ]
        )
        if value is not None and str(value).strip() != ""
    ]

    tracking_number = provider_utils.resolve_tracking_number(tracking_numbers)

    # Preserve Royal Mail's raw numeric orderIdentifier in meta.
    order_identifier = (
        order.orderIdentifier
        if order.orderIdentifier is not None
        and str(order.orderIdentifier).strip() != ""
        else None
    )

    # Use the string form only where Karrio expects a shipment identifier.
    shipment_identifier = (
        str(order_identifier).strip()
        if order_identifier is not None
        else None
    )

    order_reference = (
        str(order.orderReference).strip()
        if order.orderReference is not None
        and str(order.orderReference).strip() != ""
        else None
    )

    tracking_options = {}

    if (
        any(tracking_numbers)
        and tracking_number != provider_utils.NO_TRACKING_NUMBER
        and order_reference is not None
    ):
        tracking_options.update(
            {
                "order_references": {
                    number: order_reference for number in tracking_numbers
                },
                "order_reference": order_reference,
            }
        )

    tracking_lookup = (
        {
            key: value
            for key, value in {
                "tracking_number": tracking_number,
                "tracking_numbers": tracking_numbers,
                "order_reference": order_reference,
            }.items()
            if value not in [None, "", [], {}]
        }
        if (
            any(tracking_numbers)
            and tracking_number != provider_utils.NO_TRACKING_NUMBER
        )
        else None
    )

    return models.ShipmentDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        tracking_number=tracking_number,
        shipment_identifier=str(shipment_identifier or order_reference or ""),
        label_type=settings.label_type,
        docs=(
            models.Documents(
                label=order.label,
                pdf_label=order.label,
            )
            if order.label
            else None
        ),
        meta=dict(
            order_identifier=order_identifier,
            order_reference=order_reference,
            created_on=order.createdOn,
            order_date=order.orderDate,
            printed_on=order.printedOn,
            manifested_on=order.manifestedOn,
            shipped_on=order.shippedOn,
            tracking_numbers=tracking_numbers,
            package_tracking_numbers=package_tracking_numbers,
            generated_documents=order.generatedDocuments or [],
            tracking_number_provided=(
                tracking_number != provider_utils.NO_TRACKING_NUMBER
            ),
            tracking_options=tracking_options,
            tracking_lookup=tracking_lookup,
        ),
    )

def _extract_label_messages(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.List[models.Message]:
    """Extract label-generation messages from a Click & Drop response."""
    if not _has_created_orders(data):
        return []

    response = lib.to_object(
        royalmail_res.ShipmentResponseType,
        _shipment_response_payload(data),
    )
    messages: typing.List[models.Message] = []

    for order in response.createdOrders or []:
        for item in order.labelErrors or []:
            code = provider_utils.get_value(item, "code") or "label_error"
            message = (
                provider_utils.get_value(item, "message")
                or provider_utils.get_value(item, "description")
                or ""
            )

            if not any([code, message]):
                continue

            messages.append(
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code=code,
                    message=message,
                    details={
                        key: value
                        for key, value in dict(
                            operation="create_shipment",
                            order_identifier=order.orderIdentifier,
                            order_reference=order.orderReference,
                        ).items()
                        if value is not None
                    },
                )
            )

    return messages

def shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    """Build and validate the Click & Drop order creation request."""
    shipper = lib.to_address(payload.shipper)
    recipient = lib.to_address(payload.recipient)
    packages = lib.to_packages(payload.parcels, required=["weight"])
    raw_options = provider_units.normalize_carrier_specific_options(
        payload.options or {},
        configured_option_names=(
            settings.connection_config.shipping_options.state or []
        ),
        carrier_names=[
            settings.carrier_id,
            settings.carrier_name,
            settings.shipping_carrier_name,
        ],
    )

    options = lib.to_shipping_options(
        raw_options,
        initializer=provider_units.shipping_options_initializer,
    )
    raw_parcels = list(payload.parcels or [])

    _validate_allowed_shipping_options(raw_options, settings)

    _validate_package_level_options(raw_parcels)
    customs = (
        lib.to_customs_info(
            payload.customs,
            shipper=payload.shipper,
            recipient=payload.recipient,
            weight_unit="KG",
        )
        if payload.customs
        else None
    )
    customs_options = getattr(customs, "options", None) if customs is not None else None

    _validate_package_weight_not_less_than_contents(
        packages,
        raw_parcels,
        customs,
        settings,
    )

    selected_service = _resolve_selected_service(payload, options)

    if not settings.is_shipping_service_allowed(selected_service):
        raise ValueError(
            "Royal Mail Click & Drop service is not allowed by "
            "`config.shipping_services`."
        )

    requested_insurance_coverage = _requested_insurance_coverage_amount(
        raw_options
    )

    _validate_selected_service_compensation(
        selected_service,
        requested_insurance_coverage,
    )

    explicit_package_format = options.package_format_identifier.state

    package_formats = [
        provider_units.resolve_package_format(
            package=package,
            raw_package=raw_parcels[index] if index < len(raw_parcels) else None,
            explicit=_resolve_package_explicit_format(
                raw_parcels[index] if index < len(raw_parcels) else None,
                shipment_explicit_package_format=explicit_package_format,
            ),
        )
        for index, package in enumerate(packages)
    ]

    _validate_multi_package_rules(package_formats, len(packages))

    _validate_selected_service_package_formats(
        selected_service,
        package_formats,
    )

    package_kinds = {
        _package_format_kind(package_format)
        for package_format in package_formats
        if package_format not in [None, ""]
    }
    shipment_package_kind = next(iter(package_kinds), None)

    service_code = provider_units.resolve_carrier_service(selected_service)

    if service_code is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {selected_service}"
        )

    duty_paid_requested = provider_units.is_duty_paid_requested(
        customs=customs,
        options=raw_options,
    )

    _validate_selected_service_ddp_compatibility(
        selected_service,
        duty_paid_requested,
    )

    derived_service_register_code = provider_units.resolve_service_register_code(
        selected_service,
        package_format=shipment_package_kind,
    )

    explicit_service_register_code = options.service_register_code.state

    if (
        explicit_service_register_code is not None
        and derived_service_register_code is not None
        and explicit_service_register_code != derived_service_register_code
    ):
        raise ValueError(
            "Royal Mail Click & Drop `service_register_code` does not match the "
            "selected service and shipment package type."
        )

    service_register_code = (
        explicit_service_register_code
        or derived_service_register_code
    )
    order_reference = _text(
        _first_present(
            options.order_reference.state,
            payload.reference,
            getattr(payload, "order_id", None),
        ),
        max=40,
    )

    order_date = (
        provider_utils.to_datetime_string(options.order_date.state)
        or datetime.datetime.now(datetime.UTC).isoformat()
    )
    planned_despatch_date = provider_utils.to_datetime_string(
        _first_present(
            options.planned_despatch_date.state,
            provider_utils.get_option(options, "shipment_date"),
            provider_utils.get_option(options, "shipping_date"),
        )
    )

    subtotal = _coalesce(
        options.subtotal.state,
        _sum_items_value(packages, raw_parcels, customs),
    )
    shipping_cost = _coalesce(
        options.shipping_cost_charged.state,
        options.shipping_charges.state,
        0.0,
    )
    other_costs = options.other_costs.state
    order_tax = _coalesce(options.order_tax.state, 0.0)
    customs_duty = _coalesce(
        options.customs_duty_costs.state,
        provider_units.customs_duty_amount(
            customs=customs,
            options=raw_options,
        ),
    )

    customs_duty_to_serialize = (
        customs_duty
        if duty_paid_requested
        else None
    )

    serialized_subtotal = _quantize_money(
        subtotal,
        field="subtotal",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_shipping_cost = _quantize_money(
        shipping_cost,
        field="shippingCostCharged",
        default=0.0,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_other_costs = (
        _quantize_money(
            other_costs,
            field="otherCosts",
            default=None,
            minimum=Decimal("0.00"),
            maximum=Decimal("999999.00"),
        )
        if other_costs is not None
        else None
    )
    serialized_order_tax = _quantize_money(
        order_tax,
        field="orderTax",
        default=0.0,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_customs_duty = (
        _quantize_money(
            customs_duty_to_serialize,
            field="customsDutyCosts",
            default=None,
            minimum=Decimal("0.00"),
            maximum=Decimal("99999.99"),
        )
        if customs_duty_to_serialize is not None
        else None
    )

    total = _coalesce(
        options.total.state,
        (
            float(serialized_subtotal or 0.0)
            + float(serialized_shipping_cost or 0.0)
            + float(serialized_order_tax or 0.0)
            + float(serialized_other_costs or 0.0)
            + float(serialized_customs_duty or 0.0)
        )
        if serialized_subtotal is not None
        else None,
    )
    serialized_total = _quantize_money(
        total,
        field="total",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )

    if serialized_subtotal is None:
        raise ValueError(
            "Royal Mail Click & Drop requires `subtotal`. "
            "Provide `options.subtotal` or parcel/customs item values."
        )

    if serialized_total is None:
        raise ValueError(
            "Royal Mail Click & Drop requires `total`. "
            "Provide `options.total` or enough order values to derive it."
        )

    currency = _resolve_currency_code(
        payload,
        packages,
        raw_parcels,
        customs,
        options,
        settings,
    )

    billing = _resolve_billing(payload, raw_options)
    importer = provider_utils.get_value(raw_options, "importer")
    tags = provider_utils.get_value(raw_options, "tags")

## just incase royal mail start setting parcelforce with its own carrier name
#    service_carrier_name = provider_units.resolve_click_and_drop_carrier_name(
#        selected_service,
#        default=settings.shipping_carrier_name,
#    )

    carrier_name = _first_present(
        options.carrier_name.state,
        settings.shipping_carrier_name,
    )
    commercial_invoice_number = _first_present(
        options.commercial_invoice_number.state,
        options.invoice_number.state,
        getattr(customs, "invoice", None),
    )
    commercial_invoice_date = provider_utils.to_datetime_string(
        _first_present(
            options.commercial_invoice_date.state,
            options.invoice_date.state,
            getattr(customs, "invoice_date", None),
        )
    )
    special_instructions = _resolve_special_instructions(options)

    is_recipient_a_business = None
    if (
        _is_gb_to_northern_ireland(shipper, recipient)
        and recipient.residential is not None
    ):
        is_recipient_a_business = not recipient.residential

    is_international = (
        (shipper.country_code or "").upper()
        != (recipient.country_code or "").upper()
    )
    include_label_in_response = _coalesce(
        _to_bool(options.include_label_in_response.state),
        _to_bool(settings.connection_config.include_label_in_response.state),
        True,
    )
    include_cn = (
        True
        if is_international
        else (True if _to_bool(options.include_cn.state) is True else None)
    )
    include_returns_label = _to_bool(options.include_returns_label.state)
    if include_returns_label is None:
        include_returns_label = (
            True
            if _to_bool(
                settings.connection_config.include_return_label_in_response.state,
                False,
            )
            is True
            else None
        )

    # Royal Mail Click & Drop does not expose a generic `insurance` field.
    # Karrio's UI sends the generic coverage value as:
    #
    #   options.insurance = 2100
    #
    # For Royal Mail, map that to postageDetails.consequentialLoss, unless the
    # caller explicitly provided consequential_loss/consequentialLoss.
    consequential_loss_value = _first_present(
        options.consequential_loss.state,
        requested_insurance_coverage,
    )

    consequential_loss = _bounded_int(
        consequential_loss_value,
        field="consequentialLoss",
        default=None,
        minimum=0,
        maximum=10000,
    )
    send_notifications_to, receive_email_notification, receive_sms_notification = (
        _resolve_notification_settings(
            raw_options,
            options,
            selected_service,
            recipient,
            shipper,
            billing,
        )
    )

    request_signature_upon_delivery = _to_bool(
        options.request_signature_upon_delivery.state
    )

    # Royal Mail ID verification includes a signature check before the item is
    # handed over. Click & Drop v1 exposes requestSignatureUponDelivery, but not
    # a separate ID-verification field in the supplied OpenAPI spec.
    if request_signature_upon_delivery is None:
        request_signature_upon_delivery = (
            True
            if _to_bool(options.royalmail_id_verification.state) is True
            else None
        )

    is_local_collect = _to_bool(options.is_local_collect.state)
    requires_export_license = _to_bool(options.requires_export_license.state)
    contains_dangerous_goods = _coalesce(
        _to_bool(options.contains_dangerous_goods.state),
        _to_bool(options.dangerous_good.state),
    )

    request = royalmail_req.ShipmentRequestType(
        items=[
            royalmail_req.ItemType(
                orderReference=order_reference,
                isRecipientABusiness=is_recipient_a_business,
                recipient=royalmail_req.BillingType(
                    address=royalmail_req.AddressType(
                        fullName=_text(
                            recipient.person_name or recipient.company_name,
                            max=210,
                        ),
                        companyName=_text(recipient.company_name, max=100),
                        addressLine1=_text(recipient.address_line1, max=100),
                        addressLine2=_text(recipient.address_line2, max=100),
                        addressLine3=_text(recipient.address_line3, max=100),
                        city=_text(recipient.city, max=100),
                        county=_text(recipient.state_code or recipient.state_name, max=100),
                        postcode=_text(recipient.postal_code, max=20),
                        countryCode=_text(recipient.country_code, max=3),
                    ),
                    phoneNumber=_text(recipient.phone_number, max=25),
                    emailAddress=_text(recipient.email, max=254),
                    addressBookReference=_text(options.address_book_reference.state, max=100),
                ),
                sender=royalmail_req.SenderType(
                    tradingName=_text(shipper.company_name or shipper.person_name, max=250),
                    phoneNumber=_text(shipper.phone_number, max=25),
                    emailAddress=_text(shipper.email, max=254),
                ),
                billing=_build_billing_type(billing),
                packages=[
                    _build_package(
                        package,
                        raw_parcels[index] if index < len(raw_parcels) else None,
                        customs,
                        explicit_package_format,
                        package_count=len(packages),
                        selected_service=selected_service,
                    )
                    for index, package in enumerate(packages)
                ],
                orderDate=order_date,
                plannedDespatchDate=planned_despatch_date,
                specialInstructions=special_instructions,
                subtotal=serialized_subtotal,
                shippingCostCharged=serialized_shipping_cost,
                otherCosts=serialized_other_costs,
                customsDutyCosts=serialized_customs_duty,
                total=serialized_total,
                currencyCode=currency,
                postageDetails=royalmail_req.PostageDetailsType(
                    sendNotificationsTo=send_notifications_to,
                    serviceCode=_text(service_code, max=10),
                    carrierName=_text(carrier_name, max=50),
                    serviceRegisterCode=_text(service_register_code, max=2),
                    consequentialLoss=consequential_loss,
                    receiveEmailNotification=receive_email_notification,
                    receiveSmsNotification=receive_sms_notification,
                    requestSignatureUponDelivery=request_signature_upon_delivery,
                    isLocalCollect=is_local_collect,
                    safePlace=_text(options.safe_place.state, max=90),
                    department=_text(options.department.state, max=150),
                    AIRNumber=(
                        _text(
                            _first_present(
                                options.air_number.state,
                                _option_state(customs_options, "nip_number"),
                            ),
                            max=50,
                        )
                        if _is_gb_to_northern_ireland(shipper, recipient)
                        else None
                    ),
                    IOSSNumber=_text(
                        _first_present(
                            options.ioss_number.state,
                            _option_state(customs_options, "ioss"),
                        ),
                        max=50,
                    ),
                    requiresExportLicense=requires_export_license,
                    commercialInvoiceNumber=_text(commercial_invoice_number, max=35),
                    commercialInvoiceDate=commercial_invoice_date,
                    recipientEoriNumber=_text(
                        _first_present(
                            options.recipient_eori_number.state,
                            _option_state(customs_options, "eori_number"),
                        )
                    ),
                ),
                tags=(
                    [
                        royalmail_req.TagType(
                            key=_text(provider_utils.get_value(tag, "key"), max=100),
                            value=_text(provider_utils.get_value(tag, "value"), max=100),
                        )
                        for tag in tags
                    ]
                    if tags is not None
                    else None
                ),
                label=royalmail_req.LabelType(
                    includeLabelInResponse=include_label_in_response,
                    includeCN=include_cn,
                    includeReturnsLabel=include_returns_label,
                ),
                orderTax=serialized_order_tax,
                containsDangerousGoods=contains_dangerous_goods,
                dangerousGoodsUnCode=_text(
                    options.dangerous_goods_un_code.state,
                    max=4,
                ),
                dangerousGoodsDescription=_text(
                    options.dangerous_goods_description.state,
                    max=500,
                ),
                dangerousGoodsQuantity=options.dangerous_goods_quantity.state,
                importer=(
                    _build_importer_type(importer, options, customs)
                    if is_international and _has_importer_data(importer, options, customs)
                    else None
                ),
            )
        ]
    )

    request_data = provider_utils.clean_payload(lib.to_dict(request)) or {}

    return lib.Serializable(request_data, lambda data: data)