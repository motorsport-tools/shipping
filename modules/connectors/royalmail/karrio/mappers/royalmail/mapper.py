"""Karrio Royal Mail Click and Drop client mapper."""

import typing
import attr
from decimal import Decimal, ROUND_HALF_UP

import karrio.api.mapper as mapper
import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.royalmail.settings as provider_settings
import karrio.providers.royalmail as provider
import karrio.providers.royalmail.manifest as manifest_provider
import karrio.providers.royalmail.orders.query as order_query
import karrio.universal.providers.rating as universal_provider
import karrio.providers.royalmail.units as provider_units

_MONEY_QUANT = Decimal("0.01")


def _money_decimal(value: typing.Any) -> Decimal:
    """Return a GBP-style money Decimal rounded half-up to 2 decimals."""
    if value in [None, ""]:
        value = "0"

    return Decimal(str(value)).quantize(
        _MONEY_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _float_or_none(value: typing.Any) -> typing.Optional[float]:
    """Convert metadata/config value to float when available."""
    if value in [None, ""]:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(
    value: typing.Any,
    default: typing.Optional[bool] = None,
) -> typing.Optional[bool]:
    """Convert metadata/config value to bool when available."""
    if value in [None, ""]:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in ["1", "true", "yes", "y", "on"]:
        return True

    if text in ["0", "false", "no", "n", "off"]:
        return False

    return default


def _metadata_value(
    metadata: dict,
    *keys: str,
) -> typing.Any:
    """Return the first non-empty metadata value for the supplied keys."""
    for key in keys:
        value = metadata.get(key)

        if value not in [None, ""]:
            return value

    return None


def _connection_config_value(
    settings: provider_settings.Settings,
    *keys: str,
) -> typing.Any:
    """
    Read Royal Mail connection config values from either:

    1. settings.connection_config.<option>.state
    2. settings.config dict

    This keeps the helper safe across Karrio CE config loading paths.
    """
    connection_config = getattr(settings, "connection_config", None)

    for key in keys:
        option = getattr(connection_config, key, None) if connection_config else None
        value = getattr(option, "state", None)

        if value not in [None, ""]:
            return value

    config = getattr(settings, "config", {}) or {}

    if isinstance(config, dict):
        for key in keys:
            value = config.get(key)

            if value not in [None, ""]:
                return value

    return None


def _service_level_for_rate(
    rate: models.RateDetails,
    settings: provider_settings.Settings,
) -> typing.Optional[models.ServiceLevel]:
    """Find the ServiceLevel definition used to produce a RateDetails object."""
    services = list(getattr(settings, "services", None) or provider_units.DEFAULT_SERVICES)

    return next(
        (
            service
            for service in services
            if getattr(service, "service_code", None) == rate.service
        ),
        None,
    )


def _rate_has_uk_vat_charge(rate: models.RateDetails) -> bool:
    """Prevent double VAT if the rate is processed more than once."""
    for charge in rate.extra_charges or []:
        charge_id = getattr(charge, "id", None)
        charge_name = str(getattr(charge, "name", "") or "").strip().lower()

        if charge_id == provider_units.ROYALMAIL_UK_VAT_CHARGE_ID:
            return True

        if charge_name.startswith("uk vat") or charge_name.startswith("vat "):
            return True

    return False


def _format_percentage(value: float) -> str:
    """Format 20.0 as '20' and 17.5 as '17.5'."""
    return f"{float(value):g}"


def _vat_rate_percentage_for_rate(
    rate: models.RateDetails,
    settings: provider_settings.Settings,
) -> typing.Optional[float]:
    """
    Resolve VAT rate for a Royal Mail rate.

    Priority:
    1. Service row explicitly says vat_applicable=False -> no VAT.
    2. Service row vat_rate_percentage -> use that rate.
    3. Service row vat_applicable=True -> use connection/global/default rate.
    4. Optional connection config apply_uk_vat_to_rates=True -> use configured/default rate.
    5. Otherwise no VAT.
    """
    service = _service_level_for_rate(rate, settings)

    if service is None:
        return None

    metadata = getattr(service, "metadata", {}) or {}

    if not isinstance(metadata, dict):
        return None

    prices_include_vat = _bool_or_none(
        _metadata_value(
            metadata,
            "prices_include_vat",
            "vat_included",
            "tax_included",
        ),
        default=False,
    )

    # Your services.csv prices are VAT-free. If a future row is already gross,
    # do not gross it up again.
    if prices_include_vat is True:
        return None

    vat_applicable = _bool_or_none(
        _metadata_value(
            metadata,
            "vat_applicable",
            "taxable",
            "apply_vat",
            "apply_uk_vat",
        ),
        default=None,
    )

    if vat_applicable is False:
        return None

    service_vat_rate = _float_or_none(
        _metadata_value(
            metadata,
            "vat_rate_percentage",
            "uk_vat_rate_percentage",
            "tax_rate_percentage",
        )
    )

    if service_vat_rate is not None:
        return service_vat_rate if service_vat_rate > 0 else None

    configured_vat_rate = _float_or_none(
        _connection_config_value(
            settings,
            "uk_vat_rate_percentage",
            "ukVatRatePercentage",
            "vat_rate_percentage",
            "vatRatePercentage",
        )
    )

    default_vat_rate = (
        configured_vat_rate
        if configured_vat_rate is not None
        else provider_units.ROYALMAIL_DEFAULT_UK_VAT_RATE_PERCENTAGE
    )

    if vat_applicable is True:
        return default_vat_rate if default_vat_rate > 0 else None

    apply_uk_vat_to_rates = _bool_or_none(
        _connection_config_value(
            settings,
            "apply_uk_vat_to_rates",
            "applyUkVatToRates",
        ),
        default=False,
    )

    if apply_uk_vat_to_rates is True:
        return default_vat_rate if default_vat_rate > 0 else None

    return None


def _apply_royalmail_vat_to_rate(
    rate: models.RateDetails,
    settings: provider_settings.Settings,
) -> models.RateDetails:
    """
    Gross-up a Royal Mail VAT-exclusive rate.

    Universal rating has already calculated the Royal Mail net charge:

        net total = base + Royal Mail surcharges + selected feature charges

    VAT must be calculated on that net total, not on the base rate only.
    """
    if _rate_has_uk_vat_charge(rate):
        return rate

    vat_rate_percentage = _vat_rate_percentage_for_rate(rate, settings)

    if vat_rate_percentage in [None, 0]:
        return rate

    net_total = _money_decimal(rate.total_charge)
    vat_amount = _money_decimal(
        net_total * Decimal(str(vat_rate_percentage)) / Decimal("100")
    )

    if vat_amount == Decimal("0.00"):
        return rate

    gross_total = _money_decimal(net_total + vat_amount)
    vat_label = f"UK VAT ({_format_percentage(vat_rate_percentage)}%)"

    vat_charge = models.ChargeDetails(
        id=provider_units.ROYALMAIL_UK_VAT_CHARGE_ID,
        name=vat_label,
        amount=float(vat_amount),
        currency=rate.currency,
        charge_type="tax",
        metadata=dict(
            tax_code="UK_VAT",
            tax_rate_percentage=vat_rate_percentage,
            taxable_amount=float(net_total),
            prices_include_vat=False,
        ),
    )

    return attr.evolve(
        rate,
        total_charge=float(gross_total),
        extra_charges=[
            *(rate.extra_charges or []),
            vat_charge,
        ],
        meta={
            **(rate.meta or {}),
            "vat_applied": True,
            "vat_rate_percentage": vat_rate_percentage,
            "vat_amount": float(vat_amount),
            "vat_taxable_amount": float(net_total),
            "net_charge": float(net_total),
            "gross_charge": float(gross_total),
            "prices_include_vat": False,
        },
    )

class Mapper(mapper.Mapper):
    """Karrio mapper that converts Royal Mail requests and responses to provider handlers."""
    settings: provider_settings.Settings

    def create_rate_request(self, payload: models.RateRequest) -> lib.Serializable:
        """Build a Royal Mail rating request from a Karrio RateRequest payload."""
        request_data = lib.to_dict(payload)

        request_data["options"] = provider_units.normalize_carrier_specific_options(
            request_data.get("options") or {},
            configured_option_names=(
                self.settings.connection_config.shipping_options.state or []
            ),
            carrier_names=[
                self.settings.carrier_id,
                self.settings.carrier_name,
                self.settings.shipping_carrier_name,
            ],
        )

        requested_services = request_data.get("services") or []

        if isinstance(requested_services, str):
            requested_services = [requested_services]

        request_data["services"] = list(
            dict.fromkeys(
                provider_units.resolve_service_code(service) or str(service).strip()
                for service in requested_services
                if service not in [None, ""]
            )
        )

        return universal_provider.rate_request(
            models.RateRequest(**request_data),
            self.settings,
        )

    def create_shipment_request(
        self, payload: models.ShipmentRequest
    ) -> lib.Serializable:
        """Build a Click & Drop order creation request from a Karrio ShipmentRequest."""
        return provider.shipment_request(payload, self.settings)

    def create_return_shipment_request(
        self, payload: models.ShipmentRequest
    ) -> lib.Serializable:
        """Build a Royal Mail return shipment request from a Karrio payload."""
        return provider.return_shipment_request(payload, self.settings)

    def create_cancel_shipment_request(
        self, payload: models.ShipmentCancelRequest
    ) -> lib.Serializable[str]:
        """Build a Click & Drop order cancellation request."""
        return provider.shipment_cancel_request(payload, self.settings)

    def create_manifest_request(
        self, payload: models.ManifestRequest
    ) -> lib.Serializable:
        """Build a Click & Drop manifest creation request."""
        return provider.manifest_request(payload, self.settings)

    def create_label_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop label retrieval request."""
        return provider.label_request(payload, self.settings)

    def create_order_status_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop order status update request."""
        return provider.order_status_request(payload, self.settings)

    def create_get_manifest_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop manifest details lookup request."""
        return manifest_provider.manifest_identifier_request(payload, self.settings)

    def create_retry_manifest_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop manifest retry request."""
        return manifest_provider.manifest_identifier_request(payload, self.settings)

    def create_get_order_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop single-order lookup request."""
        return order_query.order_lookup_request(payload, self.settings)

    def create_list_orders_request(self, payload: typing.Any = None) -> lib.Serializable:
        """Build a Click & Drop order list request."""
        return order_query.orders_lookup_request(payload or {}, self.settings)

    def create_get_order_details_request(self, payload: typing.Any) -> lib.Serializable:
        """Build a Click & Drop order-details lookup request."""
        return order_query.order_lookup_request(payload, self.settings)

    def create_list_order_details_request(
        self, payload: typing.Any = None
    ) -> lib.Serializable:
        """Build a Click & Drop multi-order-details lookup request."""
        return order_query.orders_lookup_request(payload or {}, self.settings)

    def create_get_return_services_request(
        self, payload: typing.Any = None
    ) -> lib.Serializable:
        """Build a Click & Drop return-services lookup request."""
        return order_query.empty_request(payload, self.settings)

    def create_get_version_request(self, payload: typing.Any = None) -> lib.Serializable:
        """Build a Click & Drop API version request."""
        return order_query.empty_request(payload, self.settings)

    def parse_cancel_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ConfirmationDetails, typing.List[models.Message]]:
        """Parse a Click & Drop cancellation response into Karrio models."""
        return provider.parse_shipment_cancel_response(response, self.settings)

    def parse_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        """Parse a Click & Drop order creation response into Karrio shipment data."""
        return provider.parse_shipment_response(response, self.settings)

    def parse_return_shipment_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        """Parse a Royal Mail return shipment response into Karrio shipment data."""
        return provider.parse_return_shipment_response(response, self.settings)

    def parse_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[models.ManifestDetails, typing.List[models.Message]]:
        """Parse a Click & Drop manifest response into a Karrio manifest result."""
        return provider.parse_manifest_response(response, self.settings)

    def parse_label_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[models.Documents], typing.List[models.Message]]:
        """Parse a Click & Drop label response into a Karrio document result."""
        return provider.parse_label_response(response, self.settings)

    def parse_order_status_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ConfirmationDetails],
        typing.List[models.Message],
    ]:
        """Parse a Click & Drop order status response into Karrio metadata."""
        return provider.parse_order_status_response(response, self.settings)

    def parse_get_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ManifestDetails],
        typing.List[models.Message],
    ]:
        """Parse Click & Drop manifest details into Karrio metadata."""
        return manifest_provider.parse_manifest_response(response, self.settings)

    def parse_retry_manifest_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ManifestDetails],
        typing.List[models.Message],
    ]:
        """Parse a Click & Drop manifest retry response."""
        return manifest_provider.parse_manifest_response(response, self.settings)

    def parse_get_order_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse a Click & Drop single-order lookup response."""
        return order_query.parse_get_order_response(response, self.settings)

    def parse_list_orders_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse a Click & Drop order list response."""
        return order_query.parse_list_orders_response(response, self.settings)

    def parse_get_order_details_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse Click & Drop order details into Karrio metadata."""
        return order_query.parse_get_order_details_response(response, self.settings)

    def parse_list_order_details_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse a Click & Drop multi-order-details response."""
        return order_query.parse_list_order_details_response(response, self.settings)

    def parse_get_return_services_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse Click & Drop return-service metadata."""
        return order_query.parse_get_return_services_response(response, self.settings)

    def parse_get_version_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.Optional[typing.Any], typing.List[models.Message]]:
        """Parse Click & Drop API version metadata."""
        return order_query.parse_get_version_response(response, self.settings)

# old method not sure which is better yet
#    def parse_rate_response(
#        self, response: lib.Deserializable[dict]
#    ) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
#        payload = response.deserialize()
#        # Direct unit tests provide an already-normalized response:
#        # {
#        #   "rates": [...],
#        #   "messages": [...]
#        # }
#        #
#        # The universal rating parser expects the internal RatingMixinProxy
#        # multi-piece response format, so we short-circuit normalized payloads.
#        if isinstance(payload, dict) and (
#            "rates" in payload or "messages" in payload
#        ):
#            rates = payload.get("rates", [])
#            messages = payload.get("messages", [])
#
#            return rates, messages
#
#        return universal_provider.parse_rate_response(
#            lib.Deserializable(payload, lambda x: x),
#            self.settings,
#        )
    
    def parse_rate_response(
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
        """
        Parse locally rated Royal Mail services into Karrio rate results.

        Royal Mail service prices in services.csv are VAT-exclusive. Universal
        rating first calculates the net Royal Mail amount. We then add UK VAT
        as a separate Karrio ChargeDetails tax line so Karrio stores and displays
        the gross shipping charge.
        """
        rates, messages = universal_provider.parse_rate_response(
            response,
            self.settings,
        )

        return [
            _apply_royalmail_vat_to_rate(rate, self.settings)
            for rate in rates
        ], messages

    def create_tracking_request(
        self, payload: models.TrackingRequest
    ) -> lib.Serializable:
        """Build a Royal Mail tracking request from a Karrio TrackingRequest."""
        return provider.tracking_request(payload, self.settings)

    def parse_tracking_response(
        self, response: lib.Deserializable[typing.Any]
    ) -> typing.Tuple[typing.List[models.TrackingDetails], typing.List[models.Message]]:
        """Parse Royal Mail Tracking API and Click & Drop fallback responses."""
        return provider.parse_tracking_response(response, self.settings)