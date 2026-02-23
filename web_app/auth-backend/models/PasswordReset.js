const mongoose = require('mongoose');
const crypto = require('crypto');

const passwordResetSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
    ref: 'User'
  },
  token: {
    type: String,
    required: true
  },
  expiresAt: {
    type: Date,
    required: true
  },
  used: {
    type: Boolean,
    default: false
  },
  createdAt: {
    type: Date,
    default: Date.now,
    expires: 3600 // Auto-delete after 1 hour
  }
});

// Generate a secure random token
passwordResetSchema.statics.generateToken = function() {
  return crypto.randomBytes(32).toString('hex');
};

// Hash the token before saving
passwordResetSchema.pre('save', function(next) {
  if (!this.isModified('token')) return next();
  this.token = crypto.createHash('sha256').update(this.token).digest('hex');
  next();
});

// Static method to find valid reset token
passwordResetSchema.statics.findValidToken = async function(token) {
  const hashedToken = crypto.createHash('sha256').update(token).digest('hex');
  return this.findOne({
    token: hashedToken,
    expiresAt: { $gt: Date.now() },
    used: false
  }).populate('userId');
};

module.exports = mongoose.model('PasswordReset', passwordResetSchema);
