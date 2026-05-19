import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class EventsType:
    href: typing.Optional[str] = None
    title: typing.Optional[str] = None
    description: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class LinksType:
    events: typing.Optional[EventsType] = jstruct.JStruct[EventsType]
    summary: typing.Optional[EventsType] = jstruct.JStruct[EventsType]


@attr.s(auto_attribs=True)
class SignatureType:
    uniqueItemId: typing.Optional[str] = None
    oneDBarcode: typing.Optional[str] = None
    recipientName: typing.Optional[str] = None
    signatureDateTime: typing.Optional[str] = None
    imageFormat: typing.Optional[str] = None
    imageId: typing.Optional[str] = None
    height: typing.Optional[int] = None
    width: typing.Optional[int] = None
    image: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class MailPiecesType:
    mailPieceId: typing.Optional[str] = None
    carrierShortName: typing.Optional[str] = None
    carrierFullName: typing.Optional[str] = None
    signature: typing.Optional[SignatureType] = jstruct.JStruct[SignatureType]
    links: typing.Optional[LinksType] = jstruct.JStruct[LinksType]


@attr.s(auto_attribs=True)
class TrackingSignatureResponseType:
    mailPieces: typing.Optional[MailPiecesType] = jstruct.JStruct[MailPiecesType]
