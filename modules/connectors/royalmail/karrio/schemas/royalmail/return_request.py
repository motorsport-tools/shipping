import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ServiceType:
    serviceCode: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class CustomerReferenceType:
    reference: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class AddressType:
    title: typing.Optional[str] = None
    firstName: typing.Optional[str] = None
    lastName: typing.Optional[str] = None
    companyName: typing.Optional[str] = None
    addressLine1: typing.Optional[str] = None
    addressLine2: typing.Optional[str] = None
    addressLine3: typing.Optional[str] = None
    city: typing.Optional[str] = None
    county: typing.Optional[str] = None
    postcode: typing.Optional[str] = None
    country: typing.Optional[str] = None
    countryIsoCode: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ShipmentType:
    shippingAddress: typing.Optional[AddressType] = jstruct.JStruct[AddressType]
    returnAddress: typing.Optional[AddressType] = jstruct.JStruct[AddressType]
    customerReference: typing.Optional[CustomerReferenceType] = jstruct.JStruct[CustomerReferenceType]


@attr.s(auto_attribs=True)
class ReturnRequestType:
    service: typing.Optional[ServiceType] = jstruct.JStruct[ServiceType]
    shipment: typing.Optional[ShipmentType] = jstruct.JStruct[ShipmentType]
