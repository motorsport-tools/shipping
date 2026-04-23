import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class TrackingRequestType:
    mailPieceId: typing.Optional[str] = None
