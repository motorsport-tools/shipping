import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class LabelErrorResponseElementType:
    accountOrderNumber: typing.Optional[int] = None
    channelOrderReference: typing.Optional[str] = None
    code: typing.Optional[str] = None
    message: typing.Optional[str] = None
