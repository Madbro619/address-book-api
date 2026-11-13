"""FastAPI application factory and address endpoints."""
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse

from app.database import AddressRepository
from app.geo import distance_km
from app.schemas import AddressCreate, AddressRead, AddressUpdate, NearbyAddress

logger = logging.getLogger("address_book")
AddressId = Annotated[int, Path(gt=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def create_app(database_path: str | None = None) -> FastAPI:
    repo = AddressRepository(database_path or os.getenv("ADDRESS_BOOK_DB", "data/addresses.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        repo.initialize()
        logger.info("Address book initialized")
        yield

    app = FastAPI(title="Address Book API", version="1.0.0", lifespan=lifespan,
                  description="SQLite address book. Coordinates are decimal degrees; distances are kilometres.")

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        # Avoid logging address bodies or query coordinates.
        logger.info("method=%s path=%s status=%s duration_ms=%.2f", request.method,
                    request.url.path, response.status_code, (perf_counter() - start) * 1000)
        return response

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        logger.error("Database operation failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Database unavailable; please retry later"})

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok"}

    @app.post("/addresses", response_model=AddressRead, status_code=201, tags=["Addresses"])
    def create_address(address: AddressCreate, response: Response):
        result = repo.create(address.model_dump())
        response.headers["Location"] = f"/addresses/{result['id']}"
        return result

    @app.get("/addresses", response_model=list[AddressRead], tags=["Addresses"])
    def list_addresses(limit: Limit = 20, offset: Offset = 0):
        return repo.list_addresses(limit, offset)

    # Static route must precede the dynamic /{address_id} route.
    @app.get("/addresses/nearby", response_model=list[NearbyAddress], tags=["Addresses"])
    def nearby_addresses(
        latitude: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
        longitude: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
        radius_km: Annotated[float, Query(ge=0, allow_inf_nan=False)],
        limit: Limit = 20, offset: Offset = 0,
    ):
        matches = []
        for address in repo.all():
            distance = distance_km(latitude, longitude, address["latitude"], address["longitude"])
            if distance <= radius_km:
                matches.append({**address, "distance_km": distance})
        matches.sort(key=lambda item: (item["distance_km"], item["id"]))
        return matches[offset:offset + limit]

    @app.get("/addresses/{address_id}", response_model=AddressRead, tags=["Addresses"])
    def get_address(address_id: AddressId):
        result = repo.get(address_id)
        if result is None:
            raise HTTPException(404, "Address not found")
        return result

    @app.patch("/addresses/{address_id}", response_model=AddressRead, tags=["Addresses"])
    def update_address(address_id: AddressId, address: AddressUpdate):
        result = repo.update(address_id, address.model_dump(exclude_unset=True))
        if result is None:
            raise HTTPException(404, "Address not found")
        return result

    @app.delete("/addresses/{address_id}", status_code=204, tags=["Addresses"])
    def delete_address(address_id: AddressId):
        if not repo.delete(address_id):
            raise HTTPException(404, "Address not found")
        return Response(status_code=204)

    return app


app = create_app()
