require("dotenv").config();
const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");

const app = express();

// Security middleware
app.use(helmet());
app.use(
  cors({
    origin: process.env.FRONTEND_URL || "http://localhost:3000",
    credentials: true,
  }),
);

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
});
app.use("/api/", limiter);

// Body parser
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Email configuration is read from environment variables (.env file).
// See .env.example for required variables: EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD

// MongoDB connection
mongoose
  .connect(process.env.MONGODB_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
  })
  .then(() => console.log("✅ MongoDB connected successfully"))
  .catch((err) => {
    console.error("❌ MongoDB connection error:", err);
    process.exit(1);
  });

// Routes
app.use("/api/auth", require("./routes/auth"));
app.use("/api/chat", require("./routes/chat"));

// Health check
app.get("/health", (req, res) => {
  res.json({
    success: true,
    message: "AI Council Auth Backend is running",
    email: {
      configured: !!process.env.EMAIL_PASSWORD,
      from: process.env.EMAIL_USER,
    },
    timestamp: new Date().toISOString(),
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    success: false,
    message: "Something went wrong!",
    error: process.env.NODE_ENV === "development" ? err.message : undefined,
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: "Route not found",
  });
});

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`🚀 Auth Backend running on port ${PORT}`);
  console.log(`📧 Email service: ${process.env.EMAIL_HOST}`);
  console.log(`📨 Emails will be sent from: ${process.env.EMAIL_USER}`);
  console.log(`🌍 Environment: ${process.env.NODE_ENV}`);
  if (!process.env.EMAIL_PASSWORD) {
    console.log(`⚠️  Email not configured - add EMAIL_PASSWORD to .env`);
  }
});
