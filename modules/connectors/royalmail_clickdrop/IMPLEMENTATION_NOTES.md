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
- Uses generated schema models under `karrio/schemas/royalmail_clickdrop/`.
- Carrier services are loaded from `services.csv`; blank lines are ignored.
- Click & Drop credentials and tracking credentials are kept separate.
- Connection config remains in `units.py`; required credentials remain in `utils.py`.

## Rating model

Royal Mail Click & Drop does not expose live rate endpoints in the supplied public API.  
This integration therefore uses Karrio's universal rate-table mixin to support the `rating` capability from configured carrier service tables.

## Shipping behavior

- `shipment_date` and `shipping_date` are normalized to `plannedDespatchDate`.
- `order_date` remains a separate field and is not overwritten by shipment date aliases.
- Order references continue to be supported, including numeric-looking references when the caller explicitly uses the `reference` field.
- Label retrieval, order lookup, and related follow-up operations still support carrier-generated numeric order identifiers.
- Cancel requests can explicitly force reference-style encoding for numeric-looking order references via `options.reference` or `options.order_reference`.
- Notification target defaults to the first contact with an available email address in this order: `recipient`, `sender`, `billing`.
- `receiveEmailNotification` defaults against the resolved notification target rather than always assuming the recipient.

## Customs and multi-piece behavior

- Single-package international shipments may fall back to `payload.customs.commodities` when parcel-level `items` are not supplied.
- Multi-package shipments no longer duplicate shipment-level customs commodities onto every parcel.
- For multi-package international shipments, parcel-level `items` should be supplied when parcel-specific customs contents are required.
- Shipment subtotal calculation supports both object-style commodities and raw dict-style parcel items.
- When parcel-level items are absent, order-level subtotal calculation may fall back to shipment-level `customs.commodities`.

## Dangerous goods behavior

- `dangerous_goods_quantity` supports fractional numeric values and is no longer restricted to integers.

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

## Important limitations

- The Click & Drop public API spec does not expose live carrier rating endpoints.
- The Click & Drop public API and the Royal Mail tracking API use different credentials and base URLs.
- Tracking enrichment is currently sequential, not async fan-out.
- For multi-piece international shipments, automatic allocation of shipment-level customs commodities across packages is intentionally not attempted. Provide parcel-level `items` when customs contents differ by parcel.
- `services.csv` remains the source for account-supported service mapping. Example values present in the YAML but not supported by the account are intentionally not surfaced.
