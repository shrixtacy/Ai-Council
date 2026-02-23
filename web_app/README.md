# AI Council Web Application

## 🚀 Quick Setup for Contributors

### 1. Install Dependencies
```bash
# Auth Backend
cd web_app/auth-backend
npm install

# React Frontend
cd web_app/frontend-react
npm install
```

### 2. Configure Environment

Create `.env` in `web_app/auth-backend/`:
```env
# ONLY thing you need to add:
MONGODB_URI=mongodb+srv://your-username:password@cluster.mongodb.net/

# Use this JWT secret (or generate your own):
JWT_SECRET=ai-council-super-secret-jwt-key-2026-production-grade

# ✅ EMAIL IS 100% CONFIGURED - DON'T ADD ANYTHING!
# All emails sent from: obstructgamer@gmail.com
# Email credentials are hardcoded in server.js
```

### 3. Start Everything
```bash
# Terminal 1: Auth Backend
cd web_app/auth-backend
npm start

# Terminal 2: React Frontend
cd web_app/frontend-react
npm start

# Terminal 3: AI Backend (Python)
cd web_app/backend
python main.py
```

### 4. Test
- Open http://localhost:3000
- Register with your email
- Check email for OTP (sent from obstructgamer@gmail.com)
- Verify and login!

## ✅ What You Get

- Full authentication with email OTP
- MongoDB auto-sync (no migrations needed)
- Real-time chat with AI orchestration
- Live orchestration visualization
- Analytics dashboard
- Chat history

## 📧 Email System

**Fully configured and hardcoded!**
- All OTP emails sent from: obstructgamer@gmail.com
- Email credentials hardcoded in `auth-backend/server.js`
- Contributors need ZERO email configuration
- No EMAIL_PASSWORD needed in .env

## 🗄️ MongoDB

**Auto-sync like Supabase!**
- Collections created automatically on first use
- No migration scripts needed
- Just add your MongoDB URI and it works

### Collections Created:
- `users` - User accounts with email verification
- `sessions` - Active sessions (7-day auto-expire)
- `chathistories` - Conversations with orchestration data

## 🏗️ Architecture

```
React Frontend (3000)
    ↓
Auth Backend (5000) ← Email: obstructgamer@gmail.com
    ↓
MongoDB Atlas ← Auto-Sync
    ↓
AI Backend (8000)
```

## 🔧 Configuration

### Required:
- `MONGODB_URI` - Your MongoDB connection string

### Already Configured:
- Email (hardcoded in server.js)
- JWT secret (example provided)
- All ports and URLs

## 🐛 Troubleshooting

**MongoDB connection fails:**
- Check your connection string
- Whitelist your IP in MongoDB Atlas

**Port already in use:**
```bash
# Change port in .env
PORT=5001
```

**Email not sending:**
- Should work automatically (hardcoded)
- Check server.js if issues persist

## 📚 API Endpoints

### Authentication
- `POST /api/auth/register` - Register with OTP
- `POST /api/auth/verify-otp` - Verify email
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

### Chat
- `POST /api/chat/save` - Save conversation
- `GET /api/chat/history` - Get history
- `GET /api/chat/analytics` - Get analytics

## 🎯 Features

- JWT authentication
- Email OTP verification
- Session management
- Chat with AI orchestration
- Live orchestration visualization
- Real-time analytics
- Chat history

---

## 📝 For Project Admins

### Email Configuration

Email is hardcoded in `auth-backend/server.js` (lines 27-46):
```javascript
process.env.EMAIL_USER = 'obstructgamer@gmail.com';
process.env.EMAIL_PASSWORD = 'ewyrxtlruykyfyda';
```

**To change:**
1. Edit `server.js` lines 41-42
2. Commit and push
3. All contributors get the update

### Security Notes

- Email password is a Gmail app-specific password
- Revocable anytime from Google Account
- Limited to SMTP sending only
- Safe for centralized email service

---

**Setup time: 2 minutes** ⚡
**Email setup: 0 (hardcoded)** ✅
**MongoDB setup: 0 (auto-sync)** ✅
