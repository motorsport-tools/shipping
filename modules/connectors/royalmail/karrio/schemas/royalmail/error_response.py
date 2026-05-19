import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ErrorResponseType:
    code: typing.Optional[str] = None
    message: typing.Optional[str] = None
    details: typing.Optional[str] = None
