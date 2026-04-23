import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class Tracking429_ResponseType:
    httpCode: typing.Optional[int] = None
    httpMessage: typing.Optional[str] = None
    moreInformation: typing.Optional[str] = None
