const express = require("express");

const router = express.Router();


// POST /api/v1/fare/estimate
router.post("/estimate", async (req, res) => {

    const {
        vehicle_id,
        trip_type,
        base_fare,
        distance_km,
        per_km_rate,
        two_way_discount_percent
    } = req.body;


    // Validate trip type
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


    // Validate base fare
    if (base_fare == null || Number(base_fare) < 0) {
        return res.status(422).json({
            success: false,
            error: "base_fare must be a positive number"
        });
    }


    // Validate distance
    if (distance_km == null || Number(distance_km) <= 0) {
        return res.status(422).json({
            success: false,
            error: "distance_km must be greater than 0"
        });
    }


    // Validate per km rate
    if (per_km_rate == null || Number(per_km_rate) < 0) {
        return res.status(422).json({
            success: false,
            error: "per_km_rate must be a positive number"
        });
    }


    // Validate discount
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


    // Prepare data for Python
    const fareInput = {
        vehicle_id: vehicle_id || null,
        trip_type,
        base_fare: Number(base_fare),
        distance_km: Number(distance_km),
        per_km_rate: Number(per_km_rate),
        two_way_discount_percent: Number(two_way_discount_percent)
    };


    // Send data to Python
    try {

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


        const pythonData = await pythonResponse.json();


        // Return Python result to client
        return res
            .status(pythonResponse.status)
            .json(pythonData);


    } catch (error) {

        console.error("Python fare server error:", error);

        return res.status(500).json({
            success: false,
            error: "Unable to connect to Python fare server"
        });
    }
});


module.exports = router;