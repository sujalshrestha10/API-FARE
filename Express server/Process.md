1. Installed cors

cors controls whether a browser frontend is allowed to make requests to your Express server from a different origin.
For example:
Frontend
http://localhost:5173
       │
       │ request
       ▼
Express
http://localhost:3000
Those are different origins (5173 vs 3000), so browsers can block the request unless the Express server allows it.
With:

const cors = require("cors");
app.use(cors());
we allow cross-origin requests.

2. dotenv

We installed:
npm install dotenv
This lets Express load configuration from a .env file.
For example:
PORT=3000
PYTHON_FARE_URL=http://localhost:8000
Then:
require("dotenv").config();

const port = process.env.PORT || 3000;
Later we'll need this for things like:
PORT=3000
PYTHON_FARE_URL=http://localhost:8000
ROUTING_API_KEY=...
DATABASE_URL=...