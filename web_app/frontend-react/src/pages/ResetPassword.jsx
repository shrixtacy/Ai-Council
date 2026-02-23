import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, ArrowLeft, Brain, KeyRound, CheckCircle, AlertCircle, Eye, EyeOff, Clock, Shield, Check, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../utils/api';

// Password strength calculator
const calculatePasswordStrength = (password) => {
  let score = 0;
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
  };

  Object.values(checks).forEach(passed => {
    if (passed) score += 20;
  });

  let label = 'Very Weak';
  let color = 'bg-red-500';

  if (score >= 100) {
    label = 'Strong';
    color = 'bg-green-500';
  } else if (score >= 80) {
    label = 'Good';
    color = 'bg-blue-500';
  } else if (score >= 60) {
    label = 'Fair';
    color = 'bg-yellow-500';
  } else if (score >= 40) {
    label = 'Weak';
    color = 'bg-orange-500';
  }

  return { score, label, color, checks };
};

// Countdown timer component
const CountdownTimer = ({ expiresAt }) => {
  const [timeLeft, setTimeLeft] = useState('');
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    const calculateTimeLeft = () => {
      const now = new Date().getTime();
      const expiry = new Date(expiresAt).getTime();
      const difference = expiry - now;

      if (difference <= 0) {
        setIsExpired(true);
        setTimeLeft('Expired');
        return;
      }

      const minutes = Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((difference % (1000 * 60)) / 1000);
      setTimeLeft(`${minutes}m ${seconds}s`);
    };

    calculateTimeLeft();
    const timer = setInterval(calculateTimeLeft, 1000);

    return () => clearInterval(timer);
  }, [expiresAt]);

  return (
    <div className={`flex items-center gap-2 text-sm ${isExpired ? 'text-red-600' : 'text-gray-600'}`}>
      <Clock className="w-4 h-4" />
      <span>Link expires in: <strong>{timeLeft}</strong></span>
    </div>
  );
};

// Success animation component
const SuccessAnimation = () => (
  <motion.div
    initial={{ scale: 0 }}
    animate={{ scale: 1 }}
    transition={{ type: 'spring', stiffness: 200, damping: 15 }}
    className="text-center py-6"
  >
    <motion.div
      initial={{ scale: 0, rotate: -180 }}
      animate={{ scale: 1, rotate: 0 }}
      transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.1 }}
      className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-4"
    >
      <motion.div
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.5, delay: 0.3 }}
      >
        <CheckCircle className="w-10 h-10 text-green-600" />
      </motion.div>
    </motion.div>
    <motion.h2
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="text-2xl font-bold text-gray-800 mb-2"
    >
      Password Reset!
    </motion.h2>
    <motion.p
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5 }}
      className="text-gray-600 mb-4"
    >
      Your password has been successfully reset.
    </motion.p>
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.6 }}
      className="flex items-center justify-center gap-2 text-green-600"
    >
      <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
      <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
      <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
      <span className="ml-2 text-sm">Redirecting to login...</span>
    </motion.div>
  </motion.div>
);

const ResetPassword = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [tokenExpiresAt, setTokenExpiresAt] = useState(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: ''
  });

  const passwordStrength = useMemo(() => 
    calculatePasswordStrength(formData.password), 
    [formData.password]
  );

  const passwordsMatch = formData.password === formData.confirmPassword && formData.confirmPassword.length > 0;
  const allRequirementsMet = passwordStrength.score === 100 && passwordsMatch;

  useEffect(() => {
    verifyToken();
  }, [token]);

  const verifyToken = async () => {
    try {
      const { data } = await authAPI.get(`/auth/verify-reset-token/${token}`);
      if (data.success) {
        setTokenValid(true);
        setTokenExpiresAt(data.expiresAt);
      }
    } catch (error) {
      setTokenValid(false);
      toast.error('This password reset link is invalid or has expired');
    } finally {
      setVerifying(false);
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!passwordsMatch) {
      toast.error('Passwords do not match');
      return;
    }

    if (passwordStrength.score < 100) {
      toast.error('Please meet all password requirements');
      return;
    }

    setLoading(true);

    try {
      const { data } = await authAPI.post('/auth/reset-password', {
        token,
        password: formData.password
      });

      if (data.success) {
        setSuccess(true);
        toast.success('Password reset successful!');
        setTimeout(() => navigate('/login'), 3000);
      }
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to reset password';
      const errors = error.response?.data?.errors;
      if (errors && errors.length > 0) {
        errors.forEach(err => toast.error(err));
      } else {
        toast.error(message);
      }
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <div className="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-white text-lg">Verifying reset link...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white rounded-full mb-4">
            <Brain className="w-8 h-8 text-primary-600" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">AI Council</h1>
          <p className="text-white/80">Multi-Agent Orchestration System</p>
        </div>

        {/* Reset Password Form */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <AnimatePresence mode="wait">
            {!tokenValid ? (
              <motion.div
                key="invalid"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-4"
              >
                <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
                  <AlertCircle className="w-8 h-8 text-red-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-800 mb-2">Invalid Link</h2>
                <p className="text-gray-600 mb-6">
                  This password reset link is invalid or has expired. 
                  Please request a new password reset link.
                </p>
                <Link 
                  to="/forgot-password" 
                  className="inline-flex items-center gap-2 bg-gradient-to-r from-primary-600 to-primary-700 text-white px-6 py-3 rounded-lg font-semibold hover:from-primary-700 hover:to-primary-800 transition-all"
                >
                  Request New Link
                </Link>
              </motion.div>
            ) : success ? (
              <motion.div
                key="success"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <SuccessAnimation />
              </motion.div>
            ) : (
              <motion.div
                key="form"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-800">Set New Password</h2>
                    <p className="text-gray-600 text-sm mt-1">Create a strong password for your account</p>
                  </div>
                  <Shield className="w-8 h-8 text-primary-500" />
                </div>

                {/* Countdown Timer */}
                {tokenExpiresAt && (
                  <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                    <CountdownTimer expiresAt={tokenExpiresAt} />
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* New Password */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      New Password
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        name="password"
                        value={formData.password}
                        onChange={handleChange}
                        required
                        className="w-full pl-10 pr-12 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        placeholder="••••••••"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>

                    {/* Password Strength Indicator */}
                    {formData.password.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="mt-2"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-600">Password Strength</span>
                          <span className={`text-xs font-medium ${
                            passwordStrength.score >= 100 ? 'text-green-600' :
                            passwordStrength.score >= 60 ? 'text-yellow-600' : 'text-red-600'
                          }`}>
                            {passwordStrength.label}
                          </span>
                        </div>
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${passwordStrength.score}%` }}
                            transition={{ duration: 0.3 }}
                            className={`h-full ${passwordStrength.color} transition-all`}
                          />
                        </div>
                      </motion.div>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confirm Password
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showConfirmPassword ? 'text' : 'password'}
                        name="confirmPassword"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        required
                        className={`w-full pl-10 pr-12 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                          formData.confirmPassword.length > 0 
                            ? passwordsMatch 
                              ? 'border-green-500' 
                              : 'border-red-500'
                            : 'border-gray-300'
                        }`}
                        placeholder="••••••••"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>

                  {/* Password Requirements Checklist */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                      <Shield className="w-4 h-4" />
                      Password Requirements
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { key: 'length', label: '8+ characters' },
                        { key: 'uppercase', label: 'Uppercase (A-Z)' },
                        { key: 'lowercase', label: 'Lowercase (a-z)' },
                        { key: 'number', label: 'Number (0-9)' },
                        { key: 'special', label: 'Special (!@#$%)' },
                      ].map(({ key, label }) => (
                        <motion.div
                          key={key}
                          initial={{ opacity: 0.5 }}
                          animate={{ opacity: 1 }}
                          className={`flex items-center gap-2 text-sm ${
                            passwordStrength.checks[key] ? 'text-green-600' : 'text-gray-400'
                          }`}
                        >
                          {passwordStrength.checks[key] ? (
                            <Check className="w-4 h-4" />
                          ) : (
                            <X className="w-4 h-4" />
                          )}
                          <span>{label}</span>
                        </motion.div>
                      ))}
                      <motion.div
                        className={`flex items-center gap-2 text-sm ${
                          passwordsMatch ? 'text-green-600' : 'text-gray-400'
                        }`}
                      >
                        {passwordsMatch ? (
                          <Check className="w-4 h-4" />
                        ) : (
                          <X className="w-4 h-4" />
                        )}
                        <span>Passwords match</span>
                      </motion.div>
                    </div>
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={loading || !allRequirementsMet}
                    className="w-full bg-gradient-to-r from-primary-600 to-primary-700 text-white py-3 rounded-lg font-semibold hover:from-primary-700 hover:to-primary-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        Resetting Password...
                      </>
                    ) : (
                      <>
                        <KeyRound className="w-5 h-5" />
                        Reset Password
                      </>
                    )}
                  </button>
                </form>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Back to Login Link */}
          {!success && (
            <div className="mt-6 text-center">
              <Link 
                to="/login" 
                className="inline-flex items-center gap-2 text-primary-600 font-semibold hover:text-primary-700"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Login
              </Link>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default ResetPassword;
