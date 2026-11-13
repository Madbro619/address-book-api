# Address Book API

A minimal Python 3 / FastAPI assignment with SQLite persistence, validated address CRUD, and nearby-address search. No GUI is required; use Swagger at `/docs`.

## Requirements

- Python 3.12 (tested on Python 3.12)
- pip; Git and GitHub CLI only for publishing

## Run locally — Linux / macOS

Extract the ZIP and open a terminal in its parent directory:

```bash
cd address-book-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Run locally — Windows PowerShell

```powershell
cd address-book-api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, run the virtual environment executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs and use **Try it out**. OpenAPI JSON: http://127.0.0.1:8000/openapi.json. Stop with Ctrl+C. `--reload` is for local development.

SQLite is created automatically at `data/addresses.db`, relative to your working directory. It persists across restarts. No database server or manual schema setup is needed. To use a different file:

```bash
ADDRESS_BOOK_DB=/tmp/my-addresses.db python -m uvicorn app.main:app
```

PowerShell: `$env:ADDRESS_BOOK_DB = 'C:\temp\addresses.db'` before running Uvicorn. Use a file-backed database, not `:memory:`, because repository operations use separate connections.

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| POST | `/addresses` | Create an address | 201 + Location header |
| GET | `/addresses` | List by ID, with limit/offset | 200 |
| GET | `/addresses/{id}` | Retrieve one | 200 |
| PATCH | `/addresses/{id}` | Update supplied fields | 200 |
| DELETE | `/addresses/{id}` | Delete one | 204, empty body |
| GET | `/addresses/nearby` | Search within radius | 200 |
| GET | `/health` | Process liveness | 200 |

Missing records return 404. Invalid bodies, coordinates, IDs, or query parameters return 422. Database errors return a sanitized 503 response. `/health` is a liveness endpoint, not a database readiness check.

### Create

Linux/macOS curl (PowerShell users can use Swagger):

```bash
curl -i -X POST http://127.0.0.1:8000/addresses \
  -H 'Content-Type: application/json' \
  -d '{"street":"12 Main Road","city":"Nagpur","country":"India","postal_code":"440001","latitude":21.1458,"longitude":79.0882}'
```

### List, retrieve, update and delete

Use the actual ID returned by POST; `1` below assumes the first record in a fresh database.

```bash
curl 'http://127.0.0.1:8000/addresses?limit=20&offset=0'
curl http://127.0.0.1:8000/addresses/1
curl -X PATCH http://127.0.0.1:8000/addresses/1 \
  -H 'Content-Type: application/json' -d '{"street":"24 Main Road"}'
curl -i -X DELETE http://127.0.0.1:8000/addresses/1
```

### Nearby search

Create at least one address before this request:

```bash
curl 'http://127.0.0.1:8000/addresses/nearby?latitude=21.1458&longitude=79.0882&radius_km=5&limit=20&offset=0'
```

Every result includes `distance_km`. Results are sorted by distance, with ID as a deterministic tie breaker. Radius is inclusive (`distance <= radius_km`); zero radius is allowed. Empty results are `[]`. Pagination is applied after filtering and sorting. Default limit is 20, maximum 100.

## Validation rules and assumptions

- Street, city, country, postal code and coordinates are required on creation.
- Text is stripped of surrounding whitespace; blank text is rejected.
- Street/city/country: 1–200 characters; postal code: 1–32 characters.
- Postal codes are strings so leading zeros are retained; no country-specific format is imposed.
- Latitude: -90 to 90; longitude: -180 to 180. Non-finite coordinates/radius are rejected.
- Coordinates use decimal degrees, and radius/distance use kilometres.
- PATCH changes only supplied fields. Empty updates, explicit nulls and unknown fields are rejected.
- Duplicate addresses are allowed; uniqueness was not part of the requirements.
- Validation checks structure and ranges, not whether an address physically exists or matches its coordinates.

## Tests

From the project directory, with the virtual environment active:

```bash
python -m unittest discover -s tests -v
```

13 tests cover CRUD, missing records, malformed inputs, SQL parameter binding, pagination, distance filtering and inclusive radius boundaries, persistence across application instances, sanitized database failures, documentation, known distances, poles, the antimeridian and antipodal points. Tests use isolated temporary SQLite files and never touch your application database.

## Structure and design

```text
app/
  main.py       Application factory, HTTP routes, lifespan and request logging
  schemas.py    Pydantic request/response models
  database.py   SQLite repository and schema
  geo.py        Haversine distance calculation
 tests/
  test_api.py   API integration and distance tests
```

- FastAPI provides routing, validation integration and generated Swagger documentation.
- Pydantic supplies explicit request and response contracts.
- Python's `sqlite3` keeps the dependency footprint small. SQL values are parameterized; update columns come from a fixed allowlist. Database constraints add a second layer of validation.
- Synchronous handlers run blocking SQLite work in FastAPI's worker thread pool. Each operation uses its own connection and transaction; connections are closed even on failure. WAL and a 10-second busy timeout support modest concurrent use.
- Standard-library logging records method, path, status and duration without address bodies or coordinate query strings. Uvicorn also provides server logs.
- Standard-library `unittest` and FastAPI TestClient/httpx provide automated tests without another test runner dependency.
- Haversine uses a mean Earth radius of 6371.0088 km. This is an approximate spherical, straight-line surface distance, not road distance or an ellipsoidal survey calculation. Search scans all records (O(n)) and sorts matching records; appropriate for this small assignment. Large datasets should use a spatial index/database.
- Automatic table creation keeps first run simple. Schema evolution would need migrations.
- Authentication, frontend, external geocoding, deployment and rate limiting are outside the assignment scope.

Reference documentation: https://fastapi.tiangolo.com/ and https://docs.pydantic.dev/latest/ .

## Publish to a public GitHub repository

Install Git and GitHub CLI (`gh`) first. From this project directory:

```bash
git init -b main
git add .
git commit -m "Implement FastAPI SQLite address book with nearby search and tests"
gh auth login
gh repo create address-book-api --public --source=. --remote=origin --push
gh repo view --json url --jq .url
```

If Git asks for your identity, configure your own `user.name` and `user.email`, then retry the commit. If `address-book-api` already exists in your account, choose a new repository name in the create command. Share the URL printed by the final command with the reviewer. No repository has been published by this archive.

After publication, reviewers can clone the printed repository URL, `cd address-book-api`, and follow the local setup instructions above.
