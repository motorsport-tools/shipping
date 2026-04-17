"""Royal Mail Click and Drop carrier tests fixtures."""
import copy
import karrio.sdk as karrio


gateway = karrio.gateway["royalmail_clickdrop"].create(
    dict(
        id="123456789",
        test_mode=False,
        carrier_id="royalmail_clickdrop",
        api_key="TEST_API_KEY",
        account_number="123456789",
        config={},
    )
)

ShipmentPayload = {
    "shipper": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
        "phone_number": "07111111111",
        "email": "warehouse@example.com",
    },
    "recipient": {
        "address_line1": "1 High Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
        "phone_number": "07123456789",
        "email": "john@example.com",
    },
    "parcels": [
        {
            "weight": 500,
            "width": 18,
            "height": 5,
            "length": 25,
            "weight_unit": "G",
            "dimension_unit": "CM",
            "packaging_type": "small_box",
            "items": [
                {
                    "sku": "SKU-1",
                    "description": "Blue T-Shirt",
                    "quantity": 2,
                    "value_amount": 12.5,
                    "weight": 150,
                    "hs_code": "610910",
                    "origin_country": "GB",
                    "metadata": {
                        "customs_declaration_category": "saleOfGoods",
                        "requires_export_licence": False,
                        "stock_location": "A1",
                        "use_origin_preference": True,
                        "supplementary_units": 1,
                        "license_number": "",
                        "certificate_number": "",
                    },
                }
            ],
        }
    ],
    "service": "tracked_24",
    "reference": "ORDER-1001",
    "options": {
        "package_format_identifier": "small_parcel",
        "shipping_cost_charged": 3.5,
        "order_tax": 0.0,
        "subtotal": 25.0,
        "total": 28.5,
        "order_reference": "ORDER-1001",
        "address_book_reference": "ADDR-001",
        "carrier_name": "Royal Mail OBA",
        "send_notifications_to": "recipient",
        "receive_email_notification": True,
        "receive_sms_notification": False,
        "request_signature_upon_delivery": True,
        "is_local_collect": False,
        "safe_place": "Porch",
        "department": "Dispatch",
        "commercial_invoice_number": "INV-1001",
        "commercial_invoice_date": "2024-01-01T10:00:00Z",
        "tags": [{"key": "channel", "value": "web"}],
        "billing": {
            "addressLine1": "2 Billing Street",
            "city": "London",
            "postcode": "EC1A1AA",
            "countryCode": "GB",
            "fullName": "Billing Contact",
            "companyName": "Example Ltd",
            "phoneNumber": "07111111111",
            "emailAddress": "billing@example.com",
        },
        "importer": {
            "companyName": "Importer Ltd",
            "addressLine1": "3 Import Road",
            "city": "Belfast",
            "postcode": "BT11AA",
            "country": "United Kingdom",
            "businessName": "Importer Ltd",
            "contactName": "Importer Contact",
            "phoneNumber": "07000000000",
            "emailAddress": "importer@example.com",
            "vatNumber": "",
            "taxCode": "",
            "eoriNumber": "",
        },
    },
}

ShipmentPayloadWithCN = copy.deepcopy(ShipmentPayload)
ShipmentPayloadWithCN["reference"] = "ORDER-1001-CN"
ShipmentPayloadWithCN["options"]["order_reference"] = "ORDER-1001-CN"
ShipmentPayloadWithCN["options"]["include_cn"] = True

ShipmentPayloadWithReturnsLabel = copy.deepcopy(ShipmentPayload)
ShipmentPayloadWithReturnsLabel["reference"] = "ORDER-1001-RET"
ShipmentPayloadWithReturnsLabel["options"]["order_reference"] = "ORDER-1001-RET"
ShipmentPayloadWithReturnsLabel["options"]["include_returns_label"] = True

ShipmentPayloadWithoutBilling = copy.deepcopy(ShipmentPayload)
ShipmentPayloadWithoutBilling["options"].pop("billing", None)

ShipmentPayloadWithoutImporter = copy.deepcopy(ShipmentPayload)
ShipmentPayloadWithoutImporter["options"].pop("importer", None)

ShipmentPayloadWithoutTags = copy.deepcopy(ShipmentPayload)
ShipmentPayloadWithoutTags["options"].pop("tags", None)

ShipmentPayloadWithoutOptionalSections = copy.deepcopy(ShipmentPayload)
for key in [
    "billing",
    "importer",
    "tags",
    "address_book_reference",
    "special_instructions",
    "commercial_invoice_number",
    "commercial_invoice_date",
]:
    ShipmentPayloadWithoutOptionalSections["options"].pop(key, None)

ShipmentPayloadNoExplicitTotals = copy.deepcopy(ShipmentPayload)
ShipmentPayloadNoExplicitTotals["reference"] = "ORDER-1001-NO-TOTALS"
ShipmentPayloadNoExplicitTotals["options"]["order_reference"] = "ORDER-1001-NO-TOTALS"
ShipmentPayloadNoExplicitTotals["options"].pop("subtotal", None)
ShipmentPayloadNoExplicitTotals["options"].pop("total", None)
ShipmentPayloadNoExplicitTotals["options"]["shipping_cost_charged"] = 3.5
ShipmentPayloadNoExplicitTotals["options"]["order_tax"] = 1.2

ShipmentPayloadMultiParcel = copy.deepcopy(ShipmentPayload)
ShipmentPayloadMultiParcel["reference"] = "ORDER-1001-MULTI"
ShipmentPayloadMultiParcel["options"]["order_reference"] = "ORDER-1001-MULTI"
ShipmentPayloadMultiParcel["parcels"].append(
    {
        "weight": 900,
        "width": 20,
        "height": 10,
        "length": 30,
        "weight_unit": "G",
        "dimension_unit": "CM",
        "packaging_type": "medium_box",
        "items": [
            {
                "sku": "SKU-2",
                "description": "Brake Disc",
                "quantity": 1,
                "value_amount": 45.0,
                "weight": 500,
                "hs_code": "870830",
                "origin_country": "GB",
            }
        ],
    }
)

ShipmentPayloadMultiItem = copy.deepcopy(ShipmentPayload)
ShipmentPayloadMultiItem["reference"] = "ORDER-1001-MULTI-ITEM"
ShipmentPayloadMultiItem["options"]["order_reference"] = "ORDER-1001-MULTI-ITEM"
ShipmentPayloadMultiItem["parcels"][0]["items"].append(
    {
        "sku": "SKU-2",
        "description": "Sticker Pack",
        "quantity": 1,
        "value_amount": 2.5,
        "weight": 10,
        "hs_code": "491199",
        "origin_country": "GB",
    }
)

ShipmentPayloadInvalidService = copy.deepcopy(ShipmentPayload)
ShipmentPayloadInvalidService["service"] = "not_a_service"
ShipmentPayloadInvalidService["options"].pop("service_code", None)

ShipmentPayloadEnvelopePackaging = copy.deepcopy(ShipmentPayload)
ShipmentPayloadEnvelopePackaging["options"].pop("package_format_identifier", None)
ShipmentPayloadEnvelopePackaging["parcels"][0]["packaging_type"] = "envelope"

ShipmentPayloadInferredLetter = copy.deepcopy(ShipmentPayload)
ShipmentPayloadInferredLetter["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredLetter["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredLetter["parcels"][0]["weight"] = 80
ShipmentPayloadInferredLetter["parcels"][0]["length"] = 20
ShipmentPayloadInferredLetter["parcels"][0]["width"] = 15
ShipmentPayloadInferredLetter["parcels"][0]["height"] = 0.4
ShipmentPayloadInferredLetter["parcels"][0]["items"] = [
    {
        "sku": "SKU-LTR-1",
        "description": "Letter insert",
        "quantity": 1,
        "value_amount": 2.5,
        "weight": 20,
        "hs_code": "491199",
        "origin_country": "GB",
    }
]

ShipmentPayloadInferredLargeLetter = copy.deepcopy(ShipmentPayload)
ShipmentPayloadInferredLargeLetter["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredLargeLetter["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredLargeLetter["parcels"][0]["weight"] = 400
ShipmentPayloadInferredLargeLetter["parcels"][0]["length"] = 30
ShipmentPayloadInferredLargeLetter["parcels"][0]["width"] = 20
ShipmentPayloadInferredLargeLetter["parcels"][0]["height"] = 2

ShipmentPayloadInferredParcel = copy.deepcopy(ShipmentPayload)
ShipmentPayloadInferredParcel["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredParcel["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredParcel["parcels"][0]["weight"] = 1500
ShipmentPayloadInferredParcel["parcels"][0]["length"] = 40
ShipmentPayloadInferredParcel["parcels"][0]["width"] = 30
ShipmentPayloadInferredParcel["parcels"][0]["height"] = 10


ShipmentResponse = """{
  "successCount": 1,
  "errorsCount": 0,
  "createdOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "createdOn": "2024-01-01T10:00:00Z",
      "orderDate": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": null,
      "shippedOn": null,
      "trackingNumber": "RM123456789GB",
      "packages": [
        {
          "packageNumber": 1,
          "trackingNumber": "RM123456789GB"
        }
      ],
      "label": "JVBERi0xLjQKJcfs...",
      "labelErrors": [],
      "generatedDocuments": ["label"]
    }
  ],
  "failedOrders": []
}"""

ShipmentResponseWithoutTopLevelTracking = """{
  "successCount": 1,
  "errorsCount": 0,
  "createdOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "createdOn": "2024-01-01T10:00:00Z",
      "orderDate": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": null,
      "shippedOn": null,
      "trackingNumber": null,
      "packages": [
        {
          "packageNumber": 1,
          "trackingNumber": "RM999999999GB"
        }
      ],
      "label": "JVBERi0xLjQKJcfs...",
      "labelErrors": [],
      "generatedDocuments": ["label"]
    }
  ],
  "failedOrders": []
}"""

ShipmentResponseWithMultiplePackages = """{
  "successCount": 1,
  "errorsCount": 0,
  "createdOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "createdOn": "2024-01-01T10:00:00Z",
      "orderDate": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": null,
      "shippedOn": null,
      "trackingNumber": null,
      "packages": [
        {
          "packageNumber": 1,
          "trackingNumber": "RM111111111GB"
        },
        {
          "packageNumber": 2,
          "trackingNumber": "RM222222222GB"
        }
      ],
      "label": "JVBERi0xLjQKJcfs...",
      "labelErrors": [],
      "generatedDocuments": ["label"]
    }
  ],
  "failedOrders": []
}"""

ShipmentResponseWithoutLabel = """{
  "successCount": 1,
  "errorsCount": 0,
  "createdOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "createdOn": "2024-01-01T10:00:00Z",
      "orderDate": "2024-01-01T10:00:00Z",
      "printedOn": "2024-01-01T10:01:00Z",
      "manifestedOn": null,
      "shippedOn": null,
      "trackingNumber": "RM123456789GB",
      "packages": [
        {
          "packageNumber": 1,
          "trackingNumber": "RM123456789GB"
        }
      ],
      "label": null,
      "labelErrors": [],
      "generatedDocuments": []
    }
  ],
  "failedOrders": []
}"""

ShipmentResponseEmptyCreatedOrders = """{
  "successCount": 0,
  "errorsCount": 0,
  "createdOrders": [],
  "failedOrders": []
}"""

ShipmentErrorResponse = """{
  "code": "BadRequest",
  "message": "The request is invalid",
  "details": "One or more validation errors occurred"
}"""

ShipmentArrayErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "BadRequest",
    "message": "Invalid shipment request"
  }
]"""

ShipmentNestedErrorsResponse = """{
  "errors": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "code": "BadRequest",
      "description": "Validation failed"
    },
    {
      "orderIdentifier": 12345679,
      "orderReference": "ORDER-1002",
      "code": "Forbidden",
      "description": "Service not available"
    }
  ]
}"""


ShipmentCancelPayload = {
    "shipment_identifier": "12345678"
}

ShipmentCancelReferencePayload = {
    "shipment_identifier": "ORDER-1001"
}

ShipmentCancelResponse = """{
  "deletedOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "orderInfo": "Deleted successfully"
    }
  ],
  "errors": []
}"""

ShipmentCancelErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  }
]"""

ShipmentCancelMultiErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  },
  {
    "accountOrderNumber": 988,
    "channelOrderReference": "WEB-124",
    "code": "Forbidden",
    "message": "Order already manifested"
  }
]"""


ManifestPayload = {
    "shipment_identifiers": ["12345678", "12345679"],
    "address": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
        "phone_number": "07111111111",
        "email": "warehouse@example.com",
    },
    "options": {
        "carrier_name": "Royal Mail OBA"
    },
}

ManifestPayloadSingleOrder = copy.deepcopy(ManifestPayload)
ManifestPayloadSingleOrder["shipment_identifiers"] = ["12345678"]

ManifestResponse = """{
  "manifestNumber": 1001,
  "documentPdf": "JVBERi0xLjQKJcfs..."
}"""

ManifestResponseWithoutPdf = """{
  "manifestNumber": 1002,
  "documentPdf": null
}"""

ManifestErrorResponse = """{
  "errors": [
    {
      "code": "Forbidden",
      "description": "Feature not available"
    }
  ]
}"""

ManifestNestedErrorResponse = """{
  "errors": [
    {
      "code": "Forbidden",
      "description": "Feature not available"
    },
    {
      "code": "BadRequest",
      "description": "No eligible orders found"
    }
  ]
}"""


LabelPayload = {
    "order_identifiers": [12345678],
    "document_type": "postageLabel",
    "include_cn": True,
}

LabelPayloadWithoutOptionalFlags = {
    "order_identifiers": [12345678],
    "document_type": "postageLabel",
}

LabelPayloadWithReturnsLabel = {
    "order_identifiers": [12345678],
    "document_type": "postageLabel",
    "include_returns_label": True,
}

LabelResponse = b"%PDF-1.4 test label pdf"

LabelErrorResponseBytes = b'[{"code":"NotFound","message":"Order not found"}]'

LabelErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  }
]"""

LabelNestedErrorResponse = """{
  "errors": [
    {
      "accountOrderNumber": 987,
      "channelOrderReference": "WEB-123",
      "code": "NotFound",
      "description": "Order not found"
    }
  ]
}"""


OrderStatusPayload = {
    "items": [
        {
            "order_identifier": 12345678,
            "status": "despatched"
        }
    ]
}

OrderStatusResetPayload = {
    "items": [
        {
            "order_identifier": 12345678,
            "status": "new"
        }
    ]
}

OrderStatusOtherCourierPayload = {
    "items": [
        {
            "order_identifier": 12345678,
            "status": "despatchedByOtherCourier",
            "tracking_number": "OTHER123456",
            "despatch_date": "2024-01-01T12:00:00Z",
            "shipping_carrier": "Other Carrier",
            "shipping_service": "Express"
        }
    ]
}

OrderStatusResponse = """{
  "updatedOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "status": "despatched"
    }
  ],
  "errors": []
}"""

OrderStatusPartialSuccessResponse = """{
  "updatedOrders": [
    {
      "orderIdentifier": 12345678,
      "orderReference": "ORDER-1001",
      "status": "despatched"
    }
  ],
  "errors": [
    {
      "orderIdentifier": 12345679,
      "orderReference": "ORDER-1002",
      "code": "BadRequest",
      "message": "Invalid status update request"
    }
  ]
}"""

OrderStatusErrorResponse = """[
  {
    "orderIdentifier": 12345678,
    "orderReference": "ORDER-1001",
    "status": "despatched",
    "code": "BadRequest",
    "message": "Invalid status update request"
  }
]"""


ReturnShipmentPayload = {
    "shipper": {
        "address_line1": "1 High Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
        "phone_number": "07123456789",
        "email": "john@example.com",
    },
    "recipient": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "state_code": "",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
        "phone_number": "07111111111",
        "email": "warehouse@example.com",
    },
    "parcels": [
        {
            "weight": 0.5,
            "weight_unit": "KG",
            "length": 10,
            "width": 10,
            "height": 2,
            "dimension_unit": "CM",
        }
    ],
    "service": "tracked_returns_48",
    "reference": "ORDER-1001",
}

ReturnShipmentPayloadInvalidService = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadInvalidService["service"] = "tracked_24"

ReturnShipmentPayloadSingleName = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadSingleName["shipper"]["person_name"] = "John"
ReturnShipmentPayloadSingleName["recipient"]["person_name"] = "Warehouse"

ReturnShipmentPayloadUSCountry = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadUSCountry["shipper"]["country_code"] = "US"
ReturnShipmentPayloadUSCountry["recipient"]["country_code"] = "US"

ReturnShipmentPayloadESCountry = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadESCountry["shipper"]["country_code"] = "ES"
ReturnShipmentPayloadESCountry["recipient"]["country_code"] = "ES"

ReturnShipmentRequest = {
    "service": {
        "serviceCode": "TSS"
    },
    "shipment": {
        "customerReference": {
            "reference": "ORDER-1001"
        },
        "returnAddress": {
            "addressLine1": "123 Test Street",
            "city": "London",
            "companyName": "Test Warehouse",
            "country": "United Kingdom",
            "countryIsoCode": "GBR",
            "firstName": "Warehouse",
            "lastName": "User",
            "postcode": "SW1A1AA",
        },
        "shippingAddress": {
            "addressLine1": "1 High Street",
            "city": "London",
            "companyName": "Example Ltd",
            "country": "United Kingdom",
            "countryIsoCode": "GBR",
            "firstName": "John",
            "lastName": "Smith",
            "postcode": "SW1A1AA",
        }
    }
}

ReturnShipmentResponse = """{
  "shipment": {
    "trackingNumber": "RM123456789GB",
    "uniqueItemId": "0A12345678901234"
  },
  "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
  "label": "JVBERi0xLjQKJcfs..."
}"""

ReturnShipmentResponseWithoutLabel = """{
  "shipment": {
    "trackingNumber": "RM123456789GB",
    "uniqueItemId": "0A12345678901234"
  },
  "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
  "label": null
}"""

ReturnShipmentResponseWithoutShipment = """{
  "shipment": null,
  "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
  "label": "JVBERi0xLjQKJcfs..."
}"""

ReturnShipmentErrorResponse = """{
  "code": "BadRequest",
  "message": "Invalid return request",
  "details": "Service code TSS is not available for this account"
}"""

ReturnShipmentArrayErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "BadRequest",
    "message": "Invalid return request"
  }
]"""


ExpectedCoreServices = ["tpn24_01", "fe0_01"]
ExpectedReturnServices = ["TSS"]
ExpectedDefaultConnectionConfig = {
    "base_url": "https://api.parcel.royalmail.com/api/v1",
    "label_type": "PDF",
}