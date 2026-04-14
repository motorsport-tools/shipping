"""Royal Mail Click and Drop carrier tests fixtures."""

import karrio.sdk as karrio


gateway = karrio.gateway["royalmail_clickdrop"].create(
    dict(
        id="123456789",
        test_mode=False,
        carrier_id="royalmail_clickdrop",
        api_key="TEST_API_KEY",
        #for future use import and export
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
        "include_label_in_response": True,
        "include_cn": False,
        "include_returns_label": False,
        "subtotal": 25.0,
        "shipping_cost_charged": 3.5,
        "order_tax": 0.0,
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

ShipmentErrorResponse = """{
  "code": "BadRequest",
  "message": "The request is invalid",
  "details": "One or more validation errors occurred"
}"""


ShipmentCancelPayload = {
    "shipment_identifier": "12345678"
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

ManifestResponse = """{
  "manifestNumber": 1001,
  "documentPdf": "JVBERi0xLjQKJcfs..."
}"""

ManifestErrorResponse = """{
  "errors": [
    {
      "code": "Forbidden",
      "description": "Feature not available"
    }
  ]
}"""

LabelPayload = {
    "order_identifiers": [12345678],
    "document_type": "postageLabel",
    "include_returns_label": False,
    "include_cn": True,
}

LabelResponse = b"%PDF-1.4 test label pdf"

LabelErrorResponse = """[
  {
    "accountOrderNumber": 987,
    "channelOrderReference": "WEB-123",
    "code": "NotFound",
    "message": "Order not found"
  }
]"""


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

OrderStatusErrorResponse = """[
  {
    "orderIdentifier": 12345678,
    "orderReference": "ORDER-1001",
    "status": "despatched",
    "code": "BadRequest",
    "message": "Invalid status update request"
  }
]"""
