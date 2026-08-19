"""Fare calculation helper module.

Calculates:
- Base fare
- Road-distance fare
- Cumulative elevation fare
- Two-way distance
- Two-way discount
- Final fare
"""


def calculate_fare(
    trip_type: str,
    base_fare: float,
    distance_km: float,
    per_km_rate: float,
    two_way_discount_percent: float,
    elevation_gain_m: float = 0.0,
    elevation_loss_m: float = 0.0,
    elevation_rate_per_meter: float = 0.0,
) -> dict:
    """Calculate the final vehicle trip fare.

    Elevation charging is based on cumulative uphill
    elevation gain, NOT net elevation change.

    Example:

        200m -> 500m -> 300m -> 700m

    Elevation gain:

        +300m +400m = 700m

    The 200m downhill section is not charged.

    For TWO_WAY trips, the road distance is doubled.
    The elevation gain is also doubled because the
    vehicle travels the same road in the opposite
    direction.

    The two-way discount is applied to the subtotal.
    """

    # -------------------------------------------------------------------------
    # Validate trip type
    # -------------------------------------------------------------------------

    if trip_type not in {
        "ONE_WAY",
        "TWO_WAY",
    }:

        raise ValueError("trip_type must be ONE_WAY or TWO_WAY")

    # -------------------------------------------------------------------------
    # Normalize numeric values
    # -------------------------------------------------------------------------

    base_fare = float(base_fare)

    distance_km = float(distance_km)

    per_km_rate = float(per_km_rate)

    two_way_discount_percent = float(two_way_discount_percent)

    elevation_gain_m = max(
        0.0,
        float(elevation_gain_m),
    )

    elevation_loss_m = max(
        0.0,
        float(elevation_loss_m),
    )

    elevation_rate_per_meter = max(
        0.0,
        float(elevation_rate_per_meter),
    )

    # -------------------------------------------------------------------------
    # Distance
    # -------------------------------------------------------------------------

    if trip_type == "ONE_WAY":

        charged_distance_km = distance_km

        charged_elevation_gain_m = elevation_gain_m

    else:

        charged_distance_km = distance_km * 2

        # For a round trip, the vehicle traverses
        # the same route in reverse.
        #
        # Therefore the uphill portions of the
        # return trip equal the original route's
        # downhill portions.
        #
        # Total round-trip uphill gain is therefore:
        #
        #     one-way gain + one-way loss
        #
        # This is more accurate than simply multiplying
        # one-way gain by 2.
        charged_elevation_gain_m = elevation_gain_m + elevation_loss_m

    # -------------------------------------------------------------------------
    # Distance fare
    # -------------------------------------------------------------------------

    distance_charge = charged_distance_km * per_km_rate

    # -------------------------------------------------------------------------
    # Elevation fare
    # -------------------------------------------------------------------------

    elevation_charge = charged_elevation_gain_m * elevation_rate_per_meter

    # -------------------------------------------------------------------------
    # Subtotal
    # -------------------------------------------------------------------------

    subtotal = base_fare + distance_charge + elevation_charge

    # -------------------------------------------------------------------------
    # Two-way discount
    # -------------------------------------------------------------------------

    discount_amount = 0.0

    if trip_type == "TWO_WAY" and two_way_discount_percent > 0:
        discount_amount = subtotal * two_way_discount_percent / 100.0

    # -------------------------------------------------------------------------
    # Final fare
    # -------------------------------------------------------------------------

    final_fare = subtotal - discount_amount

    # -------------------------------------------------------------------------
    # Response
    # -------------------------------------------------------------------------

    return {
        "trip_type": trip_type,
        "charge_one_way_distance_km": round(
            distance_km,
            2,
        ),
        "charge_two_way_distance_km": round(
            charged_distance_km,
            2,
        ),
        "base_fare": round(
            base_fare,
            2,
        ),
        "per_km_rate": round(
            per_km_rate,
            2,
        ),
        "distance_charge": round(
            distance_charge,
            2,
        ),
        "elevation_gain_m": round(
            elevation_gain_m,
            2,
        ),
        "elevation_loss_m": round(
            elevation_loss_m,
            2,
        ),
        "charged_elevation_gain_m": round(
            charged_elevation_gain_m,
            2,
        ),
        "elevation_rate_per_meter": round(
            elevation_rate_per_meter,
            4,
        ),
        "elevation_charge": round(
            elevation_charge,
            2,
        ),
        "subtotal": round(
            subtotal,
            2,
        ),
        "discount_amount": round(
            discount_amount,
            2,
        ),
        "final_fare": round(
            final_fare,
            2,
        ),
    }
