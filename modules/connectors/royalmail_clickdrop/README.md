# karrio.royalmail_clickdrop

Royal Mail Click & Drop integration for the [Karrio](https://github.com/karrioapi/karrio) multi-carrier shipping SDK.

This extension adds support for:

- Royal Mail Click & Drop shipment creation
- Return shipment creation
- Shipment cancellation
- Manifest creation and retrieval
- Label retrieval
- Order status updates
- Order lookup and listing helpers
- Return-services and version helpers
- Royal Mail Tracking API support

> Note: the Python package/module path is `royalmail_clickdrop`, but the current Karrio gateway id exposed by this extension is `royalmail`.

---

## Requirements

- Python `3.11+`
- A Royal Mail Click & Drop API key
- For tracking: Royal Mail Tracking API credentials (`tracking_client_id` and `tracking_client_secret`)

---

## Installation

### From the Karrio monorepo

```bash
pip install -e ./modules/connectors/royalmail_clickdrop
```

### If packaged independently

```bash
pip install karrio.royalmail_clickdrop
```

---

## Gateway ID

Use the carrier through Karrio with:

```python
karrio.gateway["royalmail"]
```

Even though the extension package is named `royalmail_clickdrop`, the registered provider id is currently `royalmail`.

---

## Features

### Core shipping features

- `Rating.fetch(...)`  
  Uses Karrio’s local/static service-level rating mixin rather than a live Royal Mail rating API.

- `Shipment.create(...)`  
  Creates Click & Drop orders via `POST /orders`

- `Shipment.cancel(...)`  
  Cancels orders via `DELETE /orders/{orderIdentifiers}`

- `Manifest.create(...)`  
  Creates manifests via `POST /manifests`

- `Tracking.fetch(...)`  
  Uses the Royal Mail Tracking API:
    - `GET /mailpieces/v2/summary`
    - `GET /mailpieces/v2/{mailPieceId}/events`
    - optional signature retrieval when available

### Royal Mail-specific helper operations

This connector also exposes helper methods for Royal Mail-specific endpoints:

- `GET /version`
- `GET /orders/{orderIdentifiers}`
- `GET /orders`
- `GET /orders/{orderIdentifiers}/full`
- `GET /orders/full`
- `GET /returns/services`
- `GET /orders/{orderIdentifiers}/label`
- `PUT /orders/status`
- `GET /manifests/{manifestIdentifier}`
- `POST /manifests/retry/{manifestIdentifier}`
- `POST /returns`

These helpers are available through the carrier `mapper` and `proxy`.

---

## Configuration

### Required settings

```python
from karrio.mappers.royalmail_clickdrop.settings import Settings

settings = Settings(
    api_key="YOUR_CLICK_AND_DROP_API_KEY",
)
```

### Tracking-enabled settings

```python
from karrio.mappers.royalmail_clickdrop.settings import Settings

settings = Settings(
    api_key="YOUR_CLICK_AND_DROP_API_KEY",
    tracking_client_id="YOUR_TRACKING_CLIENT_ID",
    tracking_client_secret="YOUR_TRACKING_CLIENT_SECRET",
)
```

### Available `Settings` fields

| Field                    | Required | Description                                       |
| ------------------------ | -------: | ------------------------------------------------- |
| `api_key`                |      yes | Royal Mail Click & Drop bearer token              |
| `tracking_client_id`     |       no | Royal Mail Tracking API client id                 |
| `tracking_client_secret` |       no | Royal Mail Tracking API client secret             |
| `test_mode`              |       no | Standard Karrio flag                              |
| `account_country_code`   |       no | Used for currency/default account context         |
| `services`               |       no | Optional configured service list for rating mixin |
| `metadata`               |       no | Standard Karrio metadata                          |
| `config`                 |       no | Carrier connection config                         |

---

## Connection config

Carrier-specific connection behavior can be configured through `settings.config`.

### Supported connection config keys

| Key                                | Type   | Default                                   | Description                                             |
| ---------------------------------- | ------ | ----------------------------------------- | ------------------------------------------------------- |
| `base_url`                         | `str`  | `https://api.parcel.royalmail.com/api/v1` | Click & Drop API base URL                               |
| `tracking_base_url`                | `str`  | `https://api.royalmail.net`               | Tracking API base URL                                   |
| `carrier_name`                     | `str`  | `None`                                    | Default carrier name sent in shipment/manifest requests |
| `label_type`                       | `str`  | `PDF`                                     | Default label document type                             |
| `include_label_in_response`        | `bool` | `True`                                    | Request label data during shipment creation             |
| `include_return_label_in_response` | `bool` | `False`                                   | Request return label data by default                    |
| `shipping_options`                 | `list` | `[]`                                      | Optional configured defaults                            |
| `shipping_services`                | `list` | built-in catalog                          | Optional configured services                            |

Example:

```python
settings = Settings(
    api_key="YOUR_CLICK_AND_DROP_API_KEY",
    tracking_client_id="YOUR_TRACKING_CLIENT_ID",
    tracking_client_secret="YOUR_TRACKING_CLIENT_SECRET",
    config={
        "carrier_name": "Royal Mail OBA",
        "include_label_in_response": True,
        "include_return_label_in_response": False,
        "label_type": "PDF",
    },
)
```

---

## Quick start

### Initialize the gateway

```python
import karrio.sdk as karrio
from karrio.mappers.royalmail_clickdrop.settings import Settings

gateway = karrio.gateway["royalmail"].create(
    Settings(
        api_key="YOUR_CLICK_AND_DROP_API_KEY",
        tracking_client_id="YOUR_TRACKING_CLIENT_ID",          # optional unless tracking
        tracking_client_secret="YOUR_TRACKING_CLIENT_SECRET",  # optional unless tracking
        config={
            "carrier_name": "Royal Mail OBA",
            "include_label_in_response": True,
        },
    )
)
```

---

## Create a shipment

```python
import karrio.core.models as models
import karrio.sdk as karrio

request = models.ShipmentRequest(
    shipper=models.Address(
        company_name="Sender Ltd",
        person_name="Warehouse Team",
        address_line1="1 Shipping Street",
        city="London",
        postal_code="SW1A1AA",
        country_code="GB",
        phone_number="+441234567890",
        email="sender@example.com",
    ),
    recipient=models.Address(
        company_name="Receiver Ltd",
        person_name="Jane Doe",
        address_line1="10 Market Road",
        city="Manchester",
        postal_code="M11AE",
        country_code="GB",
        phone_number="+447700900123",
        email="jane@example.com",
    ),
    parcels=[
        models.Parcel(
            weight=1.2,
            length=30,
            width=20,
            height=10,
            packaging_type="small_parcel",
        )
    ],
    service="TPN24",
    options={
        "order_reference": "ORDER-1001",
        "planned_despatch_date": "2025-01-10",
        "include_label_in_response": True,
        "receive_email_notification": True,
    },
)

shipment, messages = (
    karrio.Shipment.create(request)
    .from_(gateway)
    .parse()
)
```

---

## Create a return shipment

```python
return_request = models.ShipmentRequest(
    shipper=models.Address(
        company_name="Customer",
        person_name="Jane Doe",
        address_line1="10 Market Road",
        city="Manchester",
        postal_code="M11AE",
        country_code="GB",
        phone_number="+447700900123",
        email="jane@example.com",
    ),
    recipient=models.Address(
        company_name="Returns Hub",
        person_name="Returns Team",
        address_line1="1 Returns Way",
        city="London",
        postal_code="SW1A1AA",
        country_code="GB",
        phone_number="+441234567890",
        email="returns@example.com",
    ),
    parcels=[
        models.Parcel(
            weight=0.8,
            packaging_type="small_parcel",
        )
    ],
    service="TSS",
)

shipment, messages = (
    gateway.mapper.parse_return_shipment_response(
        gateway.proxy.create_return_shipment(
            gateway.mapper.create_return_shipment_request(return_request)
        )
    )
)
```

---

## Fetch tracking

Tracking uses Royal Mail’s separate tracking API credentials.

```python
import karrio.core.models as models
import karrio.sdk as karrio

tracking_request = models.TrackingRequest(
    tracking_numbers=["AA123456789GB"]
)

tracking_details, messages = (
    karrio.Tracking.fetch(tracking_request)
    .from_(gateway)
    .parse()
)
```

---

## Create a manifest

```python
import karrio.core.models as models
import karrio.sdk as karrio

manifest_request = models.ManifestRequest(
    options={
        "carrier_name": "Royal Mail OBA",
    }
)

manifest, messages = (
    karrio.Manifest.create(manifest_request)
    .from_(gateway)
    .parse()
)
```

---

## Cancel a shipment

```python
import karrio.core.models as models
import karrio.sdk as karrio

cancel_request = models.ShipmentCancelRequest(
    shipment_identifier="12345678"
)

confirmation, messages = (
    karrio.Shipment.cancel(cancel_request)
    .from_(gateway)
    .parse()
)
```

---

## Retrieve a label

The connector supports label retrieval through the Royal Mail Click & Drop label endpoint.

```python
label_request = gateway.mapper.create_label_request({
    "order_identifier": 12345678,
    "document_type": "postageLabel",
    "include_returns_label": False,
    "include_cn": True,
})

documents, messages = gateway.mapper.parse_label_response(
    gateway.proxy.get_label(label_request)
)
```

---

## Royal Mail helper endpoints

These helpers are useful when you need functionality beyond Karrio’s normalized core actions.

### Get API version

```python
request = gateway.mapper.create_get_version_request({})
payload, messages = gateway.mapper.parse_get_version_response(
    gateway.proxy.get_version(request)
)
```

### Get an order

```python
request = gateway.mapper.create_get_order_request({
    "order_identifier": 12345678,
})

payload, messages = gateway.mapper.parse_get_order_response(
    gateway.proxy.get_order(request)
)
```

You can also pass a reference:

```python
request = gateway.mapper.create_get_order_request({
    "reference": "ORDER-1001",
})
```

### List orders

```python
request = gateway.mapper.create_list_orders_request({
    "pageSize": 50,
    "startDateTime": "2025-01-01T00:00:00Z",
    "endDateTime": "2025-01-31T23:59:59Z",
})

payload, messages = gateway.mapper.parse_list_orders_response(
    gateway.proxy.list_orders(request)
)
```

### Get detailed order data

```python
request = gateway.mapper.create_get_order_details_request({
    "order_identifier": 12345678,
})

payload, messages = gateway.mapper.parse_get_order_details_response(
    gateway.proxy.get_order_details(request)
)
```

### List detailed orders

```python
request = gateway.mapper.create_list_order_details_request({
    "pageSize": 50,
})

payload, messages = gateway.mapper.parse_list_order_details_response(
    gateway.proxy.list_order_details(request)
)
```

### Update order status

```python
request = gateway.mapper.create_order_status_request({
    "items": [
        {
            "order_identifier": 12345678,
            "order_status": "despatched",
        }
    ]
})

confirmation, messages = gateway.mapper.parse_order_status_response(
    gateway.proxy.update_order_status(request)
)
```

### Get return services

```python
request = gateway.mapper.create_get_return_services_request({})
payload, messages = gateway.mapper.parse_get_return_services_response(
    gateway.proxy.get_return_services(request)
)
```

### Get a manifest

```python
request = gateway.mapper.create_get_manifest_request({
    "manifest_identifier": "MANIFEST-123",
})

payload, messages = gateway.mapper.parse_get_manifest_response(
    gateway.proxy.get_manifest(request)
)
```

### Retry a manifest

```python
request = gateway.mapper.create_retry_manifest_request({
    "manifest_identifier": "MANIFEST-123",
})

payload, messages = gateway.mapper.parse_retry_manifest_response(
    gateway.proxy.retry_manifest(request)
)
```

---

## Carrier-specific shipment options

The connector exposes Royal Mail-specific options through `options={...}` on shipment requests.

Common options include:

- `order_reference`
- `order_date`
- `planned_despatch_date`
- `special_instructions`
- `service_code`
- `package_format_identifier`
- `billing`
- `importer`
- `tags`
- `send_notifications_to`
- `carrier_name`
- `service_register_code`
- `consequential_loss`
- `receive_email_notification`
- `receive_sms_notification`
- `request_signature_upon_delivery`
- `is_local_collect`
- `safe_place`
- `department`
- `air_number`
- `ioss_number`
- `requires_export_license`
- `commercial_invoice_number`
- `commercial_invoice_date`
- `recipient_eori_number`
- `include_label_in_response`
- `include_cn`
- `include_returns_label`
- `contains_dangerous_goods`
- `dangerous_goods_un_code`
- `dangerous_goods_description`
- `dangerous_goods_quantity`

For the complete list, see:

- `karrio.providers.royalmail_clickdrop.units.ShippingOption`

---

## Services and packaging

This extension provides:

- Royal Mail packaging type mappings
- common package presets
- a service catalog from `services.csv`
- canonical convenience aliases in `ShippingService`

Examples of service codes include:

- `BPL1`
- `BPL2`
- `TPN24`
- `CRL24`
- `CRL48`
- `SD1`
- `SD4`
- `OTA`
- `OTC`
- `FE0`
- `TSS`

Examples of packaging types include:

- `letter`
- `large_letter`
- `small_parcel`
- `medium_parcel`
- `large_parcel`
- `documents`

For the authoritative enums, see:

- `karrio.providers.royalmail_clickdrop.units.ShippingService`
- `karrio.providers.royalmail_clickdrop.units.PackagingType`
- `karrio.providers.royalmail_clickdrop.units.PackagePresets`

---

## Important Royal Mail behavior

### Order identifiers vs references

Royal Mail endpoints often use `orderIdentifiers`.

This connector handles both:

- numeric order identifiers
- string order references

When a string reference is supplied, the helper methods encode it in the Royal Mail-compatible format automatically.

### Tracking credentials are separate

Shipment and order operations use the Click & Drop API key.

Tracking requires separate credentials:

- `tracking_client_id`
- `tracking_client_secret`

If those are not supplied, tracking requests will fail.

### Ratings are local/static

Royal Mail Click & Drop does not provide a live real-time rating endpoint in this integration.

`Rating.fetch(...)` uses Karrio’s rating mixin and configured service metadata instead of calling a live Royal Mail pricing API.

---

## Development

Run the Royal Mail Click & Drop test suite from the connector or repository root, depending on your environment.

Typical areas covered by the tests include:

- settings and connection config
- services and package metadata
- shipment creation and parsing
- return shipments
- shipment cancellation
- manifests
- labels
- tracking
- order status updates
- order helper endpoints
- static/local rating behavior

See:

- `tests/royalmail_clickdrop/`

---

## References

- Karrio repository: <https://github.com/karrioapi/karrio>
- Karrio development docs: <https://docs.karrio.io/product/resources/development#working-on-karrio-sdk-core-and-all-extensions>
- Carrier integration guide: `CARRIER_INTEGRATION_GUIDE.md`
- Carrier integration FAQ: `CARRIER_INTEGRATION_FAQ.md`
- Royal Mail Click & Drop API: <https://api.parcel.royalmail.com/>
- Royal Mail Tracking API: <https://api.parcel.royalmail.com/>

---

## Status

Current plugin metadata status: `development`

## Future changes Needed

- I think I'm using too many custom helpers as I dont know all the libs that karrio provided some of the opperations are probably built in to karrio
- create.py needs simplifying the \_build helpers need writing into one and again more of the handling of values are probably available in the libs enum
