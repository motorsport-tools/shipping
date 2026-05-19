import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class PackageType:
    packageNumber: typing.Optional[int] = None
    trackingNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class OrderType:
    orderIdentifier: typing.Optional[int] = None
    orderReference: typing.Optional[str] = None
    createdOn: typing.Optional[str] = None
    orderDate: typing.Optional[str] = None
    printedOn: typing.Optional[str] = None
    manifestedOn: typing.Any = None
    shippedOn: typing.Any = None
    trackingNumber: typing.Optional[str] = None
    packages: typing.Optional[typing.List[PackageType]] = jstruct.JList[PackageType]


@attr.s(auto_attribs=True)
class OrdersResponseType:
    orders: typing.Optional[typing.List[OrderType]] = jstruct.JList[OrderType]
    continuationToken: typing.Optional[str] = None
