from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from reservas_api.domain.enums import ReservationStatus


class CustomerDTO(BaseModel):
    """Customer identity data for reservation creation."""

    first_name: str = Field(min_length=1, max_length=100, examples=["Ana"])
    last_name: str = Field(min_length=1, max_length=100, examples=["Perez"])
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40, examples=["+34123456789"])


class VehicleDTO(BaseModel):
    """Vehicle snapshot used for reservation and provider dispatch."""

    vehicle_code: str = Field(min_length=1, max_length=120, examples=["VH001"])
    model: str = Field(min_length=1, max_length=120, examples=["Corolla"])
    category: str = Field(min_length=1, max_length=80, examples=["Economy"])


class ReservationRequestDTO(BaseModel):
    """Request body for `POST /api/v1/reservations`."""

    supplier_code: str = Field(min_length=1, max_length=40, examples=["SUP01"])
    pickup_office_code: str = Field(min_length=1, max_length=40, examples=["MAD01"])
    dropoff_office_code: str = Field(min_length=1, max_length=40, examples=["MAD02"])
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal = Field(gt=Decimal("0"), decimal_places=2, examples=["180.50"])
    customer: CustomerDTO
    vehicle: VehicleDTO

    @model_validator(mode="after")
    def validate_dropoff_after_pickup(self) -> ReservationRequestDTO:
        if self.dropoff_datetime <= self.pickup_datetime:
            raise ValueError("dropoff_datetime must be after pickup_datetime")
        return self


class ReservationResponseDTO(BaseModel):
    """Response payload returned after reservation creation."""

    reservation_code: str
    status: ReservationStatus
    supplier_code: str
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorResponseDTO(BaseModel):
    """Error payload used for business, validation and server failures."""

    error: str
    message: str
    request_id: str | None = None
    code: str | None = None
