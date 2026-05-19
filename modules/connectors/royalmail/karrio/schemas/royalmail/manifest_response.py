import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ManifestResponseType:
    manifestNumber: typing.Optional[int] = None
    documentPdf: typing.Optional[str] = None
