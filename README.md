# hlthstack for Python

Integrate Python backends with the [hlthstack](https://www.hlthstack.io/) partner REST API:
book health checkups and lab tests, in-clinic and online doctor consultations and ePharmacy
orders for your members, read their benefit wallets, pre-register members and their
dependants, and verify the webhooks hlthstack sends you.

This repository holds the official Python SDK (`hlthstack`) and two integration guides: one
for the SDK, one for calling the REST API directly over HTTP.

## Choose how to integrate

| | SDK | Plain REST API |
|---|---|---|
| Guide | [docs/sdk-integration.md](docs/sdk-integration.md) | [docs/api-integration.md](docs/api-integration.md) |
| Install | `pip install` from this GitHub repository | Nothing from hlthstack; any HTTP client (`requests`, `httpx`, ...) |
| Access tokens | Fetched, cached and refreshed for you; one retry after a 401 | You fetch, cache and refresh them (the guide has a helper) |
| Input validation | Every request checked against the API's rules before it is sent | You check inputs yourself, or rely on the API's 400/422 responses |
| Types | `TypedDict` requests and responses | Plain dicts |
| Sync / async | `Hlthstack` and `AsyncHlthstack` with the same methods | Whatever your HTTP client offers |
| Errors | One exception class per status, with the messages extracted | You parse the API's several error shapes |
| Webhooks | `verify_signature` helper and payload types | Verify the HS256 JWT yourself (the guide shows how, standard library only) |
| Dependencies | `httpx` | None beyond your HTTP client |

Pick the SDK unless you can't add a dependency or want full control over every request.
Both talk to the same API, so you can start with one and move to the other.

## SDK quickstart

```bash
pip install "git+https://github.com/hlthstack/python"
```

Pin a tag or commit for reproducible builds: `git+https://github.com/hlthstack/python@<tag>`.

```python
import os
from hlthstack import Hlthstack

with Hlthstack(
    username=os.environ["HLTHSTACK_USERNAME"],
    password=os.environ["HLTHSTACK_PASSWORD"],
    environment="staging",
) as client:
    providers = client.appointments.list_providers(
        service_name="ahc", package_ids=[1001], pincode="500081"
    )
    for provider in providers["providers"]:
        print(provider["provider_id"], provider["provider_name"])
```

Continue with the [SDK integration guide](docs/sdk-integration.md): booking, async,
configuration, multi-entity partners, uploads, pre-registration, validation, errors and
webhooks.

## Plain REST API quickstart

```bash
curl -u "$HLTHSTACK_USERNAME:$HLTHSTACK_PASSWORD" \
  https://staging-api.hlthstack.io/api/get-access-token
```

Then send `Authorization: Bearer <access_token>` on every other call. The
[plain REST API guide](docs/api-integration.md) walks through token caching, a full booking
with `requests`, uploads, pre-registration, errors, input checks and webhook verification.
Runnable scripts are in [`examples/api/`](examples/api/).

## Reference

- REST API guides: https://github.com/hlthstack/integration-guide
- OpenAPI spec: https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml

Credentials, the entity secret key and webhook secrets are server-side secrets: never ship
them in a browser or mobile app.

## License

MIT
