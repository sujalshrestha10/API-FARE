const express = require("express");
const cors = require("cors");

const fareRoutes = require("./routes/fare_route");

const app = express();

app.use(cors());

// IMPORTANT: this must come before the routes
app.use(express.json());
app.use(express.urlencoded({ extended: true }));


// Temporary body test
app.post("/test-body", (req, res) => {
    console.log("REQUEST BODY:", req.body);

    res.json({
        success: true,
        received_body: req.body
    });
});
app.get("/health",(req, res) => {
    res.json({
        success: true,
        message: "Fare Express server is running"
    });
});

app.use("/api/v1/fare", fareRoutes);

module.exports = app;