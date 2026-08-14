# Fare Estimation System

## 1. Goal

Build a fare estimation system with two separate backend services:

1. **Express.js Server**

   * Receives fare-related inputs.
   * Validates the inputs.
   * Later communicates with the existing project/backend.
   * Later obtains actual road distance from a routing service.
   * Sends calculation data to the Python server.
   * Returns the calculated fare to the client.

2. **Python/FastAPI Server**

   * Acts as the fare calculation engine.
   * Receives validated raw fare data from Express.
   * Performs all fare calculations.
   * Handles one-way and two-way pricing.
   * Returns the calculation breakdown and final estimated fare.
   * Initially does not connect to the database.

---

# 2. Existing Database

The project already has a PostgreSQL/PostGIS database.

Existing important tables:

* `users`
* `vehicles`

The fare estimation system will eventually use data from the existing project/database.

**We will NOT create a second database for the fare system.**

Initially, the fare calculator will work entirely with data supplied by Express.

---

# 3. Initial Architecture

```text
Client
   │
   ▼
Express.js
   │
   │ Fare input
   ▼
Python / FastAPI
   │
   │ Calculated fare
   ▼
Express.js
   │
   ▼
Client
```

The database is not involved in the initial fare calculation test.

---

# 4. Express Server

## Responsibility

Express is responsible for receiving and preparing the information required by the fare engine.

Initial endpoint:

```text
POST /api/v1/fare/estimate
```

## Initial Inputs

Express will receive:

```text
trip_type
base_fare
distance_km
per_km_rate
two_way_discount_percent
```

Example:

```json
{
  "trip_type": "TWO_WAY",
  "base_fare": 5000,
  "distance_km": 200,
  "per_km_rate": 30,
  "two_way_discount_percent": 20
}
```

---

# 5. Distance

The fare system must use **actual road distance**.

It must NOT use:

* straight-line distance
* Haversine distance
* simple latitude/longitude distance

Example:

```text
Kathmandu → Pokhara

Straight-line distance ≠ actual driving distance
```

The actual road distance will eventually come from a routing/map service.

For the initial development stage, Express will simply receive:

```text
distance_km
```

as raw input.

Later:

```text
Pickup coordinates
       +
Destination coordinates
       ↓
Routing service
       ↓
Actual road distance
       ↓
Express
       ↓
Python fare engine
```

---

# 6. Trip Types

The system initially supports two trip types:

```text
ONE_WAY
TWO_WAY
```

## ONE_WAY

The customer travels from the pickup location to the destination.

Example:

```text
Kathmandu → Pokhara
```

If road distance is 200 km:

```text
Trip distance = 200 km
```

## TWO_WAY

The customer travels to the destination and returns.

Example:

```text
Kathmandu → Pokhara → Kathmandu
```

If the one-way road distance is 200 km:

```text
Total travel distance = 400 km
```

Python will handle this calculation.

---

# 7. Two-Way Pricing

Two-way trips should be comparatively cheaper than paying the equivalent one-way rate twice.

The initial system will support:

```text
two_way_discount_percent
```

Example:

```text
One-way distance = 200 km
Per-km rate = Rs. 30

Two-way distance = 400 km

Raw distance fare:
400 × 30
= Rs. 12,000
```

If the two-way discount is 20%:

```text
Discount:
12,000 × 20%
= Rs. 2,400
```

The final calculation will be handled by Python.

**The exact business pricing formula will be finalized before production integration.**

---

# 8. Python Fare Engine

Python/FastAPI will be responsible for calculations.

Initial endpoint:

```text
POST /api/v1/fare/estimate
```

Python receives raw validated data from Express.

It will eventually calculate:

```text
Base fare
+
Distance fare
+
Additional charges
-
Applicable discounts
=
Final fare
```

---

# 9. Initial Python Response

The Python server should return a calculation breakdown rather than only one number.

Example:

```json
{
  "trip_type": "TWO_WAY",
  "distance_km": 400,
  "base_fare": 5000,
  "distance_fare": 12000,
  "discount": 2400,
  "additional_charges": 0,
  "total_fare": 14600
}
```

The exact response structure may change as the pricing rules are finalized.

---

# 10. Future Inputs

The fare engine may eventually support:

```text
driver_charge
toll_charge
parking_charge
waiting_charge
extra_charge
tax
```

These will not necessarily be implemented in the first version.

---

# 11. Future Integration With Existing Project

Once the fare engine works independently, Express will connect it to the existing vehicle-rental project.

Eventually Express may obtain information such as:

```text
vehicle.daily_rate
vehicle.vehicle_category
vehicle.vehicle_type
vehicle.fuel_type
vehicle.rental_type
vehicle.seats
```

and route information such as:

```text
pickup location
destination location
actual road distance
```

Then Express will send the required information to Python.

---

# 12. Service Responsibilities

## Express

```text
API
Authentication
Validation
Existing project integration
Database access
Vehicle information
Booking information
Routing service integration
Communication with Python
```

## Python

```text
Fare calculation
One-way calculation
Two-way calculation
Discount calculation
Additional charges
Fare breakdown
Final estimated fare
```

## PostgreSQL/PostGIS

```text
Existing application data
Users
Vehicles
Locations
Bookings
Other project data
```

---

# 13. Development Strategy

We will build the system in stages.

## Stage 1 — Express

Build the Express server from scratch.

Create:

```text
POST /api/v1/fare/estimate
```

Accept raw fare inputs.

No database connection required.

No Python connection required.

---

## Stage 2 — Python

Build the Python/FastAPI fare calculation server independently.

Create:

```text
POST /api/v1/fare/estimate
```

Test the calculation using raw JSON.

---

## Stage 3 — Connect Express + Python

```text
Express
   │
   │ HTTP request
   ▼
Python
   │
   │ calculation result
   ▼
Express
```

---

## Stage 4 — Add Real Road Distance

Connect Express to a routing service.

```text
Pickup
Destination
    ↓
Routing API
    ↓
Actual road distance
```

---

## Stage 5 — Connect Existing Project

Use the existing PostgreSQL/PostGIS database and vehicle data.

---

## Stage 6 — Production Pricing Rules

Finalize:

* vehicle-specific pricing
* daily pricing
* per-km pricing
* two-way discounts
* driver charges
* tolls
* parking
* waiting
* taxes
* minimum fares
* additional charges
* future promotional discounts

---

# 14. Current Scope

### We are currently building only:

```text
Express raw input API
        ↓
Python fare calculation API
```

### We are NOT currently building:

```text
Database integration
Authentication
Booking system
Payment system
Routing integration
Production pricing rules
```

These will be added later.

---

# 15. Core Principle

Keep the Python service as a **stateless fare calculation engine**.

Express provides the facts.

Python performs the mathematics.

The existing application/database remains responsible for application data.

```text
EXPRESS = DATA + ORCHESTRATION

PYTHON = CALCULATION

DATABASE = EXISTING APPLICATION DATA
```
