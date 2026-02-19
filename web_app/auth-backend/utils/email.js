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

module.exports = { sendOTPEmail };
