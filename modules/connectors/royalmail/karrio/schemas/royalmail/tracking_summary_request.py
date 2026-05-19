import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class TrackingSummaryRequestType:
    mailPieceId: typing.Optional[str] = None
