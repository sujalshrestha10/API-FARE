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
    "charge_one_way_distance_km": round(distance_km, 2),
    "charge_two_way_distance_km": round(distance, 2),
    "base_fare": round(base_fare, 2),
    "distance_charge": round(distance_charge, 2),
    "subtotal": round(subtotal, 2),
    "discount_amount": round(discount_amount, 2),
    "final_fare": round(final_fare, 2)
}