import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class TrackingSignatureRequestType:
    mailPieceId: typing.Optional[str] = None
