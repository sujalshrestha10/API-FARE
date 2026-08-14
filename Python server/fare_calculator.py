def calculate_fare(
    trip_type,
    base_fare,
    distance_km,
    per_km_rate,
    two_way_discount_percent
):
    # Calculate the distance charge
    if trip_type == "ONE_WAY":
        distance = distance_km

    elif trip_type == "TWO_WAY":
        distance = distance_km * 2

    else:
        raise ValueError("trip_type must be ONE_WAY or TWO_WAY")

    distance_charge = distance * per_km_rate

    # Add base fare
    subtotal = base_fare + distance_charge

    # Apply discount only for TWO_WAY
    if trip_type == "TWO_WAY":
        discount_amount = (
            subtotal * two_way_discount_percent / 100
        )
    else:
        discount_amount = 0

    final_fare = subtotal - discount_amount

    return {
        "trip_type": trip_type,
        "charge_one_way_distance_km": distance_km,
        "charge_two_way_distance_km": distance,
        "base_fare": base_fare,
        "distance_charge": distance_charge,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "final_fare": final_fare
    }