import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class IngInfoType:
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
    countryCode: typing.Optional[str] = None
    phoneNumber: typing.Optional[str] = None
    emailAddress: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class OrderLineType:
    SKU: typing.Optional[str] = None
    name: typing.Optional[str] = None
    quantity: typing.Optional[int] = None
    unitValue: typing.Optional[float] = None
    lineTotal: typing.Optional[float] = None
    customsCode: typing.Optional[int] = None


@attr.s(auto_attribs=True)
class PackageType:
    packageNumber: typing.Optional[int] = None
    trackingNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ShippingDetailsType:
    shippingCost: typing.Optional[float] = None
    trackingNumber: typing.Optional[str] = None
    shippingTrackingStatus: typing.Optional[str] = None
    serviceCode: typing.Optional[str] = None
    shippingService: typing.Optional[str] = None
    shippingCarrier: typing.Optional[str] = None
    receiveEmailNotification: typing.Optional[bool] = None
    receiveSmsNotification: typing.Optional[bool] = None
    guaranteedSaturdayDelivery: typing.Optional[bool] = None
    requestSignatureUponDelivery: typing.Optional[bool] = None
    isLocalCollect: typing.Optional[bool] = None
    shippingUpdateSuccessDate: typing.Optional[str] = None
    packages: typing.Optional[typing.List[PackageType]] = jstruct.JList[PackageType]


@attr.s(auto_attribs=True)
class TagType:
    key: typing.Optional[str] = None
    value: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class OrderDetailsResponseElementType:
    orderIdentifier: typing.Optional[int] = None
    orderStatus: typing.Optional[str] = None
    createdOn: typing.Optional[str] = None
    printedOn: typing.Optional[str] = None
    shippedOn: typing.Optional[str] = None
    postageAppliedOn: typing.Optional[str] = None
    manifestedOn: typing.Optional[str] = None
    orderDate: typing.Optional[str] = None
    despatchedByOtherCourierOn: typing.Optional[str] = None
    tradingName: typing.Optional[str] = None
    channel: typing.Optional[str] = None
    marketplaceTypeName: typing.Optional[str] = None
    department: typing.Optional[str] = None
    AIRNumber: typing.Optional[str] = None
    requiresExportLicense: typing.Optional[bool] = None
    commercialInvoiceNumber: typing.Optional[str] = None
    commercialInvoiceDate: typing.Optional[str] = None
    orderReference: typing.Optional[str] = None
    channelShippingMethod: typing.Optional[str] = None
    specialInstructions: typing.Optional[str] = None
    pickerSpecialInstructions: typing.Optional[str] = None
    subtotal: typing.Optional[float] = None
    shippingCostCharged: typing.Optional[float] = None
    orderDiscount: typing.Optional[float] = None
    total: typing.Optional[float] = None
    weightInGrams: typing.Optional[int] = None
    packageSize: typing.Optional[str] = None
    accountBatchNumber: typing.Optional[str] = None
    currencyCode: typing.Optional[str] = None
    shippingDetails: typing.Optional[ShippingDetailsType] = jstruct.JStruct[ShippingDetailsType]
    shippingInfo: typing.Optional[IngInfoType] = jstruct.JStruct[IngInfoType]
    billingInfo: typing.Optional[IngInfoType] = jstruct.JStruct[IngInfoType]
    orderLines: typing.Optional[typing.List[OrderLineType]] = jstruct.JList[OrderLineType]
    tags: typing.Optional[typing.List[TagType]] = jstruct.JList[TagType]
