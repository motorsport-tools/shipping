"""Compatibility alias for legacy `royalmail` mapper lookups."""

from karrio.mappers.royalmail_clickdrop.mapper import Mapper
from karrio.mappers.royalmail_clickdrop.proxy import Proxy
from karrio.mappers.royalmail_clickdrop.settings import Settings
import karrio.providers.royalmail_clickdrop.units as units

__all__ = ["Mapper", "Proxy", "Settings", "units"]
