# Royal Mail Click & Drop Karrio Extension Notes

## Scope
This connector bundle implements the Royal Mail Click & Drop public API operations exposed in the provided OpenAPI spec:

## Endpoint coverage

From the royal mail api specification YAML, these are the public paths:

| Method | Path | Implemented? | Notes |
|---|---|---:|---|
| GET | `/version` | Yes | `proxy.get_version`, `order_query.parse_get_version_response` |
| GET | `/orders/{orderIdentifiers}` | Yes | get order |
| DELETE | `/orders/{orderIdentifiers}` | Yes | cancel |
| PUT | `/orders/status` | Yes | order status |
| GET | `/orders/{orderIdentifiers}/full` | Yes | get order details |
| GET | `/orders` | Yes | list orders |
| POST | `/orders` | Yes | create shipment |
| GET | `/orders/full` | Yes | list order details |
| GET | `/orders/{orderIdentifiers}/label` | Yes | label retrieval |
| POST | `/manifests` | Yes | create manifest |
| POST | `/manifests/retry/{manifestIdentifier}` | Yes | retry manifest |
| GET | `/manifests/{manifestIdentifier}` | Yes | get manifest |
| GET | `/returns/services` | Yes | return services |
| POST | `/returns` | Yes | create return shipment |

endpoint coverage, this is **complete**.

## Design notes
- Built to follow the Karrio direct-carrier pattern.
- Uses generated schema models under `karrio/schemas/royalmail_clickdrop/`.
- Carrier services are loaded from `services.csv`, and the loader ignores blank lines
- Connection config remains in `units.py`; required credentials remain in `utils.py`.

## Important limitations
- The provided Royal Mail Click & Drop public API spec does not expose a direct tracking endpoint. (this is a seperate API and will come later in the design)
- The spec also does not expose a live rating endpoint in the same way other parcel APIs do like DHL or fedex.
- The bundle therefore focuses on shipping, returns, manifests, label retrieval, and order-status operations, while still exposing the service catalog for service selection.
- The provided Royal Mail Click & Drop public API spec yaml lists services that not all accounts use so services.csv is the source for our account services. Anything else is ignored like the examples in the yaml. for example we are intentionally Missing `guaranteedSaturdayDelivery`

## Rating model
Royal Mail Click & Drop does not expose live rate endpoints in the provided API.
This integration uses Karrio's universal rate-table mixin to support the `rating`
capability from configured carrier service tables.

## Tracking model
Tracking is implemented separately via the Royal Mail tracking API.

unfinished schema for tracking API

signature image retrieval
lightweight summary lookup

tracking is not currently updating status (to be implemented later want to be sure click and drop status is working correctly first)
