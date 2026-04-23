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
class MailPieceType:
    mailPieceId: typing.Optional[str] = None
    status: typing.Optional[int] = None


@attr.s(auto_attribs=True)
class TrackingSummaryErrorResponseType:
    mailPieces: typing.Optional[typing.List[MailPieceType]] = jstruct.JList[MailPieceType]
    httpCode: typing.Optional[int] = None
    httpMessage: typing.Optional[str] = None
    moreinformation: typing.Optional[str] = None
    errors: typing.Optional[typing.List[ErrorType]] = jstruct.JList[ErrorType]
