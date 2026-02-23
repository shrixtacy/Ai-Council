const express = require('express');
const router = express.Router();
const crypto = require('crypto');
const { body, validationResult } = require('express-validator');
const jwt = require('jsonwebtoken');
const User = require('../models/User');
const Session = require('../models/Session');
const PasswordReset = require('../models/PasswordReset');
const RateLimit = require('../models/RateLimit');
const { sendOTPEmail, sendPasswordResetEmail, sendPasswordResetConfirmation } = require('../utils/email');
const { protect } = require('../middleware/auth');

// Password strength validation helper
const validatePasswordStrength = (password) => {
  const errors = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

// Generate OTP (cryptographically secure)
const generateOTP = () => {
  // Use crypto.randomInt for cryptographically secure random numbers
  return crypto.randomInt(100000, 1000000).toString();
};

// Generate JWT Token
const generateToken = (id) => {
  return jwt.sign({ id }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRE
  });
};

// @route   POST /api/auth/register
// @desc    Register user and send OTP
// @access  Public
router.post('/register', [
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 6 }),
  body('name').trim().notEmpty()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ success: false, errors: errors.array() });
    }

    const { email, password, name } = req.body;

    // Check if user exists
    let user = await User.findOne({ email }).exec();
    if (user && user.isVerified) {
      return res.status(400).json({ success: false, message: 'User already exists' });
    }

    // Generate OTP
    const otp = generateOTP();
    const otpExpires = new Date(Date.now() + (process.env.OTP_EXPIRE_MINUTES || 10) * 60 * 1000);

    if (user && !user.isVerified) {
      // Update existing unverified user
      user.password = password;
      user.name = name;
      user.otp = { code: otp, expiresAt: otpExpires };
      await user.save();
    } else {
      // Create new user
      user = await User.create({
        email,
        password,
        name,
        otp: { code: otp, expiresAt: otpExpires }
      });
    }

    // Send OTP email
    await sendOTPEmail(email, otp, name);

    res.status(201).json({
      success: true,
      message: 'Registration successful. Please check your email for OTP.',
      userId: user._id
    });
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ success: false, message: 'Server error during registration' });
  }
});

// @route   POST /api/auth/verify-otp
// @desc    Verify OTP and complete registration
// @access  Public
router.post('/verify-otp', [
  body('userId').notEmpty(),
  body('otp').isLength({ min: 6, max: 6 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ success: false, errors: errors.array() });
    }

    const { userId, otp } = req.body;

    const user = await User.findById(userId).exec();
    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found' });
    }

    if (user.isVerified) {
      return res.status(400).json({ success: false, message: 'User already verified' });
    }

    // Check OTP
    if (!user.otp || user.otp.code !== otp) {
      return res.status(400).json({ success: false, message: 'Invalid OTP' });
    }

    if (new Date() > user.otp.expiresAt) {
      return res.status(400).json({ success: false, message: 'OTP expired' });
    }

    // Verify user
    user.isVerified = true;
    user.otp = undefined;
    user.lastLogin = Date.now();
    await user.save();

    // Generate token
    const token = generateToken(user._id);

    // Create session
    await Session.create({
      userId: user._id,
      token,
      ipAddress: req.ip,
      userAgent: req.headers['user-agent']
    });

    res.json({
      success: true,
      message: 'Email verified successfully',
      token,
      user: {
        id: user._id,
        email: user.email,
        name: user.name
      }
    });
  } catch (error) {
    console.error('OTP verification error:', error);
    res.status(500).json({ success: false, message: 'Server error during verification' });
  }
});

// @route   POST /api/auth/resend-otp
// @desc    Resend OTP
// @access  Public
router.post('/resend-otp', [
  body('userId').notEmpty()
], async (req, res) => {
  try {
    const { userId } = req.body;

    const user = await User.findById(userId).exec();
    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found' });
    }

    if (user.isVerified) {
      return res.status(400).json({ success: false, message: 'User already verified' });
    }

    // Generate new OTP
    const otp = generateOTP();
    const otpExpires = new Date(Date.now() + (process.env.OTP_EXPIRE_MINUTES || 10) * 60 * 1000);

    user.otp = { code: otp, expiresAt: otpExpires };
    await user.save();

    // Send OTP email
    await sendOTPEmail(user.email, otp, user.name);

    res.json({
      success: true,
      message: 'OTP resent successfully'
    });
  } catch (error) {
    console.error('Resend OTP error:', error);
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

// @route   POST /api/auth/login
// @desc    Login user
// @access  Public
router.post('/login', [
  body('email').isEmail().normalizeEmail(),
  body('password').notEmpty()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ success: false, errors: errors.array() });
    }

    const { email, password } = req.body;

    // Check user exists
    const user = await User.findOne({ email }).exec();
    if (!user) {
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }

    if (!user.isVerified) {
      return res.status(403).json({ 
        success: false, 
        message: 'Please verify your email first',
        userId: user._id,
        needsVerification: true
      });
    }

    // Check password
    const isMatch = await user.comparePassword(password);
    if (!isMatch) {
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }

    // Update last login
    user.lastLogin = Date.now();
    await user.save();

    // Generate token
    const token = generateToken(user._id);

    // Create session
    await Session.create({
      userId: user._id,
      token,
      ipAddress: req.ip,
      userAgent: req.headers['user-agent']
    });

    res.json({
      success: true,
      token,
      user: {
        id: user._id,
        email: user.email,
        name: user.name
      }
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ success: false, message: 'Server error during login' });
  }
});

// @route   POST /api/auth/logout
// @desc    Logout user
// @access  Private
router.post('/logout', protect, async (req, res) => {
  try {
    const token = req.headers.authorization.split(' ')[1];
    await Session.findOneAndUpdate({ token }, { isActive: false }).exec();

    res.json({ success: true, message: 'Logged out successfully' });
  } catch (error) {
    console.error('Logout error:', error);
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

// @route   GET /api/auth/me
// @desc    Get current user
// @access  Private
router.get('/me', protect, async (req, res) => {
  res.json({
    success: true,
    user: {
      id: req.user._id,
      email: req.user.email,
      name: req.user.name,
      createdAt: req.user.createdAt,
      lastLogin: req.user.lastLogin
    }
  });
});

// @route   POST /api/auth/forgot-password
// @desc    Request password reset
// @access  Public
router.post('/forgot-password', [
  body('email').isEmail().normalizeEmail()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ success: false, errors: errors.array() });
    }

    const { email } = req.body;
    const ipAddress = req.ip || req.socket.remoteAddress;
    const userAgent = req.headers['user-agent'];

    // Check rate limit (max 3 per hour per email)
    const rateCheck = await RateLimit.checkRateLimit(email, 'forgot-password', 3, 3600000);
    if (!rateCheck.allowed) {
      console.log(`[SECURITY] Rate limit exceeded for password reset: ${email} from IP: ${ipAddress}`);
      // Still return success message to not reveal rate limiting
      return res.json({
        success: true,
        message: 'If an account exists with this email, you will receive a password reset link.'
      });
    }

    // Log the attempt for security monitoring
    await RateLimit.logAttempt(email, 'forgot-password', ipAddress, userAgent);
    console.log(`[SECURITY] Password reset requested for: ${email} from IP: ${ipAddress}`);

    // Find user by email
    const user = await User.findOne({ email });
    if (!user) {
      // Don't reveal if user exists or not for security
      return res.json({
        success: true,
        message: 'If an account exists with this email, you will receive a password reset link.'
      });
    }

    // Delete any existing reset tokens for this user
    await PasswordReset.deleteMany({ userId: user._id });

    // Generate reset token
    const resetToken = PasswordReset.generateToken();
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

    // Save token to database
    await PasswordReset.create({
      userId: user._id,
      token: resetToken,
      expiresAt
    });

    // Create reset URL
    const resetUrl = `${process.env.FRONTEND_URL || 'http://localhost:3000'}/reset-password/${resetToken}`;

    // Send email - wrap in try-catch to prevent account enumeration via error responses
    try {
      await sendPasswordResetEmail(email, resetUrl, user.name);
    } catch (emailError) {
      console.error('Failed to send password reset email:', emailError);
      // Don't change response - prevents account enumeration
    }

    res.json({
      success: true,
      message: 'If an account exists with this email, you will receive a password reset link.'
    });
  } catch (error) {
    console.error('Forgot password error:', error);
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

// @route   GET /api/auth/verify-reset-token/:token
// @desc    Verify if reset token is valid
// @access  Public
router.get('/verify-reset-token/:token', async (req, res) => {
  try {
    const { token } = req.params;

    const resetRecord = await PasswordReset.findValidToken(token);
    if (!resetRecord) {
      return res.status(400).json({
        success: false,
        message: 'Invalid or expired reset token'
      });
    }

    // Return expiry time for countdown timer
    res.json({
      success: true,
      message: 'Token is valid',
      expiresAt: resetRecord.expiresAt
    });
  } catch (error) {
    console.error('Verify reset token error:', error);
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

// @route   POST /api/auth/reset-password
// @desc    Reset password with token
// @access  Public
router.post('/reset-password', [
  body('token').notEmpty(),
  body('password').isLength({ min: 8 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ success: false, errors: errors.array() });
    }

    const { token, password } = req.body;
    const ipAddress = req.ip || req.socket?.remoteAddress || (req.headers['x-forwarded-for'] ? req.headers['x-forwarded-for'].split(',')[0].trim() : undefined);

    // Validate password strength
    const passwordValidation = validatePasswordStrength(password);
    if (!passwordValidation.isValid) {
      return res.status(400).json({
        success: false,
        message: 'Password does not meet strength requirements',
        errors: passwordValidation.errors
      });
    }

    // Find valid reset token
    const resetRecord = await PasswordReset.findValidToken(token);
    if (!resetRecord) {
      console.log(`[SECURITY] Invalid/expired password reset token attempted from IP: ${ipAddress}`);
      return res.status(400).json({
        success: false,
        message: 'Invalid or expired reset token'
      });
    }

    // Get the user
    const user = resetRecord.userId;
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found'
      });
    }

    // Update password
    user.password = password;
    await user.save();

    // Mark token as used
    resetRecord.used = true;
    await resetRecord.save();

    // Invalidate all existing sessions for security
    await Session.updateMany({ userId: user._id }, { isActive: false });

    // Log successful password reset
    console.log(`[SECURITY] Password successfully reset for user: ${user.email} from IP: ${ipAddress}`);

    // Send confirmation email
    try {
      await sendPasswordResetConfirmation(user.email, user.name);
    } catch (emailError) {
      console.error('Failed to send password reset confirmation email:', emailError);
      // Don't fail the request if confirmation email fails
    }

    res.json({
      success: true,
      message: 'Password reset successful. Please login with your new password.'
    });
  } catch (error) {
    console.error('Reset password error:', error);
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

module.exports = router;
