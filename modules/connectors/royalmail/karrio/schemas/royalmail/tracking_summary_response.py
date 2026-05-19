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
class EventsType:
    href: typing.Optional[str] = None
    title: typing.Optional[str] = None
    description: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class LinksType:
    events: typing.Optional[EventsType] = jstruct.JStruct[EventsType]


@attr.s(auto_attribs=True)
class InternationalPostalProviderType:
    url: typing.Optional[str] = None
    title: typing.Optional[str] = None
    description: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class SummaryType:
    uniqueItemId: typing.Optional[str] = None
    oneDBarcode: typing.Optional[str] = None
    productId: typing.Optional[str] = None
    productName: typing.Optional[str] = None
    productDescription: typing.Optional[str] = None
    productCategory: typing.Optional[str] = None
    destinationCountryCode: typing.Optional[str] = None
    destinationCountryName: typing.Optional[str] = None
    originCountryCode: typing.Optional[str] = None
    originCountryName: typing.Optional[str] = None
    lastEventCode: typing.Optional[str] = None
    lastEventName: typing.Optional[str] = None
    lastEventDateTime: typing.Optional[str] = None
    lastEventLocationName: typing.Optional[str] = None
    statusDescription: typing.Optional[str] = None
    statusCategory: typing.Optional[str] = None
    statusHelpText: typing.Optional[str] = None
    summaryLine: typing.Optional[str] = None
    internationalPostalProvider: typing.Optional[InternationalPostalProviderType] = jstruct.JStruct[InternationalPostalProviderType]


@attr.s(auto_attribs=True)
class MailPieceType:
    mailPieceId: typing.Optional[str] = None
    status: typing.Optional[int] = None
    carrierShortName: typing.Optional[str] = None
    carrierFullName: typing.Optional[str] = None
    summary: typing.Optional[SummaryType] = jstruct.JStruct[SummaryType]
    links: typing.Optional[LinksType] = jstruct.JStruct[LinksType]
    error: typing.Optional[ErrorType] = jstruct.JStruct[ErrorType]


@attr.s(auto_attribs=True)
class TrackingSummaryResponseType:
    mailPieces: typing.Optional[typing.List[MailPieceType]] = jstruct.JList[MailPieceType]
