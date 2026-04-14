import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class UpdatedOrderType:
    orderIdentifier: typing.Optional[int] = None
    orderReference: typing.Optional[str] = None
    status: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class OrderStatusResponseType:
    updatedOrders: typing.Optional[typing.List[UpdatedOrderType]] = jstruct.JList[UpdatedOrderType]
    errors: typing.Optional[typing.List[typing.Any]] = None
