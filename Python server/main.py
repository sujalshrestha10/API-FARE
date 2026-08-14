from fastapi import FastAPI
from fare_calculator import calculate_fare
app = FastAPI()


@app.get("/health")
def health():
    return {
        "success": True,
        "message": "Python fare server is running"
    }


@app.get("/api/v1/fare/estimate")
def get_fare_estimate():
    return {
        "success": True,
        "message": "Python fare estimate GET endpoint is working"
    }


@app.post("/api/v1/fare/estimate")
def estimate_fare(data: dict):

    result = calculate_fare(
        trip_type=data["trip_type"],
        base_fare=float(data["base_fare"]),
        distance_km=float(data["distance_km"]),
        per_km_rate=float(data["per_km_rate"]),
        two_way_discount_percent=float(
            data["two_way_discount_percent"]
        )
    )

    return {
        "success": True,
        "data": result
    }