

require("dotenv").config();

const app = require("./app");

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`Fare Express server running on port ${PORT}`);
    console.log(`Click here to open: http://localhost:${PORT}`);
});