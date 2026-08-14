const express = require("express");
const cors = require("cors");

const fareRoutes = require("./routes/fare_route");

const app = express();

app.use(cors());

// IMPORTANT: this must come before the routes
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get("/health", (req, res) => {
    res.json({
        success: true,
        message: "Fare Express server is running"
    });
});

app.get('/api/fare/estimate', async (req, res) => {
    try {
        // 1. Extract inputs from GET query parameters
        const {
            trip_type,
            base_fare,
            distance_km,
            per_km_rate,
            two_way_discount_percent
        } = req.query;

        // Optional: Validate that required params are present
        if (!trip_type || !base_fare || !distance_km || !per_km_rate || two_way_discount_percent === undefined) {
            return res.status(400).json({
                success: false,
                message: 'Missing required query parameters'
            });
        }
    } catch (error) {
        res.status(500).json({
            success: false,
            message: 'Internal server error'
        });
    }
});

// Temporary body test
app.post("/test-body", (req, res) => {
    console.log("REQUEST BODY:", req.body);

    res.json({
        success: true,
        received_body: req.body
    });
});

app.use("/api/v1/fare", fareRoutes);

module.exports = app;