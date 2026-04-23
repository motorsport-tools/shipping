import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class EstimatedDeliveryType:
    date: typing.Optional[str] = None
    startOfEstimatedWindow: typing.Optional[str] = None
    endOfEstimatedWindow: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class EventType:
    eventCode: typing.Optional[str] = None
    eventName: typing.Optional[str] = None
    eventDateTime: typing.Optional[str] = None
    locationName: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class RedeliveryType:
    href: typing.Optional[str] = None
    title: typing.Optional[str] = None
    description: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class LinksType:
    summary: typing.Optional[RedeliveryType] = jstruct.JStruct[RedeliveryType]
    signature: typing.Optional[RedeliveryType] = jstruct.JStruct[RedeliveryType]
    redelivery: typing.Optional[RedeliveryType] = jstruct.JStruct[RedeliveryType]


@attr.s(auto_attribs=True)
class SignatureType:
    recipientName: typing.Optional[str] = None
    signatureDateTime: typing.Optional[str] = None
    imageId: typing.Optional[str] = None


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
class MailPiecesType:
    mailPieceId: typing.Optional[str] = None
    carrierShortName: typing.Optional[str] = None
    carrierFullName: typing.Optional[str] = None
    summary: typing.Optional[SummaryType] = jstruct.JStruct[SummaryType]
    signature: typing.Optional[SignatureType] = jstruct.JStruct[SignatureType]
    estimatedDelivery: typing.Optional[EstimatedDeliveryType] = jstruct.JStruct[EstimatedDeliveryType]
    events: typing.Optional[typing.List[EventType]] = jstruct.JList[EventType]
    links: typing.Optional[LinksType] = jstruct.JStruct[LinksType]


@attr.s(auto_attribs=True)
class TrackingEventsResponseType:
    mailPieces: typing.Optional[MailPiecesType] = jstruct.JStruct[MailPiecesType]
