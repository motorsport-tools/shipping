import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ItemType:
    orderIdentifier: typing.Optional[int] = None
    status: typing.Optional[str] = None
    orderReference: typing.Optional[str] = None
    trackingNumber: typing.Optional[str] = None
    despatchDate: typing.Optional[str] = None
    shippingCarrier: typing.Optional[str] = None
    shippingService: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class OrderStatusRequestType:
    items: typing.Optional[typing.List[ItemType]] = jstruct.JList[ItemType]
