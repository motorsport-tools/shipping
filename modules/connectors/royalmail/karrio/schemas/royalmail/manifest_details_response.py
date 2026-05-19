import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ManifestDetailsResponseType:
    manifestNumber: typing.Optional[int] = None
    status: typing.Optional[str] = None
    documentPdf: typing.Optional[str] = None
