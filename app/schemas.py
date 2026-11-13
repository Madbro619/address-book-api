"""Request and response contracts; coordinates use decimal degrees."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=200)]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class AddressCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    street: Text
    city: Text
    country: Text
    postal_code: Annotated[str, Field(min_length=1, max_length=32)]
    latitude: Latitude
    longitude: Longitude


class AddressUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    street: Text | None = None
    city: Text | None = None
    country: Text | None = None
    postal_code: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode="after")
    def require_non_null_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Address fields cannot be null")
        return self


class AddressRead(AddressCreate):
    id: int


class NearbyAddress(AddressRead):
    distance_km: float
