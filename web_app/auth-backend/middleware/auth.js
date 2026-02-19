const jwt = require('jsonwebtoken');
const User = require('../models/User');
const Session = require('../models/Session');

const protect = async (req, res, next) => {
  try {
    let token;

    if (req.headers.authorization && req.headers.authorization.startsWith('Bearer')) {
      token = req.headers.authorization.split(' ')[1];
    }

    if (!token) {
      return res.status(401).json({ success: false, message: 'Not authorized to access this route' });
    }

    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      
      // Check if session is active
      const session = await Session.findOne({ token, isActive: true });
      if (!session) {
        return res.status(401).json({ success: false, message: 'Session expired or invalid' });
      }

      // Update last activity
      session.lastActivity = Date.now();
      await session.save();

      // Get user
      req.user = await User.findById(decoded.id).select('-password');
      
      if (!req.user) {
        return res.status(401).json({ success: false, message: 'User not found' });
      }

      if (!req.user.isVerified) {
        return res.status(403).json({ success: false, message: 'Please verify your email first' });
      }

      next();
    } catch (err) {
      return res.status(401).json({ success: false, message: 'Token is invalid or expired' });
    }
  } catch (error) {
    res.status(500).json({ success: false, message: 'Server error' });
  }
};

module.exports = { protect };
