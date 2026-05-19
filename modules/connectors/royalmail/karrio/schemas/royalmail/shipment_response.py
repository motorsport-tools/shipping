import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class PackageType:
    packageNumber: typing.Optional[int] = None
    trackingNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class CreatedOrderType:
    orderIdentifier: typing.Optional[int] = None
    orderReference: typing.Optional[str] = None
    createdOn: typing.Optional[str] = None
    orderDate: typing.Optional[str] = None
    printedOn: typing.Optional[str] = None
    manifestedOn: typing.Any = None
    shippedOn: typing.Any = None
    trackingNumber: typing.Optional[str] = None
    packages: typing.Optional[typing.List[PackageType]] = jstruct.JList[PackageType]
    label: typing.Optional[str] = None
    labelErrors: typing.Optional[typing.List[typing.Any]] = None
    generatedDocuments: typing.Optional[typing.List[str]] = None


@attr.s(auto_attribs=True)
class ShipmentResponseType:
    successCount: typing.Optional[int] = None
    errorsCount: typing.Optional[int] = None
    createdOrders: typing.Optional[typing.List[CreatedOrderType]] = jstruct.JList[CreatedOrderType]
    failedOrders: typing.Optional[typing.List[typing.Any]] = None
