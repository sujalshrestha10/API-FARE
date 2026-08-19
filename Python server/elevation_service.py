"""Elevation service using Open-Meteo.

This module:
- Fetches elevation for sampled road coordinates.
- Batches requests to avoid oversized API calls.
- Retries transient failures.
- Calculates cumulative uphill elevation gain.
- Calculates cumulative downhill elevation loss.
"""

import asyncio
import math
from typing import Any

import httpx
from fastapi import HTTPException

# =============================================================================
# Configuration
# =============================================================================

OPEN_METEO_URL = "https://api.open-meteo.com/v1/elevation"

# Open-Meteo accepts multiple coordinates in one request.
# Keep batches conservative for production.
OPEN_METEO_BATCH_SIZE = 100

OPEN_METEO_TIMEOUT_SECONDS = 15.0

OPEN_METEO_MAX_RETRIES = 3

# Delay between retries.
OPEN_METEO_RETRY_DELAYS = (
    0.5,
    1.5,
    3.0,
)


# =============================================================================
# Helpers
# =============================================================================


def is_valid_elevation(
    value: Any,
) -> bool:
    """Return True if value is a usable elevation number."""

    if value is None:
        return False

    try:
        numeric_value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return False

    return math.isfinite(numeric_value)


def chunk_coordinates(
    coordinates: list[tuple[float, float]],
    batch_size: int,
) -> list[list[tuple[float, float]]]:
    """Split coordinates into API-sized batches."""

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    return [
        coordinates[index : index + batch_size]
        for index in range(
            0,
            len(coordinates),
            batch_size,
        )
    ]


# =============================================================================
# Open-Meteo
# =============================================================================


async def fetch_elevation_batch(
    coordinates: list[tuple[float, float]],
    client: httpx.AsyncClient,
) -> list[float | None]:
    """Fetch elevation for one coordinate batch."""

    if not coordinates:
        return []

    latitudes = ",".join(f"{latitude:.6f}" for latitude, _ in coordinates)

    longitudes = ",".join(f"{longitude:.6f}" for _, longitude in coordinates)

    params: dict[str, str] = {
        "latitude": latitudes,
        "longitude": longitudes,
    }

    last_error: Exception | None = None

    for attempt in range(OPEN_METEO_MAX_RETRIES):

        try:
            response = await client.get(
                OPEN_METEO_URL,
                params=params,
                timeout=OPEN_METEO_TIMEOUT_SECONDS,
            )

            # Retry server-side errors.
            if response.status_code >= 500:

                raise httpx.HTTPStatusError(
                    ("Open-Meteo server error: " f"{response.status_code}"),
                    request=response.request,
                    response=response,
                )

            # Rate limiting.
            if response.status_code == 429:

                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    try:
                        delay = min(
                            float(retry_after),
                            10.0,
                        )
                    except ValueError:
                        delay = OPEN_METEO_RETRY_DELAYS[
                            min(
                                attempt,
                                len(OPEN_METEO_RETRY_DELAYS) - 1,
                            )
                        ]
                else:
                    delay = OPEN_METEO_RETRY_DELAYS[
                        min(
                            attempt,
                            len(OPEN_METEO_RETRY_DELAYS) - 1,
                        )
                    ]

                if attempt < (OPEN_METEO_MAX_RETRIES - 1):
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()

            response.raise_for_status()

            try:
                data = response.json()

            except ValueError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=("Open-Meteo returned " "invalid JSON."),
                ) from exc

            elevations = data.get("elevation")

            if not isinstance(
                elevations,
                list,
            ):
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Open-Meteo response " "does not contain " "elevation data."
                    ),
                )

            result: list[float | None] = []

            for elevation in elevations:

                if is_valid_elevation(elevation):
                    result.append(float(elevation))
                else:
                    result.append(None)

            # Open-Meteo should normally return one
            # elevation for every requested coordinate.
            #
            # If it doesn't, pad the response so
            # indexes remain aligned.
            if len(result) < len(coordinates):

                result.extend([None] * (len(coordinates) - len(result)))

            elif len(result) > len(coordinates):

                result = result[: len(coordinates)]

            return result

        except httpx.HTTPStatusError as exc:

            last_error = exc

            if attempt >= (OPEN_METEO_MAX_RETRIES - 1):
                break

            delay = OPEN_METEO_RETRY_DELAYS[
                min(
                    attempt,
                    len(OPEN_METEO_RETRY_DELAYS) - 1,
                )
            ]

            await asyncio.sleep(delay)

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as exc:

            last_error = exc

            if attempt >= (OPEN_METEO_MAX_RETRIES - 1):
                break

            delay = OPEN_METEO_RETRY_DELAYS[
                min(
                    attempt,
                    len(OPEN_METEO_RETRY_DELAYS) - 1,
                )
            ]

            await asyncio.sleep(delay)

        except httpx.HTTPError as exc:

            last_error = exc

            if attempt >= (OPEN_METEO_MAX_RETRIES - 1):
                break

            delay = OPEN_METEO_RETRY_DELAYS[
                min(
                    attempt,
                    len(OPEN_METEO_RETRY_DELAYS) - 1,
                )
            ]

            await asyncio.sleep(delay)

    error_message = "Open-Meteo elevation request failed after retries."

    if last_error is not None:
        error_message = f"{error_message} " f"{last_error}"

    raise HTTPException(
        status_code=502,
        detail=error_message,
    )


# =============================================================================
# Route Elevation
# =============================================================================


async def get_route_elevation(
    coordinates: list[tuple[float, float]],
    client: httpx.AsyncClient,
) -> dict:
    """Calculate cumulative elevation along a road route."""

    if not coordinates:
        return {
            "pickup_elevation_m": None,
            "dropoff_elevation_m": None,
            "elevation_gain_m": None,
            "elevation_loss_m": None,
            "net_elevation_change_m": None,
            "elevation_points_count": 0,
            "elevation_status": ("No route coordinates available"),
        }

    batches = chunk_coordinates(
        coordinates,
        OPEN_METEO_BATCH_SIZE,
    )

    all_elevations: list[float | None] = []

    # Sequential batches are intentional.
    #
    # This avoids hitting Open-Meteo with many
    # simultaneous requests and is much friendlier
    # to rate limits.
    for batch in batches:

        elevations = await fetch_elevation_batch(
            coordinates=batch,
            client=client,
        )

        all_elevations.extend(elevations)

    # -------------------------------------------------------------------------
    # Ensure we received usable data.
    # -------------------------------------------------------------------------

    valid_elevations = [
        elevation for elevation in all_elevations if elevation is not None
    ]

    if not valid_elevations:
        return {
            "pickup_elevation_m": None,
            "dropoff_elevation_m": None,
            "elevation_gain_m": None,
            "elevation_loss_m": None,
            "net_elevation_change_m": None,
            "elevation_points_count": 0,
            "elevation_status": ("Elevation API returned " "no usable data"),
        }

    # -------------------------------------------------------------------------
    # Remove leading/trailing missing values only.
    #
    # Internal missing points are handled by carrying
    # forward the previous known elevation.
    # -------------------------------------------------------------------------

    first_valid_index = None

    for index, elevation in enumerate(all_elevations):
        if elevation is not None:
            first_valid_index = index
            break

    last_valid_index = None

    for index in range(
        len(all_elevations) - 1,
        -1,
        -1,
    ):
        if all_elevations[index] is not None:
            last_valid_index = index
            break

    if first_valid_index is None or last_valid_index is None:
        return {
            "pickup_elevation_m": None,
            "dropoff_elevation_m": None,
            "elevation_gain_m": None,
            "elevation_loss_m": None,
            "net_elevation_change_m": None,
            "elevation_points_count": 0,
            "elevation_status": ("Elevation API returned " "incomplete data"),
        }

    usable_elevations = all_elevations[first_valid_index : last_valid_index + 1]

    # -------------------------------------------------------------------------
    # Fill internal missing values using the most
    # recent valid elevation.
    #
    # We do NOT invent a whole mountain profile.
    # We simply prevent one missing API point from
    # breaking the cumulative calculation.
    # -------------------------------------------------------------------------

    filled_elevations: list[float] = []

    previous_elevation: float | None = None

    for elevation in usable_elevations:

        if elevation is not None:
            previous_elevation = elevation

        if previous_elevation is not None:
            filled_elevations.append(previous_elevation)

    if len(filled_elevations) < 2:

        return {
            "pickup_elevation_m": (filled_elevations[0] if filled_elevations else None),
            "dropoff_elevation_m": (
                filled_elevations[-1] if filled_elevations else None
            ),
            "elevation_gain_m": 0.0,
            "elevation_loss_m": 0.0,
            "net_elevation_change_m": 0.0,
            "elevation_points_count": len(filled_elevations),
            "elevation_status": ("Insufficient elevation " "points"),
        }

    # -------------------------------------------------------------------------
    # Cumulative elevation calculation.
    #
    # Example:
    #
    # 200 -> 500 -> 300 -> 700 -> 400 -> 800
    #
    # Gain:
    #     +300 +400 +400 = 1100m
    #
    # Loss:
    #     200 +300 = 500m
    #
    # Net:
    #     800 - 200 = 600m
    #
    # This is what we want for a vehicle traveling
    # over mountainous roads.
    # -------------------------------------------------------------------------

    total_gain = 0.0
    total_loss = 0.0

    previous = filled_elevations[0]

    for current in filled_elevations[1:]:

        difference = current - previous

        if difference > 0:
            total_gain += difference

        elif difference < 0:
            total_loss += abs(difference)

        previous = current

    pickup_elevation = filled_elevations[0]

    dropoff_elevation = filled_elevations[-1]

    net_change = dropoff_elevation - pickup_elevation

    missing_count = sum(elevation is None for elevation in all_elevations)

    if missing_count == 0:
        elevation_status = "OK"

    else:
        elevation_status = "OK with " f"{missing_count} missing " "elevation points"

    return {
        "pickup_elevation_m": round(
            pickup_elevation,
            2,
        ),
        "dropoff_elevation_m": round(
            dropoff_elevation,
            2,
        ),
        "elevation_gain_m": round(
            total_gain,
            2,
        ),
        "elevation_loss_m": round(
            total_loss,
            2,
        ),
        "net_elevation_change_m": round(
            net_change,
            2,
        ),
        "elevation_points_count": len(filled_elevations),
        "elevation_status": elevation_status,
    }
