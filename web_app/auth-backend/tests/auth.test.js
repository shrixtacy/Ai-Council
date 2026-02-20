const request = require('supertest');
const { connect, closeDatabase, clearDatabase } = require('./setup');

jest.setTimeout(30000);

// Mock email to avoid sending actual emails during tests
jest.mock('../utils/email', () => ({
  sendOTPEmail: jest.fn().mockResolvedValue(true)
}));

// We must require app AFTER setting environment variables if not using a global setup
process.env.JWT_SECRET = 'test-secret';
process.env.JWT_EXPIRE = '1h';

let app;

beforeAll(async () => {
  await connect();
  // Require app after DB is connected and env vars are set
  app = require('../server');
});

afterAll(async () => {
  await closeDatabase();
});

afterEach(async () => {
  await clearDatabase();
  jest.clearAllMocks();
});

describe('Auth Endpoints', () => {
  let createdUserId;
  let createdOtp;

  it('should register a new user successfully', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({
        name: 'Test User',
        email: 'test@example.com',
        password: 'password123'
      });

    expect(res.statusCode).toEqual(201);
    expect(res.body.success).toBe(true);
    expect(res.body.userId).toBeDefined();
    createdUserId = res.body.userId;
    
    // We need to fetch the OTP from the database to test the verify endpoint
    const User = require('../models/User');
    const user = await User.findById(createdUserId).exec();
    expect(user).toBeDefined();
    expect(user.otp).toBeDefined();
    expect(user.isVerified).toBe(false);
    createdOtp = user.otp.code;
  });
  
  it('should not allow duplicate email registration if already verified', async () => {
    // Create and verify user
    const User = require('../models/User');
    await User.create({
      name: 'Existing User',
      email: 'existing@example.com',
      password: 'password123',
      isVerified: true
    });

    const res = await request(app)
      .post('/api/auth/register')
      .send({
        name: 'Another User',
        email: 'existing@example.com',
        password: 'password456'
      });

    expect(res.statusCode).toEqual(400);
    expect(res.body.message).toBe('User already exists');
  });

  it('should verify OTP successfully', async () => {
    // First register
    const regRes = await request(app)
      .post('/api/auth/register')
      .send({
        name: 'Verify User',
        email: 'verify@example.com',
        password: 'password123'
      });
      
    const User = require('../models/User');
    const user = await User.findById(regRes.body.userId);
    
    // Then verify
    const verifyRes = await request(app)
      .post('/api/auth/verify-otp')
      .send({
        userId: regRes.body.userId,
        otp: user.otp.code
      });

    expect(verifyRes.statusCode).toEqual(200);
    expect(verifyRes.body.success).toBe(true);
    expect(verifyRes.body.token).toBeDefined();
    expect(verifyRes.body.user).toBeDefined();
  });

  it('should login a verified user successfully', async () => {
    // First register
    const regRes = await request(app)
      .post('/api/auth/register')
      .send({
        name: 'Login User',
        email: 'login@example.com',
        password: 'password123'
      });
      
    const User = require('../models/User');
    const user = await User.findById(regRes.body.userId);
    
    // Then verify
    await request(app)
      .post('/api/auth/verify-otp')
      .send({
        userId: regRes.body.userId,
        otp: user.otp.code
      });

    // Finally login
    const loginRes = await request(app)
      .post('/api/auth/login')
      .send({
        email: 'login@example.com',
        password: 'password123'
      });

    expect(loginRes.statusCode).toEqual(200);
    expect(loginRes.body.success).toBe(true);
    expect(loginRes.body.token).toBeDefined();
  });
});
