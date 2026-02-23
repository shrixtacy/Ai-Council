const nodemailer = require('nodemailer');

// HTML escape function to prevent XSS
const escapeHtml = (text) => {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

const transporter = nodemailer.createTransport({
  host: process.env.EMAIL_HOST,
  port: process.env.EMAIL_PORT,
  secure: false,
  auth: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_PASSWORD
  }
});

const sendOTPEmail = async (email, otp, name) => {
  // Sanitize user-provided name to prevent XSS
  const safeName = escapeHtml(name);
  
  const mailOptions = {
    from: `"AI Council" <${process.env.EMAIL_USER}>`,
    to: email,
    subject: 'Verify Your AI Council Account',
    html: `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .otp-box { background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }
          .otp-code { font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px; }
          .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>🤖 AI Council</h1>
            <p>Multi-Agent Orchestration System</p>
          </div>
          <div class="content">
            <h2>Welcome, ${safeName}!</h2>
            <p>Thank you for registering with AI Council. To complete your registration, please verify your email address using the OTP below:</p>
            
            <div class="otp-box">
              <p style="margin: 0; color: #666;">Your verification code:</p>
              <div class="otp-code">${otp}</div>
              <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">Valid for ${process.env.OTP_EXPIRE_MINUTES || 10} minutes</p>
            </div>
            
            <p><strong>Important:</strong></p>
            <ul>
              <li>This OTP is valid for ${process.env.OTP_EXPIRE_MINUTES || 10} minutes</li>
              <li>Do not share this code with anyone</li>
              <li>If you didn't request this, please ignore this email</li>
            </ul>
            
            <p>Once verified, you'll have access to:</p>
            <ul>
              <li>✨ Multi-model AI orchestration</li>
              <li>📊 Real-time analytics dashboard</li>
              <li>💰 Cost optimization tools</li>
              <li>📈 Chat history and insights</li>
            </ul>
          </div>
          <div class="footer">
            <p>© 2026 AI Council Orchestrator. All rights reserved.</p>
            <p>This is an automated email. Please do not reply.</p>
          </div>
        </div>
      </body>
      </html>
    `
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log(`OTP email sent to ${email}`);
    return true;
  } catch (error) {
    console.error('Error sending OTP email:', error);
    throw new Error('Failed to send verification email');
  }
};

const sendPasswordResetEmail = async (email, resetUrl, name) => {
  // Sanitize user-provided name to prevent XSS
  const safeName = escapeHtml(name);
  
  const mailOptions = {
    from: `"AI Council" <${process.env.EMAIL_USER}>`,
    to: email,
    subject: 'Reset Your AI Council Password',
    html: `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .button-box { text-align: center; margin: 30px 0; }
          .reset-button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; text-decoration: none; padding: 15px 40px; border-radius: 8px; font-weight: bold; font-size: 16px; }
          .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
          .warning { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin: 20px 0; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>🔐 AI Council</h1>
            <p>Password Reset Request</p>
          </div>
          <div class="content">
            <h2>Hello, ${safeName}!</h2>
            <p>We received a request to reset your password for your AI Council account. Click the button below to set a new password:</p>
            
            <div class="button-box">
              <a href="${resetUrl}" class="reset-button">Reset Password</a>
            </div>
            
            <p>This link will expire in <strong>1 hour</strong>.</p>
            
            <div class="warning">
              <strong>⚠️ Security Notice:</strong>
              <ul style="margin: 5px 0;">
                <li>If you didn't request this password reset, please ignore this email</li>
                <li>Your password will remain unchanged until you create a new one</li>
                <li>Never share this link with anyone</li>
              </ul>
            </div>
            
            <p style="color: #666; font-size: 14px;">If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #667eea; font-size: 12px;">${resetUrl}</p>
          </div>
          <div class="footer">
            <p>© 2026 AI Council Orchestrator. All rights reserved.</p>
            <p>This is an automated email. Please do not reply.</p>
          </div>
        </div>
      </body>
      </html>
    `
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log(`Password reset email sent to ${email}`);
    return true;
  } catch (error) {
    console.error('Error sending password reset email:', error);
    throw new Error('Failed to send password reset email');
  }
};

const sendPasswordResetConfirmation = async (email, name) => {
  // Sanitize user-provided name to prevent XSS
  const safeName = escapeHtml(name);
  
  const mailOptions = {
    from: `"AI Council" <${process.env.EMAIL_USER}>`,
    to: email,
    subject: 'Your AI Council Password Has Been Changed',
    html: `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .success-box { background: #d1fae5; border: 1px solid #10b981; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }
          .success-icon { font-size: 48px; }
          .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
          .warning { background: #fef3c7; border: 1px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 20px 0; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>✅ AI Council</h1>
            <p>Password Changed Successfully</p>
          </div>
          <div class="content">
            <h2>Hello, ${safeName}!</h2>
            
            <div class="success-box">
              <div class="success-icon">🔐</div>
              <p style="margin: 10px 0 0 0; font-weight: bold; color: #059669;">Your password has been successfully changed!</p>
            </div>
            
            <p>This email confirms that your AI Council account password was just changed. You can now log in with your new password.</p>
            
            <div class="warning">
              <strong>⚠️ Didn't make this change?</strong>
              <p style="margin: 5px 0 0 0;">If you did not change your password, your account may have been compromised. Please:</p>
              <ul style="margin: 5px 0;">
                <li>Reset your password immediately</li>
                <li>Check your account for any unauthorized activity</li>
                <li>Contact our support team if you need assistance</li>
              </ul>
            </div>
            
            <p><strong>Security Tips:</strong></p>
            <ul>
              <li>Never share your password with anyone</li>
              <li>Use a unique password for each account</li>
              <li>Enable two-factor authentication when available</li>
              <li>Be cautious of phishing emails</li>
            </ul>
          </div>
          <div class="footer">
            <p>© 2026 AI Council Orchestrator. All rights reserved.</p>
            <p>This is an automated security notification. Please do not reply.</p>
          </div>
        </div>
      </body>
      </html>
    `
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log(`Password reset confirmation email sent to ${email}`);
    return true;
  } catch (error) {
    console.error('Error sending password reset confirmation email:', error);
    throw new Error('Failed to send password reset confirmation email');
  }
};

module.exports = { sendOTPEmail, sendPasswordResetEmail, sendPasswordResetConfirmation };
