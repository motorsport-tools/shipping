# karrio.royalmail_clickdrop

This package is a Royal Mail Click and Drop extension of the [karrio](https://pypi.org/project/karrio) multi carrier shipping SDK.

## Requirements

`Python 3.11+`


## Dependancies

`pycountry`

this is used to convert country ISOs

## Installation

```bash
pip install -e karrio.royalmail_clickdrop
```

## Usage

```python
import karrio.sdk as karrio
from karrio.mappers.royalmail_clickdrop.settings import Settings


# Initialize a carrier gateway
royalmail_clickdrop = karrio.gateway["royalmail_clickdrop"].create(
    Settings(
        ...
    )
)
```

Check the [Karrio Mutli-carrier SDK docs](https://docs.karrio.io) for Shipping API requests

##testing

 **111 tests** in total in `tests/royalmail_clickdrop/`.

- `test_shipment.py` — 25
- `test_return_shipment.py` — 10
- `test_label.py` — 8
- `test_order_status.py` — 8
- `test_cancel.py` — 6
- `test_manifest.py` — 6
- `test_services.py` — 6
- `test_settings.py` — 6
- `test_get_manifest.py` — 4
- `test_get_order.py` — 4
- `test_get_order_details.py` — 4
- `test_get_return_services.py` — 4
- `test_get_version.py` — 4
- `test_list_order_details.py` — 4
- `test_list_orders.py` — 4
- `test_rate.py` — 4
- `test_retry_manifest.py` — 4
- `test_tracking.py` — 1

All test payloads are contained in fixtures.py with comments for the purpose of all tests
