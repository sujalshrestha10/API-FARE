"""FastAPI application for calculating vehicle trip fares with road distance and elevation gain."""

import os
from typing import Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel, Field

load_dotenv()

BAATO_API_KEY = os.getenv("BAATO_API_KEY")

app = FastAPI(
    title="Fare Calculation Microservice",
    description="API for calculating vehicle trip fares with road distance and elevation gain.",
    version="1.0.0",
)


class Location(BaseModel):
    """Geographic coordinate representation for pickup and dropoff locations."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude of location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of location")


class FareEstimateRequest(BaseModel):
    """Payload model for estimating trip fare."""

    vehicle_id: Optional[str] = Field(None, description="Optional vehicle ID")
    trip_type: Literal["ONE_WAY", "TWO_WAY"] = Field(..., description="Trip type")
    base_fare: float = Field(..., ge=0, description="Base fare amount")
    pickup: Location = Field(..., description="Pickup location coordinates")
    dropoff: Location = Field(..., description="Dropoff location coordinates")
    per_km_rate: float = Field(..., ge=0, description="Fare rate per kilometer")
    two_way_discount_percent: float = Field(
        ..., ge=0, le=100, description="Discount percentage for round trips"
    )


async def get_elevation(lat: float, lon: float) -> float:
    """Fetches elevation in meters for a coordinate using Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, timeout=5.0)
            if res.status_code == 200:
                data = res.json()
                elevations = data.get("elevation", [0.0])
                return float(elevations[0]) if elevations else 0.0
        except httpx.HTTPError as e:
            print(f"Elevation fetch HTTP error for ({lat}, {lon}): {e}")
    return 0.0


async def get_route_and_elevation(pickup: dict, dropoff: dict):
    """Fetches road distance from Baato API and calculates elevation metrics."""
    if not BAATO_API_KEY:
        raise HTTPException(
            status_code=500, detail="BAATO_API_KEY is not configured in .env"
        )

    pickup_str = f"{pickup['latitude']},{pickup['longitude']}"
    dropoff_str = f"{dropoff['latitude']},{dropoff['longitude']}"

    baato_url = "https://api.baato.io/api/v1/directions"
    params = (
        ("key", BAATO_API_KEY),
        ("points[]", pickup_str),
        ("points[]", dropoff_str),
        ("mode", "car"),
    )

    async with httpx.AsyncClient() as client:
        baato_res = await client.get(baato_url, params=params)
        if baato_res.status_code != 200:
            raise HTTPException(
                status_code=502, detail=f"Baato API error: {baato_res.text}"
            )

        baato_data = baato_res.json()

    distance_in_meters = baato_data["data"][0]["distanceInMeters"]
    distance_km = round(distance_in_meters / 1000.0, 2)

    pickup_elev = await get_elevation(pickup["latitude"], pickup["longitude"])
    dropoff_elev = await get_elevation(dropoff["latitude"], dropoff["longitude"])

    elevation_diff = round(dropoff_elev - pickup_elev, 2)
    elevation_gain = max(0.0, elevation_diff)

    return {
        "distance_in_meters": distance_in_meters,
        "distance_km": distance_km,
        "pickup_elevation_m": pickup_elev,
        "dropoff_elevation_m": dropoff_elev,
        "elevation_gain_m": elevation_gain,
    }


def calculate_fare(
    base_fare: float,
    per_km_rate: float,
    distance_km: float,
    trip_type: str,
    two_way_discount_percent: float,
) -> dict:
    """Calculates gross fare, discount amount, and final total fare."""
    distance_fare = per_km_rate * distance_km

    if trip_type == "TWO_WAY":
        distance_fare *= 2

    subtotal = base_fare + distance_fare
    discount_amount = 0.0

    if trip_type == "TWO_WAY" and two_way_discount_percent > 0:
        discount_amount = round(subtotal * (two_way_discount_percent / 100.0), 2)

    total_fare = round(subtotal - discount_amount, 2)

    return {
        "base_fare": base_fare,
        "per_km_rate": per_km_rate,
        "distance_km": distance_km,
        "subtotal": round(subtotal, 2),
        "discount_amount": discount_amount,
        "total_fare": total_fare,
    }


@app.post("/api/v1/fare/estimate")
async def estimate_fare(payload: FareEstimateRequest):
    """Calculates route distance, elevation stats, and estimated trip fare."""
    pickup_dict = payload.pickup.model_dump()
    dropoff_dict = payload.dropoff.model_dump()

    route_info = await get_route_and_elevation(pickup_dict, dropoff_dict)

    fare_details = calculate_fare(
        base_fare=payload.base_fare,
        per_km_rate=payload.per_km_rate,
        distance_km=route_info["distance_km"],
        trip_type=payload.trip_type,
        two_way_discount_percent=payload.two_way_discount_percent,
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
