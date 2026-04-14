import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class AddressType:
    fullName: typing.Optional[str] = None
    companyName: typing.Optional[str] = None
    addressLine1: typing.Optional[str] = None
    addressLine2: typing.Optional[str] = None
    addressLine3: typing.Optional[str] = None
    city: typing.Optional[str] = None
    county: typing.Optional[str] = None
    postcode: typing.Optional[str] = None
    countryCode: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class BillingType:
    address: typing.Optional[AddressType] = jstruct.JStruct[AddressType]
    phoneNumber: typing.Optional[str] = None
    emailAddress: typing.Optional[str] = None
    addressBookReference: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ImporterType:
    companyName: typing.Optional[str] = None
    addressLine1: typing.Optional[str] = None
    addressLine2: typing.Optional[str] = None
    addressLine3: typing.Optional[str] = None
    city: typing.Optional[str] = None
    postcode: typing.Optional[str] = None
    country: typing.Optional[str] = None
    businessName: typing.Optional[str] = None
    contactName: typing.Optional[str] = None
    phoneNumber: typing.Optional[str] = None
    emailAddress: typing.Optional[str] = None
    vatNumber: typing.Optional[str] = None
    taxCode: typing.Optional[str] = None
    eoriNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class LabelType:
    includeLabelInResponse: typing.Optional[bool] = None
    includeCN: typing.Optional[bool] = None
    includeReturnsLabel: typing.Optional[bool] = None


@attr.s(auto_attribs=True)
class ContentType:
    SKU: typing.Optional[str] = None
    name: typing.Optional[str] = None
    quantity: typing.Optional[int] = None
    unitValue: typing.Optional[float] = None
    unitWeightInGrams: typing.Optional[int] = None
    customsDescription: typing.Optional[str] = None
    extendedCustomsDescription: typing.Optional[str] = None
    customsCode: typing.Optional[str] = None
    originCountryCode: typing.Optional[str] = None
    customsDeclarationCategory: typing.Optional[str] = None
    requiresExportLicence: typing.Optional[bool] = None
    stockLocation: typing.Optional[str] = None
    useOriginPreference: typing.Optional[bool] = None
    supplementaryUnits: typing.Optional[str] = None
    licenseNumber: typing.Optional[str] = None
    certificateNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class DimensionsType:
    heightInMms: typing.Optional[int] = None
    widthInMms: typing.Optional[int] = None
    depthInMms: typing.Optional[int] = None


@attr.s(auto_attribs=True)
class PackageType:
    weightInGrams: typing.Optional[int] = None
    packageFormatIdentifier: typing.Optional[str] = None
    dimensions: typing.Optional[DimensionsType] = jstruct.JStruct[DimensionsType]
    contents: typing.Optional[typing.List[ContentType]] = jstruct.JList[ContentType]


@attr.s(auto_attribs=True)
class PostageDetailsType:
    sendNotificationsTo: typing.Optional[str] = None
    serviceCode: typing.Optional[str] = None
    carrierName: typing.Optional[str] = None
    serviceRegisterCode: typing.Optional[str] = None
    consequentialLoss: typing.Optional[int] = None
    receiveEmailNotification: typing.Optional[bool] = None
    receiveSmsNotification: typing.Optional[bool] = None
    requestSignatureUponDelivery: typing.Optional[bool] = None
    isLocalCollect: typing.Optional[bool] = None
    safePlace: typing.Optional[str] = None
    department: typing.Optional[str] = None
    AIRNumber: typing.Optional[str] = None
    IOSSNumber: typing.Optional[str] = None
    requiresExportLicense: typing.Optional[bool] = None
    commercialInvoiceNumber: typing.Optional[str] = None
    commercialInvoiceDate: typing.Optional[str] = None
    recipientEoriNumber: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class SenderType:
    tradingName: typing.Optional[str] = None
    phoneNumber: typing.Optional[str] = None
    emailAddress: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class TagType:
    key: typing.Optional[str] = None
    value: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ItemType:
    orderReference: typing.Optional[str] = None
    isRecipientABusiness: typing.Optional[bool] = None
    recipient: typing.Optional[BillingType] = jstruct.JStruct[BillingType]
    sender: typing.Optional[SenderType] = jstruct.JStruct[SenderType]
    billing: typing.Optional[BillingType] = jstruct.JStruct[BillingType]
    packages: typing.Optional[typing.List[PackageType]] = jstruct.JList[PackageType]
    orderDate: typing.Optional[str] = None
    plannedDespatchDate: typing.Optional[str] = None
    specialInstructions: typing.Optional[str] = None
    subtotal: typing.Optional[float] = None
    shippingCostCharged: typing.Optional[float] = None
    otherCosts: typing.Optional[float] = None
    customsDutyCosts: typing.Optional[float] = None
    total: typing.Optional[float] = None
    currencyCode: typing.Optional[str] = None
    postageDetails: typing.Optional[PostageDetailsType] = jstruct.JStruct[PostageDetailsType]
    tags: typing.Optional[typing.List[TagType]] = jstruct.JList[TagType]
    label: typing.Optional[LabelType] = jstruct.JStruct[LabelType]
    orderTax: typing.Optional[float] = None
    containsDangerousGoods: typing.Optional[bool] = None
    dangerousGoodsUnCode: typing.Optional[str] = None
    dangerousGoodsDescription: typing.Optional[str] = None
    dangerousGoodsQuantity: typing.Optional[float] = None
    importer: typing.Optional[ImporterType] = jstruct.JStruct[ImporterType]


@attr.s(auto_attribs=True)
class ShipmentRequestType:
    items: typing.Optional[typing.List[ItemType]] = jstruct.JList[ItemType]
