const express = require("express");
const router = express.Router();
// =====================================================
// TEST BAATO DIRECTIONS
// GET /api/v1/fare/test-baato
// =====================================================
router.get("/test-baato", async (req, res) => {
    try {
        const pickup = "27.7172,85.3240";
        const dropoff = "27.6710,85.4298";
        // Build Baato URL
        const baatoUrl = new URL(
            "https://api.baato.io/api/v1/directions"
        );
        // Baato API key
        baatoUrl.searchParams.set(
            "key",
            process.env.BAATO_API_KEY
        );
        // Pickup
        baatoUrl.searchParams.append(
            "points[]",
            pickup
        );
        // Dropoff
        baatoUrl.searchParams.append(
            "points[]",
            dropoff
        );
        // Vehicle
        baatoUrl.searchParams.set(
            "mode",
            "car"
        );
        // Call Baato
        const baatoResponse = await fetch(
            baatoUrl.toString()
        );
        const baatoData = await baatoResponse.json();
        console.log(
            "BAATO STATUS:",
            baatoResponse.status
        );
        console.log(
            "BAATO RESPONSE:",
            baatoData
        );
        // Check Baato response
        if (!baatoResponse.ok) {
            return res.status(502).json({
                success: false,
                error: "Baato request failed",
                baato: baatoData
            });
        }
        // Get road distance
        const distanceInMeters =
            baatoData.data[0].distanceInMeters;
        const distanceKm =
            Number(
                (distanceInMeters / 1000).toFixed(2)
            );
        return res.json({
            success: true,
            distanceInMeters: distanceInMeters,
            distanceKm: distanceKm
        });
    } catch (error) {
        console.error(
            "BAATO ERROR:",
            error
        );
        return res.status(500).json({
            success: false,
            error: "Unable to connect to Baato"
        });
    }
});
// =====================================================
// FARE ESTIMATE
// POST /api/v1/fare/estimate
// =====================================================
router.post("/estimate", async (req, res) => {
    const {
        vehicle_id,
        trip_type,
        base_fare,
        pickup,
        dropoff,
        per_km_rate,
        two_way_discount_percent
    } = req.body;
    // =================================================
    // Validate pickup/dropoff
    // =================================================
    if (
        !pickup ||
        pickup.latitude == null ||
        pickup.longitude == null ||
        !dropoff ||
        dropoff.latitude == null ||
        dropoff.longitude == null
    ) {
        return res.status(422).json({
            success: false,
            error: "Valid pickup and dropoff coordinates are required"
        });
    }
    // =================================================
    // Validate trip type
    // =================================================
    if (!trip_type) {
        return res.status(422).json({
            success: false,
            error: "trip_type is required"
        });
    }
    if (!["ONE_WAY", "TWO_WAY"].includes(trip_type)) {
        return res.status(422).json({
            success: false,
            error: "trip_type must be ONE_WAY or TWO_WAY"
        });
    }
    // =================================================
    // Validate base fare
    // =================================================
    if (
        base_fare == null ||
        Number(base_fare) < 0
    ) {
        return res.status(422).json({
            success: false,
            error: "base_fare must be a positive number"
        });
    }
    // =================================================
    // Validate per km rate
    // =================================================
    if (
        per_km_rate == null ||
        Number(per_km_rate) < 0
    ) {
        return res.status(422).json({
            success: false,
            error: "per_km_rate must be a positive number"
        });
    }
    // =================================================
    // Validate discount
    // =================================================
    if (
        two_way_discount_percent == null ||
        Number(two_way_discount_percent) < 0 ||
        Number(two_way_discount_percent) > 100
    ) {
        return res.status(422).json({
            success: false,
            error: "two_way_discount_percent must be between 0 and 100"
        });
    }
    try {
        // =================================================
        // 1. Ask Baato for actual ROAD distance
        // =================================================
        // =================================================
        // Baato error
        // =================================================
        // =================================================
        // 3. Prepare data for Python
        // =================================================
        const fareInput = {
            vehicle_id: vehicle_id || null,
            trip_type,
            base_fare: Number(base_fare),
            pickup,
            dropoff,
            per_km_rate: Number(per_km_rate),
            two_way_discount_percent:
                Number(two_way_discount_percent)
        };
        console.log(
            "Sending to Python:",
            fareInput
        );
        // =================================================
        // 4. Send data to Python
        // =================================================
        const pythonResponse = await fetch(
            "http://localhost:8000/api/v1/fare/estimate",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(fareInput)
            }
        );
        const pythonData =
            await pythonResponse.json();
        // =================================================
        // 5. Return Python result to frontend
        // =================================================
        return res
            .status(pythonResponse.status)
            .json(pythonData);
    } catch (error) {
        console.error(
            "Fare calculation error:",
            error
        );
        return res.status(500).json({
            success: false,
            error: "Unable to calculate fare"
        });
    }
});
module.exports = router;