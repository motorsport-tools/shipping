# Royal Mail Click & Drop Karrio Extension Notes

## Scope
This connector bundle implements the Royal Mail Click & Drop public API operations exposed in the provided OpenAPI spec:

- `POST /orders` -> create shipment
- `DELETE /orders/{orderIdentifiers}` -> cancel shipment
- `GET /orders/{orderIdentifiers}/label` -> fetch label/document
- `POST /returns` -> create return shipment
- `PUT /orders/status` -> update order status
- `POST /manifests` -> create manifest

## Design notes
- Built to follow the Karrio direct-carrier pattern.
- Uses generated schema models under `karrio/schemas/royalmail_clickdrop/`.
- Carrier services are loaded from `services.csv`, and the loader ignores blank lines
- Connection config remains in `units.py`; required credentials remain in `utils.py`.

## Important limitations
- The provided Royal Mail Click & Drop public API spec does not expose a direct tracking endpoint.
- The spec also does not expose a live rating endpoint in the same way other parcel APIs do like DHL or fedex.
- The bundle therefore focuses on shipping, returns, manifests, label retrieval, and order-status operations, while still exposing the service catalog for service selection.
- The provided Royal Mail Click & Drop public API spec yaml lists services that not all accounts use so services.csv is the source of for our account services.

## Rating model
Royal Mail Click & Drop does not expose live rate endpoints in the provided API.
This integration uses Karrio's universal rate-table mixin to support the `rating`
capability from configured carrier service tables.

## Tracking model
Tracking is implemented separately via the Royal Mail tracking API plugin.


