import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ShipmentType:
    trackingNumber: typing.Optional[str] = None
    uniqueItemId: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ReturnResponseType:
    shipment: typing.Optional[ShipmentType] = jstruct.JStruct[ShipmentType]
    qrCode: typing.Optional[str] = None
    label: typing.Optional[str] = None
