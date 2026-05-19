from karrio.core.metadata import PluginMetadata

from karrio.mappers.royalmail.mapper import Mapper
from karrio.mappers.royalmail.proxy import Proxy
from karrio.mappers.royalmail.settings import Settings
import karrio.providers.royalmail.units as units

def _register_server_hooks():
    """Import and register optional server hooks for the Royal Mail extension."""
    try:
        from django.conf import settings as django_settings

        if not getattr(django_settings, "configured", False):
            return

        from karrio.plugins.royalmail.server import register

        register()
    except Exception:
        return


_register_server_hooks()


METADATA = PluginMetadata(
    status="development",
    id="royalmail",
    label="Royal Mail Click and Drop",
    description="Royal Mail Click and Drop shipping integration for Karrio",
    Mapper=Mapper,
    Proxy=Proxy,
    Settings=Settings,
    is_hub=False,
    options=units.ShippingOption,
    package_presets=units.PackagePresets,
    packaging_types=units.PackagingType,
    services=units.ShippingService,
    service_levels=units.REFERENCE_SERVICE_LEVELS,
    connection_configs=units.ConnectionConfig,
    website="https://www.royalmail.com",
    documentation="https://api.parcel.royalmail.com/",
)