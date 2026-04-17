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
