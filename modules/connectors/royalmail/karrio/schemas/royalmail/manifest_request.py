import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ManifestRequestType:
    carrierName: typing.Optional[str] = None
