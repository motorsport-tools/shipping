
"""Royal Mail Click and Drop carrier tests fixtures.
all payloads should be contained in this single file for eas of use
"""
from __future__ import annotations

import copy
from unittest.mock import ANY

import karrio.sdk as karrio


gateway = karrio.gateway["royalmail_clickdrop"].create(
    {
        "id": "123456789",
        "carrier_id": "royalmail",
        "api_key": "CLICKDROP_API_KEY",
        "tracking_client_id": "ROYALMAIL_TRACKING_CLIENT_ID",
        "tracking_client_secret": "ROYALMAIL_TRACKING_CLIENT_SECRET",
        "config": {
            "base_url": "https://api.parcel.royalmail.com/api/v1",
            "tracking_base_url": "https://api.royalmail.net",
        },
    }
)

# ---------------------------------------------------------------------------
# Tracking payload catalog
# ---------------------------------------------------------------------------
TrackingPayload = {
    "tracking_numbers": ["090367574000000FE1E1B"],
}

TrackingRequestJSON = ["090367574000000FE1E1B"]

TrackingPayloadMulti = {
    "tracking_numbers": ["090367574000000FE1E1B", "ZZ000000000GB"],
}


TrackingSummaryResponseJSON = """{
  "mailPieces": [
    {
      "mailPieceId": "090367574000000FE1E1B",
      "status": "200",
      "carrierShortName": "RM",
      "carrierFullName": "Royal Mail Group Ltd",
      "summary": {
        "uniqueItemId": "090367574000000FE1E1B",
        "oneDBarcode": "FQ087430672GB",
        "productId": "SD2",
        "productName": "Special Delivery Guaranteed",
        "productDescription": "Our guaranteed next working day service with tracking and a signature on delivery",
        "productCategory": "NON-INTERNATIONAL",
        "destinationCountryCode": "GBR",
        "destinationCountryName": "United Kingdom of Great Britain and Northern Ireland",
        "originCountryCode": "GBR",
        "originCountryName": "United Kingdom of Great Britain and Northern Ireland",
        "lastEventCode": "EVNMI",
        "lastEventName": "Forwarded - Mis-sort",
        "lastEventDateTime": "2016-10-20T10:04:00+0000",
        "lastEventLocationName": "Stafford DO",
        "statusDescription": "It's being redirected",
        "statusCategory": "IN TRANSIT",
        "statusHelpText": "The item is in transit and a confirmation will be provided on delivery.",
        "summaryLine": "Item FQ087430672GB was forwarded to the Delivery Office on 2016-10-20."
      },
      "links": {
        "events": {
          "href": "/mailpieces/v2/090367574000000FE1E1B/events",
          "title": "Events",
          "description": "Get events"
        }
      }
    }
  ]
}"""


TrackingSummaryResponseWithProofOfDeliveryJSON = """{
  "mailPieces": [
    {
      "mailPieceId": "090367574000000FE1E1B",
      "status": "200",
      "carrierShortName": "RM",
      "carrierFullName": "Royal Mail Group Ltd",
      "summary": {
        "uniqueItemId": "090367574000000FE1E1B",
        "oneDBarcode": "FQ087430672GB",
        "productId": "SD2",
        "productName": "Special Delivery Guaranteed",
        "productDescription": "Our guaranteed next working day service with tracking and a signature on delivery",
        "productCategory": "NON-INTERNATIONAL",
        "lastEventCode": "DELIVERED",
        "lastEventName": "Delivered",
        "lastEventDateTime": "2017-03-30T16:15:00+0000",
        "lastEventLocationName": "Stafford DO",
        "statusDescription": "Delivered",
        "statusCategory": "DELIVERED",
        "summaryLine": "Item was delivered."
      },
      "links": {
        "events": {
          "href": "/mailpieces/v2/090367574000000FE1E1B/events",
          "title": "Events",
          "description": "Get events"
        }
      }
    }
  ]
}"""


TrackingSummaryPartialResponseJSON = """{
  "mailPieces": [
    {
      "mailPieceId": "090367574000000FE1E1B",
      "status": "200",
      "carrierShortName": "RM",
      "carrierFullName": "Royal Mail Group Ltd",
      "summary": {
        "uniqueItemId": "090367574000000FE1E1B",
        "oneDBarcode": "FQ087430672GB",
        "productId": "SD2",
        "productName": "Special Delivery Guaranteed",
        "productDescription": "Our guaranteed next working day service with tracking and a signature on delivery",
        "productCategory": "NON-INTERNATIONAL",
        "destinationCountryCode": "GBR",
        "destinationCountryName": "United Kingdom of Great Britain and Northern Ireland",
        "originCountryCode": "GBR",
        "originCountryName": "United Kingdom of Great Britain and Northern Ireland",
        "lastEventCode": "EVNMI",
        "lastEventName": "Forwarded - Mis-sort",
        "lastEventDateTime": "2016-10-20T10:04:00+0000",
        "lastEventLocationName": "Stafford DO",
        "statusDescription": "It's being redirected",
        "statusCategory": "IN TRANSIT",
        "statusHelpText": "The item is in transit and a confirmation will be provided on delivery.",
        "summaryLine": "Item FQ087430672GB was forwarded to the Delivery Office on 2016-10-20."
      },
      "links": {
        "events": {
          "href": "/mailpieces/v2/090367574000000FE1E1B/events",
          "title": "Events",
          "description": "Get events"
        }
      }
    },
    {
      "mailPieceId": "ZZ000000000GB",
      "status": "404",
      "error": {
        "errorCode": "E2001",
        "errorDescription": "Tracking number not found",
        "errorCause": "The barcode reference isn't recognised",
        "errorResolution": "Please check the tracking number and resubmit"
      }
    }
  ]
}"""

TrackingResponseJSON = """{
  "mailPieces": {
    "mailPieceId": "090367574000000FE1E1B",
    "carrierShortName": "RM",
    "carrierFullName": "Royal Mail Group Ltd",
    "summary": {
      "uniqueItemId": "090367574000000FE1E1B",
      "oneDBarcode": "FQ087430672GB",
      "productId": "SD2",
      "productName": "Special Delivery Guaranteed",
      "productDescription": "Our guaranteed next working day service with tracking and a signature on delivery",
      "productCategory": "NON-INTERNATIONAL",
      "destinationCountryCode": "GBR",
      "destinationCountryName": "United Kingdom of Great Britain and Northern Ireland",
      "originCountryCode": "GBR",
      "originCountryName": "United Kingdom of Great Britain and Northern Ireland",
      "lastEventCode": "EVNMI",
      "lastEventName": "Forwarded - Mis-sort",
      "lastEventDateTime": "2016-10-20T10:04:00+0000",
      "lastEventLocationName": "Stafford DO",
      "statusDescription": "It's being redirected",
      "statusCategory": "IN TRANSIT",
      "statusHelpText": "The item is in transit and a confirmation will be provided on delivery.",
      "summaryLine": "Item FQ087430672GB was forwarded to the Delivery Office on 2016-10-20."
    },
    "estimatedDelivery": {
      "date": "2017-02-20",
      "startOfEstimatedWindow": "08:00:00+0000",
      "endOfEstimatedWindow": "11:00:00+0000"
    },
    "events": [
      {
        "eventCode": "EVNMI",
        "eventName": "Forwarded - Mis-sort",
        "eventDateTime": "2016-10-20T10:04:00+0000",
        "locationName": "Stafford DO"
      }
    ]
  }
}"""


TrackingResponseWithoutSummaryJSON = """{
  "mailPieces": {
    "mailPieceId": "090367574000000FE1E1B",
    "carrierShortName": "RM",
    "carrierFullName": "Royal Mail Group Ltd",
    "events": [
      {
        "eventCode": "EVNPS",
        "eventName": "Ready for redelivery or collection",
        "eventDateTime": "2016-10-21T07:30:00+0000",
        "locationName": "Mount Pleasant MC"
      }
    ]
  }
}"""


TrackingErrorResponseJSON = """{
  "httpCode": "400",
  "httpMessage": "Bad Request",
  "errors": [
    {
      "errorCode": "E0004",
      "errorDescription": "Failed header validation for X-Accept-RMG-Terms",
      "errorCause": "The submitted request was not valid against the required header definition",
      "errorResolution": "Please check the API request against the required header definition and re-submit"
    }
  ]
}"""


ParsedTrackingResponse = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "tracking_number": "090367574000000FE1E1B",
            "delivered": False,
            "estimated_delivery": "2017-02-20",
            "events": [
                {
                    "code": "EVNMI",
                    "date": "2016-10-20",
                    "description": "Forwarded - Mis-sort",
                    "location": "Stafford DO",
                    "reason": "carrier_sorting_error",
                    "time": "10:04 AM",
                    "timestamp": "2016-10-20T10:04:00.000Z",
                }
            ],
        }
    ],
    [],
]


ParsedTrackingResponseWithoutSummary = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "tracking_number": "090367574000000FE1E1B",
            "delivered": False,
            "events": [
                {
                    "code": "EVNPS",
                    "date": "2016-10-21",
                    "description": "Ready for redelivery or collection",
                    "location": "Mount Pleasant MC",
                    "reason": "consignee_not_home",
                    "time": "07:30 AM",
                    "timestamp": "2016-10-21T07:30:00.000Z",
                }
            ],
        }
    ],
    [],
]


ParsedTrackingErrorResponse = [
    [],
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "400",
            "message": "Bad Request",
            "details": {
                "tracking_number": "090367574000000FE1E1B",
                "errors": [
                    {
                        "errorCode": "E0004",
                        "errorDescription": "Failed header validation for X-Accept-RMG-Terms",
                        "errorCause": "The submitted request was not valid against the required header definition",
                        "errorResolution": "Please check the API request against the required header definition and re-submit",
                    }
                ],
            },
        }
    ],
]

ParsedTrackingSummaryPartialResponse = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "tracking_number": "090367574000000FE1E1B",
            "delivered": False,
            "events": [
                {
                    "code": "EVNMI",
                    "date": "2016-10-20",
                    "description": "Forwarded - Mis-sort",
                    "location": "Stafford DO",
                    "reason": "carrier_sorting_error",
                    "time": "10:04 AM",
                    "timestamp": "2016-10-20T10:04:00.000Z",
                }
            ],
        }
    ],
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "E2001",
            "message": "Tracking number not found",
            "details": {
                "tracking_number": "ZZ000000000GB",
                "status": "404",
                "cause": "The barcode reference isn't recognised",
                "resolution": "Please check the tracking number and resubmit",
            },
        }
    ],
]

TrackingResponseWithProofOfDeliveryJSON = """{
  "mailPieces": {
    "mailPieceId": "090367574000000FE1E1B",
    "carrierShortName": "RM",
    "carrierFullName": "Royal Mail Group Ltd",
    "summary": {
      "uniqueItemId": "090367574000000FE1E1B",
      "oneDBarcode": "FQ087430672GB",
      "productId": "SD2",
      "productName": "Special Delivery Guaranteed",
      "productDescription": "Our guaranteed next working day service with tracking and a signature on delivery",
      "productCategory": "NON-INTERNATIONAL",
      "lastEventCode": "DELIVERED",
      "lastEventName": "Delivered",
      "lastEventDateTime": "2017-03-30T16:15:00+0000",
      "lastEventLocationName": "Stafford DO",
      "statusDescription": "Delivered",
      "statusCategory": "DELIVERED",
      "summaryLine": "Item was delivered."
    },
    "signature": {
      "recipientName": "Simon",
      "signatureDateTime": "2017-03-30T16:15:00+0000",
      "imageId": "001234"
    },
    "events": [
      {
        "eventCode": "DELIVERED",
        "eventName": "Delivered",
        "eventDateTime": "2017-03-30T16:15:00+0000",
        "locationName": "Stafford DO"
      }
    ],
    "links": {
      "signature": {
        "href": "/mailpieces/v2/090367574000000FE1E1B/signature",
        "title": "Signature",
        "description": "Get signature"
      }
    }
  }
}"""


TrackingSignatureResponseJSON = """{
  "mailPieces": {
    "mailPieceId": "090367574000000FE1E1B",
    "carrierShortName": "RM",
    "carrierFullName": "Royal Mail Group Ltd",
    "signature": {
      "uniqueItemId": "090367574000000FE1E1B",
      "oneDBarcode": "FQ087430672GB",
      "recipientName": "Simon",
      "signatureDateTime": "2017-03-30T16:15:00+0000",
      "imageFormat": "image/svg+xml",
      "imageId": "001234",
      "height": 530,
      "width": 660,
      "image": "<svg height=\\"530\\" width=\\"660\\"></svg>"
    },
    "links": {
      "events": {
        "href": "/mailpieces/v2/090367574000000FE1E1B/events",
        "title": "Events",
        "description": "Get events"
      },
      "summary": {
        "href": "/mailpieces/v2/summary?mailPieceId=090367574000000FE1E1B",
        "title": "Summary",
        "description": "Get summary"
      }
    }
  }
}"""


ParsedTrackingResponseWithProofOfDelivery = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "tracking_number": "090367574000000FE1E1B",
            "delivered": True,
            "events": [
                {
                    "code": "DELIVERED",
                    "date": "2017-03-30",
                    "description": "Delivered",
                    "location": "Stafford DO",
                    "time": "04:15 PM",
                    "timestamp": "2017-03-30T16:15:00.000Z",
                },
                {
                    "code": "POD",
                    "date": "2017-03-30",
                    "description": "Proof of delivery captured for Simon",
                    "status": "delivered",
                    "time": "04:15 PM",
                    "timestamp": "2017-03-30T16:15:00.000Z",
                },
            ],
            "info": {
                "customer_name": "Simon",
            },
            "images": {
                "signature_image": "PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
            },
            "meta": {
                "proof_of_delivery": {
                    "type": "signature",
                    "image_format": "image/svg+xml",
                    "image_id": "001234",
                    "recipient_name": "Simon",
                    "signed_at": "2017-03-30T16:15:00+0000",
                    "base64": "PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
                    "data_uri": "data:image/svg+xml;base64,PHN2ZyBoZWlnaHQ9IjUzMCIgd2lkdGg9IjY2MCI+PC9zdmc+",
                }
            },
        }
    ],
    [],
]
# ---------------------------------------------------------------------------
# Shipment payload catalog
# ---------------------------------------------------------------------------

ShipmentPayloadRichBase = {
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
            "address": {
                "addressLine1": "2 Billing Street",
                "city": "London",
                "postcode": "EC1A1AA",
                "countryCode": "GB",
                "fullName": "Billing Contact",
                "companyName": "Example Ltd",
            },
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

ShipmentPayloadWithoutBilling = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithoutBilling["options"].pop("billing", None)

ShipmentPayloadMissingBillingPostcode = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadMissingBillingPostcode["options"]["billing"]["address"].pop("postcode", None)

ShipmentPayloadWithBilling = copy.deepcopy(ShipmentPayloadRichBase)

ShipmentPayloadWithBillingAddress = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadWithBillingAddress["billing_address"] = {
    "person_name": "Billing Contact",
    "company_name": "Example Ltd",
    "address_line1": "2 Billing Street",
    "city": "London",
    "postal_code": "EC1A1AA",
    "country_code": "GB",
    "phone_number": "07111111111",
    "email": "billing@example.com",
}


ShipmentPayloadWithOrderIdFallback = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadWithOrderIdFallback["reference"] = ""
ShipmentPayloadWithOrderIdFallback["order_id"] = "ORDER-ID-1001"
ShipmentPayloadWithOrderIdFallback["options"].pop("order_reference", None)



ShipmentPayloadWithoutItemValueWeight = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadWithoutItemValueWeight["parcels"][0]["items"] = [
    {
        "sku": "SKU-LOOKUP-1",
        "quantity": 1,
    }
]


ShipmentPayloadInvalidService = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadInvalidService["service"] = "not_a_service"

ShipmentPayloadWithRawServiceCode = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadWithRawServiceCode["service"] = "CRL24"

ShipmentRequestWithRawServiceCode = copy.deepcopy(ShipmentRequest)
ShipmentRequestWithRawServiceCode["items"][0]["postageDetails"]["serviceCode"] = "CRL24"
ShipmentRequestWithRawServiceCode["items"][0]["postageDetails"]["serviceRegisterCode"] = "01"

ShipmentPayloadWithServiceOptionOverride = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadWithServiceOptionOverride["service"] = "tracked_24"
ShipmentPayloadWithServiceOptionOverride["options"]["service_code"] = "CRL24"

ShipmentRequestWithServiceOptionOverride = copy.deepcopy(ShipmentRequest)
ShipmentRequestWithServiceOptionOverride["items"][0]["postageDetails"]["serviceCode"] = "CRL24"
ShipmentRequestWithServiceOptionOverride["items"][0]["postageDetails"]["serviceRegisterCode"] = "01"

ShipmentPayloadInternational = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadInternational["recipient"].update(
    {
        "address_line1": "10 Rue de Rivoli",
        "city": "Paris",
        "postal_code": "75001",
        "country_code": "FR",
        "state_code": "",
        "person_name": "Jean Martin",
        "company_name": "Example FR",
        "phone_number": "0102030405",
        "email": "jean@example.fr",
    }
)
ShipmentPayloadInternational["reference"] = "ORDER-INTL-1001"
ShipmentPayloadInternational["options"].update(
    {
        "order_reference": "ORDER-INTL-1001",
        "include_cn": True,
        "commercial_invoice_number": "INV-INTL-1001",
        "commercial_invoice_date": "2024-01-01T10:00:00Z",
        "ioss_number": "IM2760000000",
        "recipient_eori_number": "FR12345678900013",
        "requires_export_license": False,
    }
)

ShipmentPayloadWithCustomsInvoiceFallback = copy.deepcopy(ShipmentPayloadInternational)
ShipmentPayloadWithCustomsInvoiceFallback["options"].pop("commercial_invoice_number", None)
ShipmentPayloadWithCustomsInvoiceFallback["options"].pop("commercial_invoice_date", None)
ShipmentPayloadWithCustomsInvoiceFallback["customs"] = {
    "content_type": "merchandise",
    "invoice": "INV-CUSTOMS-1001",
    "invoice_date": "2024-01-03T10:00:00Z",
}

ShipmentPayloadWithImporterFallbacks = copy.deepcopy(ShipmentPayloadInternational)
ShipmentPayloadWithImporterFallbacks["options"].pop("importer", None)
ShipmentPayloadWithImporterFallbacks["options"]["importer_vat_number"] = "GB123456789"
ShipmentPayloadWithImporterFallbacks["options"]["importer_tax_code"] = "TAX-GB-1001"
ShipmentPayloadWithImporterFallbacks["options"]["importer_eori_number"] = "GB123456789000"

ShipmentPayloadWithOrderExtras = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithOrderExtras["reference"] = "ORDER-EXTRA-1001"
ShipmentPayloadWithOrderExtras["options"].update(
    {
        "order_reference": "ORDER-EXTRA-1001",
        "planned_despatch_date": "2024-01-02T10:00:00Z",
        "special_instructions": "Leave with dispatch desk",
        "other_costs": 1.25,
    }
)

ShipmentPayloadWithCN = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithCN["reference"] = "ORDER-1001-CN"
ShipmentPayloadWithCN["options"]["order_reference"] = "ORDER-1001-CN"
ShipmentPayloadWithCN["options"]["include_cn"] = True

ShipmentPayloadWithReturnsLabel = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithReturnsLabel["reference"] = "ORDER-1001-RET"
ShipmentPayloadWithReturnsLabel["options"]["order_reference"] = "ORDER-1001-RET"
ShipmentPayloadWithReturnsLabel["options"]["include_returns_label"] = True



ShipmentPayloadWithoutImporter = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithoutImporter["options"].pop("importer", None)

ShipmentPayloadWithoutTags = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithoutTags["options"].pop("tags", None)

ShipmentPayloadWithoutOptionalSections = copy.deepcopy(ShipmentPayloadRichBase)
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

ShipmentPayloadNoExplicitTotals = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadNoExplicitTotals["reference"] = "ORDER-1001-NO-TOTALS"
ShipmentPayloadNoExplicitTotals["options"]["order_reference"] = "ORDER-1001-NO-TOTALS"
ShipmentPayloadNoExplicitTotals["options"].pop("subtotal", None)
ShipmentPayloadNoExplicitTotals["options"].pop("total", None)
ShipmentPayloadNoExplicitTotals["options"]["shipping_cost_charged"] = 3.5
ShipmentPayloadNoExplicitTotals["options"]["order_tax"] = 1.2

ShipmentPayloadMultiParcel = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadMultiParcel["reference"] = "ORDER-1001-MULTI"
ShipmentPayloadMultiParcel["options"]["order_reference"] = "ORDER-1001-MULTI"
ShipmentPayloadMultiParcel["options"].pop("package_format_identifier", None)
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

ShipmentPayloadMultiItem = copy.deepcopy(ShipmentPayloadRichBase)
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



ShipmentPayloadEnvelopePackaging = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadEnvelopePackaging["options"].pop("package_format_identifier", None)
ShipmentPayloadEnvelopePackaging["parcels"][0]["packaging_type"] = "envelope"

ShipmentPayloadInferredLetter = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadInferredLetter["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredLetter["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredLetter["parcels"][0]["weight"] = 80
ShipmentPayloadInferredLetter["parcels"][0]["length"] = 20
ShipmentPayloadInferredLetter["parcels"][0]["width"] = 15
ShipmentPayloadInferredLetter["parcels"][0]["height"] = 0.4

ShipmentPayloadInferredLargeLetter = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadInferredLargeLetter["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredLargeLetter["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredLargeLetter["parcels"][0]["weight"] = 400
ShipmentPayloadInferredLargeLetter["parcels"][0]["length"] = 30
ShipmentPayloadInferredLargeLetter["parcels"][0]["width"] = 20
ShipmentPayloadInferredLargeLetter["parcels"][0]["height"] = 2

ShipmentPayloadInferredParcel = copy.deepcopy(ShipmentPayloadWithoutBilling)
ShipmentPayloadInferredParcel["options"].pop("package_format_identifier", None)
ShipmentPayloadInferredParcel["parcels"][0].pop("packaging_type", None)
ShipmentPayloadInferredParcel["parcels"][0]["weight"] = 1500
ShipmentPayloadInferredParcel["parcels"][0]["length"] = 40
ShipmentPayloadInferredParcel["parcels"][0]["width"] = 30
ShipmentPayloadInferredParcel["parcels"][0]["height"] = 10

# Canonical shipment payload used by request/response equality tests.
ShipmentPayload = {
    "shipper": {
        "address_line1": "123 Test Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
    },
    "recipient": {
        "address_line1": "1 High Street",
        "city": "London",
        "postal_code": "SW1A1AA",
        "country_code": "GB",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
    },
    "parcels": [
        {
            "weight": 500,
            "weight_unit": "G",
            "length": 25,
            "width": 18,
            "height": 5,
            "dimension_unit": "CM",
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
                    },
                }
            ],
        }
    ],
    "service": "tracked_24",
    "reference": "ORDER-1001",
    "options": {
        "package_format_identifier": "small_parcel",
        "order_reference": "ORDER-1001",
        "order_date": "2024-01-01T10:00:00Z",
        "carrier_name": "Royal Mail OBA",
        "subtotal": 25.0,
        "shipping_cost_charged": 3.5,
        "order_tax": 0.0,
        "total": 28.5,
        "receive_email_notification": True,
        "receive_sms_notification": False,
        "include_label_in_response": True,
        "tags": [{"key": "channel", "value": "web"}],
    },
}

ShipmentRequest = {
    "items": [
        {
            "orderReference": "ORDER-1001",
            "recipient": {
                "address": {
                    "fullName": "John Smith",
                    "companyName": "Example Ltd",
                    "addressLine1": "1 High Street",
                    "city": "London",
                    "postcode": "SW1A1AA",
                    "countryCode": "GB",
                }
            },
            "sender": {"tradingName": "Test Warehouse"},
            "packages": [
                {
                    "weightInGrams": 500,
                    "packageFormatIdentifier": "smallParcel",
                    "dimensions": {
                        "heightInMms": 50,
                        "widthInMms": 180,
                        "depthInMms": 250,
                    },
                    "contents": [
                        {
                            "SKU": "SKU-1",
                            "name": "Blue T-Shirt",
                            "quantity": 2,
                            "unitValue": 12.5,
                            "unitWeightInGrams": 150,
                            "customsDescription": "Blue T-Shirt",
                            "extendedCustomsDescription": "Blue T-Shirt",
                            "customsCode": "610910",
                            "originCountryCode": "GB",
                            "customsDeclarationCategory": "saleOfGoods",
                            "requiresExportLicence": False,
                            "stockLocation": "A1",
                            "useOriginPreference": True,
                            "supplementaryUnits": "1",
                        }
                    ],
                }
            ],
            "orderDate": "2024-01-01T10:00:00Z",
            "subtotal": 25.0,
            "shippingCostCharged": 3.5,
            "total": 28.5,
            "currencyCode": "GBP",
            "postageDetails": {
                "serviceCode": "TPN24",
                "serviceRegisterCode": "01",
                "carrierName": "Royal Mail OBA",
                "receiveEmailNotification": True,
                "receiveSmsNotification": False,
            },
            "tags": [{"key": "channel", "value": "web"}],
            "label": {"includeLabelInResponse": True},
            "orderTax": 0.0,
        }
    ]
}

ShipmentRequestWithBillingAddress = copy.deepcopy(ShipmentRequest)
ShipmentRequestWithBillingAddress["items"][0]["billing"] = {
    "address": {
        "fullName": "Billing Contact",
        "companyName": "Example Ltd",
        "addressLine1": "2 Billing Street",
        "city": "London",
        "postcode": "EC1A1AA",
        "countryCode": "GB",
    },
    "phoneNumber": "07111111111",
    "emailAddress": "billing@example.com",
}

ShipmentRequestWithOrderIdFallback = copy.deepcopy(ShipmentRequest)
ShipmentRequestWithOrderIdFallback["items"][0]["orderReference"] = "ORDER-ID-1001"

ShipmentResponseCreatedOnly = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": "RM123456789GB",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ShipmentResponse = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": "2024-01-01T11:00:00Z",
            "shippedOn": "2024-01-01T12:00:00Z",
            "trackingNumber": "RM123456789GB",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ShipmentResponseWithoutTopLevelTracking = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": None,
            "packages": [{"packageNumber": 1, "trackingNumber": "RM999999999GB"}],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ShipmentResponseWithMultiplePackages = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": None,
            "packages": [
                {"packageNumber": 1, "trackingNumber": "RM111111111GB"},
                {"packageNumber": 2, "trackingNumber": "RM222222222GB"},
            ],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ShipmentResponseWithoutLabel = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": "RM123456789GB",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
            "label": None,
            "labelErrors": [],
            "generatedDocuments": [],
        }
    ],
    "failedOrders": [],
}

ShipmentResponseEmptyCreatedOrders = {
    "successCount": 0,
    "errorsCount": 0,
    "createdOrders": [],
    "failedOrders": [],
}

ShipmentResponseWithoutTracking = {
    "successCount": 1,
    "errorsCount": 0,
    "createdOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "packages": [{"packageNumber": 1}],
            "label": "JVBERi0xLjQKJcfs...",
            "labelErrors": [],
            "generatedDocuments": ["label"],
        }
    ],
    "failedOrders": [],
}

ShipmentErrorResponse = {
    "code": "BadRequest",
    "message": "The request is invalid",
    "details": "One or more validation errors occurred",
}

ShipmentArrayErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "BadRequest",
        "message": "Invalid shipment request",
    }
]

ShipmentNestedErrorsResponse = {
    "errors": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "code": "BadRequest",
            "description": "Validation failed",
        },
        {
            "orderIdentifier": 12345679,
            "orderReference": "ORDER-1002",
            "code": "Forbidden",
            "description": "Service not available",
        },
    ]
}

ShipmentFailedOrdersValidationResponse = {
    "successCount": 0,
    "errorsCount": 1,
    "createdOrders": [],
    "failedOrders": [
        {
            "order": {
                "orderReference": "ORDER-1001",
            },
            "errors": [
                {
                    "errorCode": 1001,
                    "errorMessage": "Validation failed",
                    "fields": [
                        {
                            "fieldName": "recipient.address.postcode",
                            "value": "",
                        },
                        {
                            "fieldName": "packages[0].weightInGrams",
                            "value": None,
                        },
                    ],
                }
            ],
        }
    ],
}

ParsedShipmentResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "tracking_number": "RM123456789GB",
        "shipment_identifier": "12345678",
        "label_type": "PDF",
        "docs": ANY,
        "meta": {
            "order_identifier": 12345678,
            "order_reference": "ORDER-1001",
            "created_on": "2024-01-01T10:00:00Z",
            "order_date": "2024-01-01T10:00:00Z",
            "printed_on": "2024-01-01T10:01:00Z",
            "manifested_on": "2024-01-01T11:00:00Z",
            "shipped_on": "2024-01-01T12:00:00Z",
            "tracking_numbers": ["RM123456789GB"],
            "shipment_identifiers": ["12345678", "ORDER-1001"],
            "package_tracking_numbers": ["RM123456789GB"],
            "generated_documents": ["label"],
            "tracking_number_provided": True,
        },
    },
    [],
]

ParsedShipmentErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "The request is invalid",
            "details": {
                "operation": "create_shipment",
                "details": "One or more validation errors occurred",
            },
        }
    ],
]

ParsedShipmentFailedOrdersValidationResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "1001",
            "message": "Validation failed — check required fields: recipient.address.postcode, packages[0].weightInGrams",
            "details": {
                "operation": "create_shipment",
                "order_reference": "ORDER-1001",
                "fields": [
                    {"field": "recipient.address.postcode", "value": ""},
                    {"field": "packages[0].weightInGrams", "value": None},
                ],
            },
        },
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "1001",
            "message": "Validation failed — field 'recipient.address.postcode' is required",
            "details": {
                "operation": "create_shipment",
                "order_reference": "ORDER-1001",
                "field": "recipient.address.postcode",
                "value": "",
            },
        },
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "1001",
            "message": "Validation failed — field 'packages[0].weightInGrams' is required",
            "details": {
                "operation": "create_shipment",
                "order_reference": "ORDER-1001",
                "field": "packages[0].weightInGrams",
                "value": None,
            },
        },
    ],
]

ShipmentPayloadWithoutTags = copy.deepcopy(ShipmentPayloadRichBase)
ShipmentPayloadWithoutTags["options"].pop("tags", None)
# ---------------------------------------------------------------------------
# Cancel shipment
# ---------------------------------------------------------------------------

# Karrio stores shipment/order identifiers as strings, but Royal Mail expects
# numeric order identifiers to remain unquoted in the path.
ShipmentCancelPayload = {"shipment_identifier": "12345678"}
ShipmentCancelReferencePayload = {"shipment_identifier": "ORDER-1001"}

ShipmentCancelRequest = {"orderIdentifiers": "12345678"}

ShipmentCancelResponse = {
    "deletedOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "orderInfo": "Deleted successfully",
        }
    ],
    "errors": [],
}

ShipmentCancelErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "NotFound",
        "message": "Order not found",
    }
]

ShipmentCancelMultiErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "NotFound",
        "message": "Order not found",
    },
    {
        "accountOrderNumber": 988,
        "channelOrderReference": "WEB-124",
        "code": "Forbidden",
        "message": "Order already manifested",
    },
]

ParsedShipmentCancelResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "operation": "Cancel Shipment",
        "success": True,
    },
    [],
]

ParsedShipmentCancelErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order not found",
            "details": {
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Manifest creation / retrieval / retry
# ---------------------------------------------------------------------------

# Karrio's generic ManifestRequest can include shipment_identifiers, but
# Royal Mail Click & Drop manifest creation does not accept them in the
# request body. The provider ignores them and sends only `carrierName`.
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
    "options": {"carrier_name": "Royal Mail OBA"},
}

ManifestPayloadSingleOrder = copy.deepcopy(ManifestPayload)
ManifestPayloadSingleOrder["shipment_identifiers"] = ["12345678"]

ManifestRequest = {"carrierName": "Royal Mail OBA"}

ManifestResponse = {"manifestNumber": 1001, "documentPdf": "JVBERi0xLjQKJcfs..."}

ManifestResponseWithoutPdf = {"manifestNumber": 1002, "documentPdf": None}

ManifestErrorResponse = {
    "errors": [{"code": "Forbidden", "description": "Feature not available"}]
}

ManifestNestedErrorResponse = {
    "errors": [
        {"code": "Forbidden", "description": "Feature not available"},
        {"code": "BadRequest", "description": "No eligible orders found"},
    ]
}

ParsedManifestResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "doc": ANY,
        "meta": {
            "manifest_number": 1001,
            "status": "completed",
            "document_available": True,
        },
    },
    [],
]

ParsedManifestErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Feature not available",
            "details": {"operation": "manifest"},
        }
    ],
]

GetManifestPayload = {"manifest_number": 1001}

ManifestIdentifierRequest = {"manifestIdentifier": 1001}

GetManifestResponse = {
    "manifestNumber": 1001,
    "status": "Completed",
    "documentPdf": "JVBERi0xLjQKJcfs...",
}

GetManifestErrorResponse = {
    "errors": [{"code": "Forbidden", "description": "Manifest not found"}]
}

ParsedGetManifestResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "doc": ANY,
        "meta": {
            "manifest_number": 1001,
            "status": "completed",
            "document_available": True,
        },
    },
    [],
]

ParsedGetManifestErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Manifest not found",
            "details": {"operation": "manifest"},
        }
    ],
]

RetryManifestPayload = {"manifest_number": 1002}

RetryManifestIdentifierRequest = {"manifestIdentifier": 1002}

RetryManifestResponse = {"manifestNumber": 1002}

RetryManifestErrorResponse = {
    "errors": [{"code": "BadRequest", "description": "Manifest cannot be retried"}]
}

ParsedRetryManifestResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "meta": {
            "manifest_number": 1002,
            "status": "in_progress",
            "document_available": False,
        },
    },
    [],
]

ParsedRetryManifestErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Manifest cannot be retried",
            "details": {"operation": "manifest"},
        }
    ],
]

# ---------------------------------------------------------------------------
# Label retrieval
# ---------------------------------------------------------------------------

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

LabelRequest = {
    "orderIdentifiers": "12345678",
    "query": {
        "documentType": "postageLabel",
        "includeReturnsLabel": False,
        "includeCN": True,
    },
}

LabelResponse = b"%PDF-1.4 test label pdf"

LabelErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "NotFound",
        "message": "Order not found",
    }
]

LabelErrorResponseBytes = b'[{"code":"NotFound","message":"Order not found"}]'

LabelNestedErrorResponse = {
    "errors": [
        {
            "accountOrderNumber": 987,
            "channelOrderReference": "WEB-123",
            "code": "NotFound",
            "description": "Order not found",
        }
    ]
}

ParsedLabelResponse = [
    {
        "label": "JVBERi0xLjQgdGVzdCBsYWJlbCBwZGY=",
        "pdf_label": "JVBERi0xLjQgdGVzdCBsYWJlbCBwZGY=",
    },
    [],
]

ParsedLabelErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order not found",
            "details": {
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
                "operation": "get_label",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Order status
# ---------------------------------------------------------------------------

OrderStatusPayload = {"items": [{"order_identifier": 12345678, "status": "despatched"}]}

OrderStatusResetPayload = {"items": [{"order_identifier": 12345678, "status": "new"}]}

OrderStatusOtherCourierPayload = {
    "items": [
        {
            "order_identifier": 12345678,
            "status": "despatchedByOtherCourier",
            "tracking_number": "OTHER123456",
            "despatch_date": "2024-01-01T12:00:00Z",
            "shipping_carrier": "Other Carrier",
            "shipping_service": "Express",
        }
    ]
}

OrderStatusRequest = {"items": [{"orderIdentifier": 12345678, "status": "despatched"}]}

OrderStatusResponse = {
    "updatedOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "status": "despatched",
        }
    ],
    "errors": [],
}

OrderStatusPartialSuccessResponse = {
    "updatedOrders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "status": "despatched",
        }
    ],
    "errors": [
        {
            "orderIdentifier": 12345679,
            "orderReference": "ORDER-1002",
            "code": "BadRequest",
            "message": "Invalid status update request",
        }
    ],
}

OrderStatusErrorResponse = [
    {
        "orderIdentifier": 12345678,
        "orderReference": "ORDER-1001",
        "status": "despatched",
        "code": "BadRequest",
        "message": "Invalid status update request",
    }
]

ParsedOrderStatusResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "operation": "Update Order Status",
        "success": True,
    },
    [],
]

ParsedOrderStatusErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Invalid status update request",
            "details": {
                "operation": "update_order_status",
                "order_identifier": 12345678,
                "order_reference": "ORDER-1001",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Return shipment
# ---------------------------------------------------------------------------

ParsedReturnShipmentWithoutShipmentResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "return_shipment_error",
            "message": "Unable to parse return shipment response",
            "details": {"operation": "create_return_shipment"},
        }
    ],
]

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

ReturnShipmentPayloadWithReturnAddress = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadWithReturnAddress["return_address"] = {
    "address_line1": "9 Merchant Returns Lane",
    "city": "Manchester",
    "postal_code": "M11AE",
    "country_code": "GB",
    "state_code": "",
    "person_name": "Returns Team",
    "company_name": "Merchant Returns Hub",
}

ReturnShipmentPayloadWithOrderId = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadWithOrderId["reference"] = ""
ReturnShipmentPayloadWithOrderId["order_id"] = "ORDER-ID-RET-1001"

ReturnShipmentPayloadRawServiceCode = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadRawServiceCode["service"] = "TSS"

ReturnShipmentPayloadWithServiceOptionOverride = copy.deepcopy(ReturnShipmentPayload)
ReturnShipmentPayloadWithServiceOptionOverride["service"] = "tracked_24"
ReturnShipmentPayloadWithServiceOptionOverride["options"] = {"service_code": "TSS"}

ReturnShipmentRequestWithServiceOptionOverride = copy.deepcopy(ReturnShipmentRequest)

ReturnShipmentRequest = {
    "service": {"serviceCode": "TSS"},
    "shipment": {
        "customerReference": {"reference": "ORDER-1001"},
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
        },
    },
}

ReturnShipmentResponse = {
    "shipment": {
        "trackingNumber": "RM123456789GB",
        "uniqueItemId": "0A12345678901234",
    },
    "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
    "label": "JVBERi0xLjQKJcfs...",
}

ReturnShipmentResponseWithoutLabel = {
    "shipment": {
        "trackingNumber": "RM123456789GB",
        "uniqueItemId": "0A12345678901234",
    },
    "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
    "label": None,
}

ReturnShipmentResponseWithoutShipment = {
    "shipment": None,
    "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
    "label": "JVBERi0xLjQKJcfs...",
}

ReturnShipmentResponseWithoutTracking = {
    "shipment": {"uniqueItemId": "0A12345678901234"},
    "qrCode": "iVBORw0KGgoAAAANSUhEUgAA...",
    "label": "JVBERi0xLjQKJcfs...",
}

ReturnShipmentErrorResponse = {
    "code": "BadRequest",
    "message": "Invalid return request",
    "details": "Service code TSS is not available for this account",
}

ReturnShipmentArrayErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "BadRequest",
        "message": "Invalid return request",
    }
]

ParsedReturnShipmentResponse = [
    {
        "carrier_id": "royalmail_clickdrop",
        "carrier_name": "royalmail_clickdrop",
        "tracking_number": "RM123456789GB",
        "shipment_identifier": "0A12345678901234",
        "label_type": "PDF",
        "docs": {
            "label": "JVBERi0xLjQKJcfs...",
            "pdf_label": "JVBERi0xLjQKJcfs...",
        },
        "meta": {
            "qr_code": "iVBORw0KGgoAAAANSUhEUgAA...",
            "is_return": True,
            "unique_item_id": "0A12345678901234",
            "tracking_number_provided": True,
        },
    },
    [],
]

ParsedReturnShipmentErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Invalid return request",
            "details": {
                "operation": "create_return_shipment",
                "details": "Service code TSS is not available for this account",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Service / settings expectations
# ---------------------------------------------------------------------------

ExpectedCoreServices = ["TPN24", "FE0"]
ExpectedReturnServices = ["TSS"]
ExpectedServiceRegisterCodes = {
    "TPN24": "01",
    "TSS": "01",
}
ExpectedDefaultConnectionConfig = {
    "base_url": "https://api.parcel.royalmail.com/api/v1",
    "label_type": "PDF",
}

# ---------------------------------------------------------------------------
# Get order details
# ---------------------------------------------------------------------------

GetOrderDetailsPayload = {"order_identifiers": [12345678]}

OrderLookupRequest = {"orderIdentifiers": "12345678"}

GetOrderDetailsResponse = [
    {
        "orderIdentifier": 12345678,
        "orderStatus": "new",
        "createdOn": "2024-01-01T10:00:00Z",
        "printedOn": "2024-01-01T10:01:00Z",
        "shippedOn": None,
        "postageAppliedOn": "2024-01-01T10:01:00Z",
        "manifestedOn": None,
        "orderDate": "2024-01-01T10:00:00Z",
        "tradingName": "Test Warehouse",
        "department": "Dispatch",
        "orderReference": "ORDER-1001",
        "subtotal": 25.0,
        "shippingCostCharged": 3.5,
        "total": 28.5,
        "weightInGrams": 500,
        "currencyCode": "GBP",
        "shippingDetails": {
            "shippingCost": 3.5,
            "trackingNumber": "RM123456789GB",
            "serviceCode": "TPN24",
            "shippingService": "Royal Mail Tracked 24",
            "shippingCarrier": "Royal Mail",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
        },
        "shippingInfo": {
            "firstName": "John",
            "lastName": "Smith",
            "companyName": "Example Ltd",
            "addressLine1": "1 High Street",
            "city": "London",
            "postcode": "SW1A1AA",
            "countryCode": "GB",
        },
        "billingInfo": {
            "firstName": "John",
            "lastName": "Smith",
            "companyName": "Example Ltd",
            "addressLine1": "1 High Street",
            "city": "London",
            "postcode": "SW1A1AA",
            "countryCode": "GB",
        },
        "orderLines": [
            {
                "SKU": "SKU-1",
                "name": "Blue T-Shirt",
                "quantity": 2,
                "unitValue": 12.5,
                "lineTotal": 25.0,
                "customsCode": 610910,
            }
        ],
        "tags": [{"key": "channel", "value": "web"}],
    }
]

GetOrderDetailsErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "NotFound",
        "message": "Order details not found",
    }
]

ParsedGetOrderDetailsResponse = [
    [
        {
            "orderIdentifier": 12345678,
            "orderStatus": "new",
            "createdOn": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "postageAppliedOn": "2024-01-01T10:01:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "tradingName": "Test Warehouse",
            "department": "Dispatch",
            "orderReference": "ORDER-1001",
            "subtotal": 25.0,
            "shippingCostCharged": 3.5,
            "total": 28.5,
            "weightInGrams": 500,
            "currencyCode": "GBP",
            "shippingDetails": ANY,
            "shippingInfo": ANY,
            "billingInfo": ANY,
            "orderLines": ANY,
            "tags": ANY,
        }
    ],
    [],
]

ParsedGetOrderDetailsErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order details not found",
            "details": {
                "operation": "get_order_details",
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Get order
# ---------------------------------------------------------------------------

GetOrderPayload = {"order_identifiers": [12345678]}

GetOrderResponse = [
    {
        "orderIdentifier": 12345678,
        "orderReference": "ORDER-1001",
        "createdOn": "2024-01-01T10:00:00Z",
        "orderDate": "2024-01-01T10:00:00Z",
        "printedOn": "2024-01-01T10:01:00Z",
        "manifestedOn": None,
        "shippedOn": None,
        "trackingNumber": "RM123456789GB",
        "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
    }
]

GetOrderErrorResponse = [
    {
        "accountOrderNumber": 987,
        "channelOrderReference": "WEB-123",
        "code": "NotFound",
        "message": "Order not found",
    }
]

ParsedGetOrderResponse = [
    [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "trackingNumber": "RM123456789GB",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
        }
    ],
    [],
]

ParsedGetOrderErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "NotFound",
            "message": "Order not found",
            "details": {
                "operation": "get_order",
                "account_order_number": 987,
                "channel_order_reference": "WEB-123",
            },
        }
    ],
]

# ---------------------------------------------------------------------------
# Rate
# ---------------------------------------------------------------------------

RatePayload = {
    "shipper": {
        "postal_code": "SW1A1AA",
        "city": "London",
        "country_code": "GB",
        "address_line1": "123 Test Street",
        "person_name": "Warehouse User",
        "company_name": "Test Warehouse",
    },
    "recipient": {
        "postal_code": "BT11AA",
        "city": "Belfast",
        "country_code": "GB",
        "address_line1": "3 Import Road",
        "person_name": "John Smith",
        "company_name": "Example Ltd",
    },
    "parcels": [
        {
            "weight": 0.5,
            "weight_unit": "KG",
            "length": 25,
            "width": 18,
            "height": 5,
            "dimension_unit": "CM",
            "packaging_type": "small_box",
        }
    ],
    "options": {"currency": "GBP"},
}

RateResponse = {
    "rates": [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "service": "TPN24",
            "currency": "GBP",
            "total_charge": 8.5,
            "transit_days": 1,
            "meta": {
                "service_name": "Royal Mail Tracked 24 (01 / 214708C1)",
                "carrier_service_code": "01",
                "rate_provider": "rate_table",
            },
        }
    ],
    "messages": [],
}

RateErrorResponse = {
    "rates": [],
    "messages": [{"code": "rate_table_error", "message": "No matching rate table entry found"}],
}

ParsedRateResponse = [
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "service": "TPN24",
            "currency": "GBP",
            "total_charge": 8.5,
            "transit_days": 1,
            "meta": {
                "service_name": "Royal Mail Tracked 24 (01 / 214708C1)",
                "carrier_service_code": "01",
                "rate_provider": "rate_table",
            },
        }
    ],
    [],
]

ParsedRateErrorResponse = [
    [],
    [{"code": "rate_table_error", "message": "No matching rate table entry found"}],
]

# ---------------------------------------------------------------------------
# List orders / order details
# ---------------------------------------------------------------------------

ListOrdersPayload = {
    "page_size": 2,
    "start_date_time": "2024-01-01T00:00:00Z",
    "end_date_time": "2024-01-31T23:59:59Z",
    "continuation_token": "NEXT123",
}

OrdersLookupRequest = {
    "pageSize": 2,
    "startDateTime": "2024-01-01T00:00:00Z",
    "endDateTime": "2024-01-31T23:59:59Z",
    "continuationToken": "NEXT123",
}

ListOrdersResponse = {
    "orders": [
        {
            "orderIdentifier": 12345678,
            "orderReference": "ORDER-1001",
            "createdOn": "2024-01-01T10:00:00Z",
            "orderDate": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "shippedOn": None,
            "trackingNumber": "RM123456789GB",
            "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
        }
    ],
    "continuationToken": "NEXT456",
}

ListOrdersErrorResponse = {"code": "BadRequest", "message": "Invalid paging request"}

ParsedListOrdersResponse = [
    {
        "orders": [
            {
                "orderIdentifier": 12345678,
                "orderReference": "ORDER-1001",
                "createdOn": "2024-01-01T10:00:00Z",
                "orderDate": "2024-01-01T10:00:00Z",
                "printedOn": "2024-01-01T10:01:00Z",
                "trackingNumber": "RM123456789GB",
                "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
            }
        ],
        "continuationToken": "NEXT456",
    },
    [],
]

ParsedListOrdersErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Invalid paging request",
            "details": {"operation": "list_orders"},
        }
    ],
]

ListOrderDetailsPayload = {
    "page_size": 2,
    "start_date_time": "2024-01-01T00:00:00Z",
    "end_date_time": "2024-01-31T23:59:59Z",
    "continuation_token": "NEXT123",
}

ListOrderDetailsResponse = {
    "orders": [
        {
            "orderIdentifier": 12345678,
            "orderStatus": "new",
            "createdOn": "2024-01-01T10:00:00Z",
            "printedOn": "2024-01-01T10:01:00Z",
            "shippedOn": None,
            "postageAppliedOn": "2024-01-01T10:01:00Z",
            "manifestedOn": None,
            "orderDate": "2024-01-01T10:00:00Z",
            "tradingName": "Test Warehouse",
            "department": "Dispatch",
            "orderReference": "ORDER-1001",
            "subtotal": 25.0,
            "shippingCostCharged": 3.5,
            "total": 28.5,
            "weightInGrams": 500,
            "currencyCode": "GBP",
            "shippingDetails": {
                "shippingCost": 3.5,
                "trackingNumber": "RM123456789GB",
                "serviceCode": "TPN24",
                "shippingService": "Royal Mail Tracked 24",
                "shippingCarrier": "Royal Mail",
                "packages": [{"packageNumber": 1, "trackingNumber": "RM123456789GB"}],
            },
            "shippingInfo": {
                "firstName": "John",
                "lastName": "Smith",
                "companyName": "Example Ltd",
                "addressLine1": "1 High Street",
                "city": "London",
                "postcode": "SW1A1AA",
                "countryCode": "GB",
            },
            "billingInfo": {
                "firstName": "John",
                "lastName": "Smith",
                "companyName": "Example Ltd",
                "addressLine1": "1 High Street",
                "city": "London",
                "postcode": "SW1A1AA",
                "countryCode": "GB",
            },
            "orderLines": [
                {
                    "SKU": "SKU-1",
                    "name": "Blue T-Shirt",
                    "quantity": 2,
                    "unitValue": 12.5,
                    "lineTotal": 25.0,
                    "customsCode": 610910,
                }
            ],
            "tags": [{"key": "channel", "value": "web"}],
        }
    ],
    "continuationToken": "NEXT456",
}

ListOrderDetailsErrorResponse = {
    "code": "BadRequest",
    "message": "Invalid order details lookup request",
}

ParsedListOrderDetailsResponse = [{"orders": ANY, "continuationToken": "NEXT456"}, []]

ParsedListOrderDetailsErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "BadRequest",
            "message": "Invalid order details lookup request",
            "details": {"operation": "list_order_details"},
        }
    ],
]

# ---------------------------------------------------------------------------
# Version / return services
# ---------------------------------------------------------------------------

VersionRequest = {}

VersionResponse = {
    "commit": "abcdef1234567890",
    "build": "100",
    "release": "1.0.0",
    "releaseDate": "2024-01-01T00:00:00Z",
}

VersionErrorResponse = {
    "code": "Forbidden",
    "message": "Not authorised to view version information",
}

ParsedVersionResponse = [
    {
        "commit": "abcdef1234567890",
        "build": "100",
        "release": "1.0.0",
        "releaseDate": "2024-01-01T00:00:00Z",
    },
    [],
]

ParsedVersionErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Not authorised to view version information",
            "details": {"operation": "get_version"},
        }
    ],
]

ReturnServicesRequest = {}

ReturnServicesResponse = {
    "services": [
        {
            "carrierGuid": "carrier-guid-1",
            "carrierServiceGuid": "service-guid-1",
            "serviceName": "Tracked Returns 48",
            "serviceCode": "TSS",
        }
    ]
}

ReturnServicesErrorResponse = {
    "code": "Forbidden",
    "message": "Not authorised to view return services",
}

ParsedReturnServicesResponse = [
    {
        "services": [
            {
                "carrierGuid": "carrier-guid-1",
                "carrierServiceGuid": "service-guid-1",
                "serviceName": "Tracked Returns 48",
                "serviceCode": "TSS",
            }
        ]
    },
    [],
]

ParsedReturnServicesErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Not authorised to view return services",
            "details": {"operation": "get_return_services"},
        }
    ],
]
