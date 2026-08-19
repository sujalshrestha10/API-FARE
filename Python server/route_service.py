"""Road routing and route geometry service.

This module is responsible for:
- Fetching road routes from Baato.
- Extracting road geometry from Baato responses.
- Decoding encoded polylines.
- Dynamically downsampling road geometry.
- Passing sampled road coordinates to the elevation service.
- Returning route distance and elevation information.
"""

import math
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

from elevation_service import get_route_elevation

# =============================================================================
# Configuration
# =============================================================================

load_dotenv()

BAATO_API_KEY = os.getenv("BAATO_API_KEY")

BAATO_URL = "https://api.baato.io/api/v1/directions"

BAATO_TIMEOUT_SECONDS = 20.0

# Target approximately this many elevation samples per route.
#
# This is intentionally NOT a fixed distance such as 100m.
#
# Example:
#
# 26 km route:
#     ~104m spacing -> ~250 points
#
# 259 km route:
#     ~1,040m spacing -> ~250 points
#
# This keeps Open-Meteo requests predictable for long routes.
TARGET_ELEVATION_POINTS = 250

# Never allow a pathological Baato response to consume unlimited memory.
MAX_ROUTE_COORDINATES = 100_000


# =============================================================================
# HTTP
# =============================================================================


async def get_baato_route(
    pickup: dict,
    dropoff: dict,
    client: httpx.AsyncClient,
) -> dict:
    """Fetch the driving route from Baato."""

    if not BAATO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail=("BAATO_API_KEY is not configured " "in .env"),
        )

    pickup_string = f"{pickup['latitude']}," f"{pickup['longitude']}"

    dropoff_string = f"{dropoff['latitude']}," f"{dropoff['longitude']}"

    # Use a dictionary with a list for points[].
    #
    # This works with httpx and also avoids the Pylance error caused by
    # list[tuple[str, str]] being inferred too narrowly.
    params: dict[str, Any] = {
        "key": BAATO_API_KEY,
        "points[]": [
            pickup_string,
            dropoff_string,
        ],
        "mode": "car",
    }

    try:
        response = await client.get(
            BAATO_URL,
            params=params,
            timeout=BAATO_TIMEOUT_SECONDS,
        )

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Baato API request timed out.",
        ) from exc

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Baato API request failed: {exc}",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Baato API error "
                f"(HTTP {response.status_code}): "
                f"{response.text[:500]}"
            ),
        )

    try:
        baato_data = response.json()

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Baato returned invalid JSON.",
        ) from exc

    try:
        routes = baato_data["data"]

        if not isinstance(routes, list):
            raise ValueError("Baato data is not a list.")

        if not routes:
            raise ValueError("Baato returned no routes.")

        route = routes[0]

        if not isinstance(route, dict):
            raise ValueError("Baato route is not an object.")

        distance_in_meters = float(route["distanceInMeters"])

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=("Invalid route response " "from Baato API."),
        ) from exc

    if not math.isfinite(distance_in_meters) or distance_in_meters <= 0:
        raise HTTPException(
            status_code=502,
            detail=("Baato returned an invalid " "route distance."),
        )

    return {
        "route": route,
        "distance_in_meters": (distance_in_meters),
        "distance_km": round(
            distance_in_meters / 1000.0,
            2,
        ),
    }


# =============================================================================
# Polyline Decoder
# =============================================================================


def decode_polyline(
    encoded: str,
) -> list[tuple[float, float]]:
    """Decode a Google-compatible encoded polyline.

    Returns:
        List of (latitude, longitude) coordinates.
    """

    if not encoded:
        return []

    coordinates: list[tuple[float, float]] = []

    index = 0
    latitude = 0
    longitude = 0

    length = len(encoded)

    try:
        while index < length:

            # ---------------------------------------------------------------
            # Latitude
            # ---------------------------------------------------------------

            result = 0
            shift = 0

            while True:
                if index >= length:
                    return coordinates

                byte = ord(encoded[index]) - 63

                index += 1

                result |= (byte & 0x1F) << shift

                shift += 5

                if byte < 0x20:
                    break

            delta_latitude = -(result >> 1) if result & 1 else result >> 1

            latitude += delta_latitude

            # ---------------------------------------------------------------
            # Longitude
            # ---------------------------------------------------------------

            result = 0
            shift = 0

            while True:
                if index >= length:
                    return coordinates

                byte = ord(encoded[index]) - 63

                index += 1

                result |= (byte & 0x1F) << shift

                shift += 5

                if byte < 0x20:
                    break

            delta_longitude = -(result >> 1) if result & 1 else result >> 1

            longitude += delta_longitude

            coordinates.append(
                (
                    latitude / 100000.0,
                    longitude / 100000.0,
                )
            )

    except (
        TypeError,
        ValueError,
    ):
        return []

    return coordinates


# =============================================================================
# Coordinate Helpers
# =============================================================================


def pairs_to_coordinates(
    pairs: list[Any],
) -> list[tuple[float, float]]:
    """Convert coordinate pairs to (latitude, longitude).

    Supports both common representations:

        [longitude, latitude]

    and:

        [latitude, longitude]

    Nepal coordinate bounds are used when they make the ordering
    unambiguous.
    """

    coordinates: list[tuple[float, float]] = []

    # Nepal geographic bounds.
    nepal_lat_min = 24.0
    nepal_lat_max = 32.0
    nepal_lon_min = 78.0
    nepal_lon_max = 90.0

    for pair in pairs:

        if not isinstance(
            pair,
            (list, tuple),
        ):
            continue

        if len(pair) < 2:
            continue

        try:
            first = float(pair[0])
            second = float(pair[1])

        except (
            TypeError,
            ValueError,
        ):
            continue

        first_is_nepal_lat = nepal_lat_min <= first <= nepal_lat_max

        second_is_nepal_lat = nepal_lat_min <= second <= nepal_lat_max

        first_is_nepal_lon = nepal_lon_min <= first <= nepal_lon_max

        second_is_nepal_lon = nepal_lon_min <= second <= nepal_lon_max

        # [latitude, longitude]
        if first_is_nepal_lat and second_is_nepal_lon:
            latitude = first
            longitude = second

        # [longitude, latitude]
        elif first_is_nepal_lon and second_is_nepal_lat:
            longitude = first
            latitude = second

        # Generic latitude/longitude detection.
        elif -90 <= first <= 90 and not -90 <= second <= 90:
            latitude = first
            longitude = second

        else:
            # Default to GeoJSON convention:
            # [longitude, latitude]
            longitude = first
            latitude = second

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        coordinates.append(
            (
                latitude,
                longitude,
            )
        )

    return coordinates


# =============================================================================
# Distance
# =============================================================================


def haversine_distance_m(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    """Calculate great-circle distance between two points in meters."""

    earth_radius_m = 6_371_000.0

    lat1, lon1 = point_a
    lat2, lon2 = point_b

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)

    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    a = min(
        1.0,
        max(0.0, a),
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius_m * c


# =============================================================================
# Dynamic Route Sampling
# =============================================================================


def calculate_sampling_spacing_m(
    route_distance_m: float,
    target_points: int = TARGET_ELEVATION_POINTS,
) -> float:
    """Calculate dynamic sampling spacing.

    The spacing scales with route length so that a route generally
    produces around 250 elevation samples.

    A minimum of 90m prevents very short routes from producing
    excessive samples.
    """

    if route_distance_m <= 0:
        return 100.0

    target_points = max(
        2,
        target_points,
    )

    spacing = route_distance_m / (target_points - 1)

    return max(
        90.0,
        spacing,
    )


def downsample_route(
    coordinates: list[tuple[float, float]],
    route_distance_m: float,
    target_points: int = TARGET_ELEVATION_POINTS,
) -> list[tuple[float, float]]:
    """Downsample a road polyline using dynamic spacing.

    This is the key production optimization.

    We do NOT use a fixed 100m spacing.

    Instead:

        spacing = route_distance / ~249 intervals

    This keeps the number of elevation samples approximately
    constant for short and long routes.
    """

    if len(coordinates) <= 2:
        return coordinates

    spacing_m = calculate_sampling_spacing_m(
        route_distance_m=route_distance_m,
        target_points=target_points,
    )

    sampled: list[tuple[float, float]] = [coordinates[0]]

    last_kept = coordinates[0]

    for point in coordinates[1:-1]:

        distance = haversine_distance_m(
            last_kept,
            point,
        )

        if distance >= spacing_m:
            sampled.append(point)
            last_kept = point

    # Always include the final destination.
    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])

    return sampled


# =============================================================================
# Route Geometry Extraction
# =============================================================================


def extract_route_coordinates(
    route: dict,
) -> list[tuple[float, float]]:
    """Extract road coordinates from a Baato route.

    Supports:
    - GeoJSON geometry
    - encoded polylines
    - raw coordinate arrays
    - legs
    - steps
    - common Baato geometry fields
    """

    # -------------------------------------------------------------------------
    # geometry object
    # -------------------------------------------------------------------------

    geometry = route.get("geometry")

    if isinstance(
        geometry,
        dict,
    ):

        coordinates = geometry.get("coordinates")

        if isinstance(
            coordinates,
            list,
        ):

            result = pairs_to_coordinates(coordinates)

            if len(result) >= 2:
                return result

        for field in (
            "points",
            "polyline",
            "encodedPolyline",
            "encoded_polyline",
        ):

            value = geometry.get(field)

            if isinstance(
                value,
                str,
            ):

                decoded = decode_polyline(value)

                if len(decoded) >= 2:
                    return decoded

    # -------------------------------------------------------------------------
    # geometry string
    # -------------------------------------------------------------------------

    if isinstance(
        geometry,
        str,
    ):

        decoded = decode_polyline(geometry)

        if len(decoded) >= 2:
            return decoded

    # -------------------------------------------------------------------------
    # geometry list
    # -------------------------------------------------------------------------

    if isinstance(
        geometry,
        list,
    ):

        result = pairs_to_coordinates(geometry)

        if len(result) >= 2:
            return result

    # -------------------------------------------------------------------------
    # Common encoded polyline fields
    # -------------------------------------------------------------------------

    for field in (
        "overview_polyline",
        "polyline",
        "shape",
        "encodedPolyline",
        "encoded_polyline",
        "points",
    ):

        value = route.get(field)

        if isinstance(
            value,
            dict,
        ):

            value = value.get("points") or value.get("geometry")

        if isinstance(
            value,
            str,
        ):

            decoded = decode_polyline(value)

            if len(decoded) >= 2:
                return decoded

        if isinstance(
            value,
            list,
        ):

            result = pairs_to_coordinates(value)

            if len(result) >= 2:
                return result

    # -------------------------------------------------------------------------
    # Legs and steps
    # -------------------------------------------------------------------------

    legs = route.get("legs")

    if isinstance(
        legs,
        list,
    ):

        all_coordinates: list[tuple[float, float]] = []

        for leg in legs:

            if not isinstance(
                leg,
                dict,
            ):
                continue

            leg_geometry = leg.get("geometry")

            if isinstance(
                leg_geometry,
                str,
            ):

                all_coordinates.extend(decode_polyline(leg_geometry))

            elif isinstance(
                leg_geometry,
                dict,
            ):

                leg_coordinates = leg_geometry.get("coordinates")

                if isinstance(
                    leg_coordinates,
                    list,
                ):

                    all_coordinates.extend(pairs_to_coordinates(leg_coordinates))

            elif isinstance(
                leg_geometry,
                list,
            ):

                all_coordinates.extend(pairs_to_coordinates(leg_geometry))

            steps = leg.get("steps")

            if not isinstance(
                steps,
                list,
            ):
                continue

            for step in steps:

                if not isinstance(
                    step,
                    dict,
                ):
                    continue

                step_geometry = step.get("geometry")

                if isinstance(
                    step_geometry,
                    str,
                ):

                    all_coordinates.extend(decode_polyline(step_geometry))

                elif isinstance(
                    step_geometry,
                    dict,
                ):

                    step_coordinates = step_geometry.get("coordinates")

                    if isinstance(
                        step_coordinates,
                        list,
                    ):

                        all_coordinates.extend(pairs_to_coordinates(step_coordinates))

                elif isinstance(
                    step_geometry,
                    list,
                ):

                    all_coordinates.extend(pairs_to_coordinates(step_geometry))

        if len(all_coordinates) >= 2:

            return all_coordinates

    return []


# =============================================================================
# Public Service Function
# =============================================================================


async def get_route_and_elevation(
    pickup: dict,
    dropoff: dict,
    client: httpx.AsyncClient,
) -> dict:
    """Get Baato road distance and cumulative road elevation.

    Flow:

        Pickup + Dropoff
              ↓
            Baato
              ↓
        Road distance
              ↓
        Road geometry
              ↓
      Dynamic downsampling
              ↓
       ~250 coordinates
              ↓
        Open-Meteo
              ↓
      Elevation profile
              ↓
    Cumulative uphill gain
    """

    route_info = await get_baato_route(
        pickup=pickup,
        dropoff=dropoff,
        client=client,
    )

    route = route_info["route"]

    coordinates = extract_route_coordinates(route)

    # -------------------------------------------------------------------------
    # No usable route geometry.
    #
    # We still return the Baato road distance because that part is valid.
    # Elevation is explicitly marked unavailable instead of pretending it
    # is zero.
    # -------------------------------------------------------------------------

    if not coordinates:

        return {
            "distance_in_meters": (route_info["distance_in_meters"]),
            "distance_km": (route_info["distance_km"]),
            "pickup_elevation_m": None,
            "dropoff_elevation_m": None,
            "elevation_gain_m": None,
            "elevation_loss_m": None,
            "net_elevation_change_m": None,
            "elevation_points_count": 0,
            "elevation_status": ("Route geometry unavailable"),
            "elevation_sampling": {
                "raw_route_points": 0,
                "sampled_points": 0,
                "target_points": (TARGET_ELEVATION_POINTS),
                "spacing_m": None,
            },
        }

    # -------------------------------------------------------------------------
    # Safety limit.
    # -------------------------------------------------------------------------

    raw_point_count = len(coordinates)

    if raw_point_count > MAX_ROUTE_COORDINATES:
        coordinates = coordinates[:MAX_ROUTE_COORDINATES]

    # -------------------------------------------------------------------------
    # Dynamic sampling.
    # -------------------------------------------------------------------------

    sampling_spacing_m = calculate_sampling_spacing_m(
        route_distance_m=(route_info["distance_in_meters"]),
        target_points=(TARGET_ELEVATION_POINTS),
    )

    sampled_coordinates = downsample_route(
        coordinates=coordinates,
        route_distance_m=(route_info["distance_in_meters"]),
        target_points=(TARGET_ELEVATION_POINTS),
    )

    sampled_point_count = len(sampled_coordinates)

    # -------------------------------------------------------------------------
    # Elevation service.
    # -------------------------------------------------------------------------

    elevation_info = await get_route_elevation(
        coordinates=sampled_coordinates,
        client=client,
    )

    return {
        "distance_in_meters": (route_info["distance_in_meters"]),
        "distance_km": (route_info["distance_km"]),
        "pickup_elevation_m": (elevation_info["pickup_elevation_m"]),
        "dropoff_elevation_m": (elevation_info["dropoff_elevation_m"]),
        "elevation_gain_m": (elevation_info["elevation_gain_m"]),
        "elevation_loss_m": (elevation_info["elevation_loss_m"]),
        "net_elevation_change_m": (elevation_info["net_elevation_change_m"]),
        "elevation_points_count": (elevation_info["elevation_points_count"]),
        "elevation_status": (elevation_info["elevation_status"]),
        "elevation_sampling": {
            "raw_route_points": (raw_point_count),
            "sampled_points": (sampled_point_count),
            "target_points": (TARGET_ELEVATION_POINTS),
            "spacing_m": round(
                sampling_spacing_m,
                2,
            ),
        },
    }
