# Royal Mail Click & Drop Karrio Extension Notes

## Endpoint coverage

### Click & Drop shipping API

| Method | Path                                    | Implemented? | Notes                                                          |
| ------ | --------------------------------------- | -----------: | -------------------------------------------------------------- |
| GET    | `/version`                              |          Yes | `proxy.get_version`, `orders.query.parse_get_version_response` |
| GET    | `/orders/{orderIdentifiers}`            |          Yes | Get order                                                      |
| DELETE | `/orders/{orderIdentifiers}`            |          Yes | Cancel shipment/order                                          |
| PUT    | `/orders/status`                        |          Yes | Update order status                                            |
| GET    | `/orders/{orderIdentifiers}/full`       |          Yes | Get order details                                              |
| GET    | `/orders`                               |          Yes | List orders                                                    |
| POST   | `/orders`                               |          Yes | Create shipment                                                |
| GET    | `/orders/full`                          |          Yes | List order details                                             |
| GET    | `/orders/{orderIdentifiers}/label`      |          Yes | Label retrieval                                                |
| POST   | `/manifests`                            |          Yes | Create manifest                                                |
| POST   | `/manifests/retry/{manifestIdentifier}` |          Yes | Retry manifest                                                 |
| GET    | `/manifests/{manifestIdentifier}`       |          Yes | Get manifest                                                   |
| GET    | `/returns/services`                     |          Yes | Return services                                                |
| POST   | `/returns`                              |          Yes | Create return shipment                                         |

Click & Drop endpoint coverage is complete for the supplied public specification.

### Royal Mail tracking API

| Method | Path                                     | Implemented? | Notes                                       |
| ------ | ---------------------------------------- | -----------: | ------------------------------------------- |
| GET    | `/mailpieces/v2/summary?mailPieceId=...` |          Yes | Bulk summary lookup in chunks of up to 30   |
| GET    | `/mailpieces/v2/{mailPieceId}/events`    |          Yes | Per-piece event enrichment                  |
| GET    | `/mailpieces/v2/{mailPieceId}/signature` |          Yes | Proof-of-delivery enrichment when available |

## Design notes

- Built to follow the Karrio direct-carrier pattern.
- Uses generated schema models under `karrio/schemas/royalmail/`.
- Carrier services are loaded from `services.csv`; blank lines are ignored.
- Click & Drop credentials and tracking credentials are kept separate.
- Connection config remains in `units.py`; required credentials remain in `utils.py`.

## Rating model

Royal Mail Click & Drop does not expose a live rating endpoint in the supplied public API.

This connector therefore uses Karrio's universal local rate-table mixin with Royal Mail-specific pre-processing and post-filtering.

The rating flow is:

1. Load Royal Mail service/rate metadata from `services.csv`.
2. Expose only active, priced service rows through Karrio references and runtime rating.
3. Normalize requested raw Royal Mail service selectors into active Karrio service codes where possible.
4. Normalize parcel weights/dimensions for Karrio universal rating.
5. Apply Karrio universal local rate-table matching.
6. Filter returned rates by Royal Mail package-format compatibility.
7. Filter by requested insurance/compensation coverage.
8. Filter by requested service features, for example:
    - `options.is_tracked`
    - `options.features = ["tracked"]`
    - `options.signature_confirmation`
    - `options.dangerous_good`
    - Royal Mail age / ID verification options
9. Apply Royal Mail service surcharges:
    - fuel / energy surcharge
    - Parcelforce fuel / energy surcharge
    - green surcharge
    - date-limited peak surcharge
10. Apply selected option surcharges:

- signature on delivery
- age verification
- ID verification

11. Apply UK VAT when service metadata or connection config says VAT should be added.

Rates are therefore local/static, but the connector still enforces Royal Mail service capability rules before returning Karrio `RateDetails`.

## Service catalogue and selector model

`services.csv` is the source of truth for Royal Mail service metadata.

The connector intentionally separates active runtime services from full Click & Drop metadata:

| Use case                                | Source                                   |
| --------------------------------------- | ---------------------------------------- |
| Karrio service references               | active CSV rows with usable rate data    |
| Karrio rating                           | active CSV rows only                     |
| `ShippingService` enum                  | active CSV rows only                     |
| Click & Drop shipment metadata          | full CSV catalogue                       |
| `serviceRegisterCode` lookup            | full CSV catalogue                       |
| Return shipment service-code resolution | full return-service catalogue by default |
| Runtime return-service detection        | active return services only              |

This distinction is required because Royal Mail carrier service codes can be ambiguous or package-format dependent.

Example:

```text
CRL24 + largeLetter -> serviceRegisterCode 01
CRL24 + parcel      -> serviceRegisterCode 02
```

Some parcel metadata rows are inactive for rating/reference purposes but are still required to serialize valid Click & Drop shipment requests.

Raw Royal Mail carrier codes such as `CRL24`, `CRL48`, `OTA`, and `TSS` may be accepted for shipment creation. For rating, raw carrier codes are expanded into active canonical Karrio service codes where possible and then narrowed by package format.

## Shipping behavior

- `shipment_date` and `shipping_date` are normalized to `plannedDespatchDate`.
- `order_date` remains a separate field and is not overwritten by shipment date aliases.
- Order references continue to be supported, including numeric-looking references when the caller explicitly uses the `reference` field.
- Label retrieval, order lookup, and related follow-up operations still support carrier-generated numeric order identifiers.
- Cancel requests can explicitly force reference-style encoding for numeric-looking order references via `options.reference` or `options.order_reference`.
- Standard Karrio `shipping_charges` is accepted and mapped to Royal Mail `shippingCostCharged`.
- Standard Karrio `email_notification_to` is accepted and mapped to Royal Mail `sendNotificationsTo`.
- Notification target defaults to the first contact with an available email address in this order: `recipient`, `sender`, `billing`.
- `receiveEmailNotification` now respects explicit raw option input first and otherwise falls back to whether the resolved notification target actually has an email address.

## Customs and product line mapping

- Royal Mail package contents are built from normalized Karrio item / commodity data.
- The connector passes through all Royal Mail product fields when present in Karrio item data or item metadata:
    - `SKU`
    - `name`
    - `quantity`
    - `unitValue`
    - `unitWeightInGrams`
    - `customsDescription`
    - `extendedCustomsDescription`
    - `customsCode`
    - `originCountryCode`
    - `customsDeclarationCategory`
    - `requiresExportLicence`
    - `stockLocation`
    - `useOriginPreference`
    - `supplementaryUnits`
    - `licenseNumber`
    - `certificateNumber`
- Item metadata is used for Royal Mail-specific customs/product extensions when present.
- Shipment-level `customs.content_type` and item-level `customs_declaration_category` values are normalized into Royal Mail’s allowed category set:
    - `none`
    - `gift`
    - `commercialSample`
    - `documents`
    - `other`
    - `returnedGoods`
    - `saleOfGoods`
    - `mixedContent`

## Customs and multi-piece behavior

- Single-package international shipments will fall back to `payload.customs.commodities` when parcel-level `items` are not supplied.
- Multi-package shipments no longer duplicate shipment-level customs commodities onto every parcel.
- For multi-package international shipments, parcel-level `items` should be supplied when parcel-specific customs contents are required.
- Shipment subtotal calculation supports both object-style commodities and raw dict-style parcel items.
- For order-level subtotal and currency resolution, shipment-level `customs.commodities` is preferred when present.
- Karrio commodity fields are mapped into Royal Mail customs item fields as follows:
    - `description` / `customs_description` -> `customsDescription`
    - `description` / `extended_customs_description` -> `extendedCustomsDescription`
    - `hs_code` / `customs_code` -> `customsCode`
    - `origin_country` / `origin_country_code` -> `originCountryCode`
    - `customs.content_type` -> `customsDeclarationCategory`
- Royal Mail customs declaration categories are normalized to:
    - `none`
    - `gift`
    - `commercialSample`
    - `documents`
    - `other`
    - `returnedGoods`
    - `saleOfGoods`
    - `mixedContent`

## Importer behavior

- Importer payloads support both carrier-shaped keys like `country` and normalized Karrio-style keys like `country_code`.
- When only `country_code` is supplied, the connector resolves it to the Royal Mail importer country name.

## Dangerous goods behavior

The connector maps Royal Mail dangerous-goods fields when supplied through shipment options:

- `contains_dangerous_goods`
- `dangerous_goods_un_code`
- `dangerous_goods_description`
- `dangerous_goods_quantity`

The connector performs basic value normalization only. Detailed dangerous-goods eligibility remains the responsibility of the Royal Mail account configuration, service rules, and Click & Drop API validation.

- `dangerous_goods_description` is documented in the api spec as an integer but surely it should be more than this, so i've set it as a string (this might be a oversight on the royal mail api) unless they use set descriptions the store as ID's still yet to confirm this

## Tracking model

Tracking is implemented separately via the Royal Mail tracking API.

| Tracking API feature                            | Status | Notes                                                                   |
| ----------------------------------------------- | ------ | ----------------------------------------------------------------------- |
| Separate Royal Mail tracking credentials        | Yes    | `tracking_client_id` and `tracking_client_secret` required for tracking |
| Configurable tracking base URL                  | Yes    | Via connection config                                                   |
| Bulk summary lookup                             | Yes    | Uses `/summary` in chunks of up to 30 mail pieces                       |
| Multiple tracking numbers in one Karrio request | Yes    | Sequential summary + per-piece events enrichment                        |
| Event history normalization                     | Yes    | Maps carrier events to Karrio tracking events                           |
| Delivered state inference                       | Yes    | Uses POD metadata, event names, and summary status category             |
| Estimated delivery date                         | Yes    | Exposed when returned by Royal Mail                                     |
| Tracking API error normalization                | Yes    | Top-level and mail-piece-level error handling                           |
| `GET /{mailPieceId}/signature`                  | Yes    | Retrieved when available from tracking links or metadata                |
| Proof of delivery merge                         | Yes    | Signature payload merged into tracking detail                           |
| Signatory/recipient name mapping                | Yes    | Exposed in `TrackingInfo.customer_name`                                 |
| Proof-of-delivery image normalization           | Yes    | SVG is base64-encoded; base64 PNG is passed through unchanged           |

If tracking credentials are not provided the call logic reverts to click and drop basic tracking but this has account limitations trying to use it without access will get the following error

"Forbidden (Feature not available)"

/orders/{orderIdentifiers}/full:
description: Reserved for ChannelShipper customers only
'403':
description: Forbidden (Feature not available)

That /full endpoint is not available for normal Click & Drop / OBA accounts. It is ChannelShipper-only customers

## Royal Mail surcharge and VAT implementation

Royal Mail surcharges are implemented as data-driven service-level surcharges on top of Karrio's universal rating engine.

`services.csv` contains base rate and surcharge metadata. The connector loads recurring service surcharges into Karrio `ServiceLevel.surcharges`, then filters or augments those surcharges during rating.

Implemented surcharge types:

| Surcharge                 | Behaviour                                                                         |
| ------------------------- | --------------------------------------------------------------------------------- |
| Fuel / Energy             | Loaded from CSV and applied when present                                          |
| Parcelforce Fuel / Energy | Loaded from CSV and applied to Parcelforce rows                                   |
| Green surcharge           | Loaded from CSV and applied when present                                          |
| Peak surcharge            | Loaded from CSV but only applied inside the configured peak date window           |
| Signature on delivery     | Option-triggered via `signature_confirmation` / `request_signature_upon_delivery` |
| Age verification          | Option-triggered via `royalmail_age_verification` / `age_verification`            |
| ID verification           | Option-triggered via `royalmail_id_verification` / `id_verification`              |

Peak surcharge dates can come from service metadata:

- `peak_surcharge_start_date`
- `peak_surcharge_end_date`

The request date used for peak surcharge selection is resolved from, in order:

1. explicit surcharge/rate date
2. `planned_despatch_date`
3. generic shipment/ship/shipping date
4. current date

### UK VAT

Royal Mail rate rows are treated as VAT-exclusive unless metadata says otherwise.

VAT can be applied when:

- service metadata has `vat_applicable = true`
- service metadata has `vat_rate_percentage`
- connection config has `apply_uk_vat_to_rates = true`

VAT is not applied when:

- service metadata has `vat_applicable = false`
- service metadata has `prices_include_vat = true`
- VAT has already been added to the rate

VAT is added as a separate Karrio `ChargeDetails` tax line with id:

```text
royalmail_uk_vat
```

The rated result includes metadata such as:

- `net_charge`
- `vat_amount`
- `gross_charge`
- `vat_rate_percentage`
- `prices_include_vat`

## Important limitations

- The Click & Drop public API spec does not expose live carrier rating endpoints.
- The Click & Drop public API and the Royal Mail tracking API use different credentials and base URLs.
- Tracking enrichment is currently sequential, not async fan-out.
- For multi-piece international shipments, automatic allocation of shipment-level customs commodities across packages is intentionally not attempted. Provide parcel-level `items` when customs contents differ by parcel.
- `services.csv` remains the source for account-supported service mapping. Example values present in the YAML but not supported by the account are intentionally not surfaced.
