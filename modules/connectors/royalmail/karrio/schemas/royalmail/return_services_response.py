import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ServiceType:
    carrierGuid: typing.Optional[str] = None
    carrierServiceGuid: typing.Optional[str] = None
    serviceName: typing.Optional[str] = None
    serviceCode: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ReturnServicesResponseType:
    services: typing.Optional[typing.List[ServiceType]] = jstruct.JList[ServiceType]
