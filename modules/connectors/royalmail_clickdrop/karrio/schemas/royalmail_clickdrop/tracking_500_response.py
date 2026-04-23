import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ErrorType:
    errorCode: typing.Optional[str] = None
    errorDescription: typing.Optional[str] = None
    errorCause: typing.Optional[str] = None
    errorResolution: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class Tracking500_ResponseType:
    httpCode: typing.Optional[int] = None
    httpMessage: typing.Optional[str] = None
    errors: typing.Optional[typing.List[ErrorType]] = jstruct.JList[ErrorType]
