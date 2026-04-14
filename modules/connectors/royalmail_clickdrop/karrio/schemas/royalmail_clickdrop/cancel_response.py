import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class DeletedOrderType:
    orderIdentifier: typing.Optional[int] = None
    orderReference: typing.Optional[str] = None
    orderInfo: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class CancelResponseType:
    deletedOrders: typing.Optional[typing.List[DeletedOrderType]] = jstruct.JList[DeletedOrderType]
    errors: typing.Optional[typing.List[typing.Any]] = None
