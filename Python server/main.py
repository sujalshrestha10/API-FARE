"""FastAPI application for calculating vehicle trip fares."""

import os
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fare_calculator import calculate_fare
from route_service import get_route_and_elevation

load_dotenv()
BAATO_API_KEY = os.getenv("BAATO_API_KEY")


app = FastAPI(
    title="Fare Calculation Microservice",
    description=(
        "API for calculating vehicle trip fares "
        "with road distance and cumulative elevation."
    ),
    version="1.0.0",
)


# =============================================================================
# Request Models
# =============================================================================


class Location(BaseModel):
    """Geographic coordinate representation."""

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude of location",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude of location",
    )


class FareEstimateRequest(BaseModel):
    """Payload model for estimating trip fare."""

    vehicle_id: Optional[str] = Field(
        None,
        description="Optional vehicle ID",
    )

    trip_type: Literal[
        "ONE_WAY",
        "TWO_WAY",
    ] = Field(
        ...,
        description="Trip type",
    )

    base_fare: float = Field(
        ...,
        ge=0,
        description="Base fare amount",
    )

    pickup: Location = Field(
        ...,
        description="Pickup location coordinates",
    )

    dropoff: Location = Field(
        ...,
        description="Dropoff location coordinates",
    )

    per_km_rate: float = Field(
        ...,
        ge=0,
        description="Fare rate per kilometer",
    )

    two_way_discount_percent: float = Field(
        ...,
        ge=0,
        le=100,
        description="Discount percentage for two-way trips",
    )

    elevation_rate_per_meter: float = Field(
        0.0,
        ge=0,
        description=("Fare charged per meter of cumulative " "elevation gain"),
    )


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health")
async def health_check() -> dict:
    """Return service health status."""

    return {
        "success": True,
        "service": "fare-calculation",
        "status": "healthy",
    }


# =============================================================================
# Configuration
# =============================================================================


def require_baato_api_key() -> None:
    """Ensure Baato API key is configured."""

    if not BAATO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail=("BAATO_API_KEY is not configured " "in .env"),
        )


# =============================================================================
# Fare Estimate
# =============================================================================


@app.post("/api/v1/fare/estimate")
async def estimate_fare(
    payload: FareEstimateRequest,
) -> dict:
    """Calculate road distance, elevation, and fare."""

    require_baato_api_key()

    pickup = payload.pickup.model_dump()
    dropoff = payload.dropoff.model_dump()

    # The route service expects exactly:
    #
    #     pickup
    #     dropoff
    #     client
    #
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            30.0,
            connect=10.0,
        ),
        follow_redirects=True,
    ) as client:

        route_info = await get_route_and_elevation(
            pickup,
            dropoff,
            client,
        )

    # -------------------------------------------------------------------------
    # Fare calculation
    # -------------------------------------------------------------------------

    fare_details = calculate_fare(
        trip_type=payload.trip_type,
        base_fare=payload.base_fare,
        distance_km=route_info["distance_km"],
        per_km_rate=payload.per_km_rate,
        two_way_discount_percent=(payload.two_way_discount_percent),
        elevation_gain_m=(
            route_info.get(
                "elevation_gain_m",
                0.0,
            )
            or 0.0
        ),
        elevation_loss_m=(
            route_info.get(
                "elevation_loss_m",
                0.0,
            )
            or 0.0
        ),
        elevation_rate_per_meter=(payload.elevation_rate_per_meter),
    )

    return {
        "success": True,
        "data": {
            "vehicle_id": payload.vehicle_id,
            "trip_type": payload.trip_type,
            "route": route_info,
            "fare": fare_details,
        },
    }
