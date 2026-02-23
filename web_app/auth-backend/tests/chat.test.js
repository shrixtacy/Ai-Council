const request = require('supertest');
const { connect, closeDatabase, clearDatabase } = require('./setup');
const jwt = require('jsonwebtoken');

jest.setTimeout(30000);

jest.mock('../utils/email', () => ({
  sendOTPEmail: jest.fn().mockResolvedValue(true)
}));

process.env.JWT_SECRET = 'test-secret';
process.env.JWT_EXPIRE = '1h';

let app;

beforeAll(async () => {
  await connect();
  app = require('../server');
});

afterAll(async () => {
  await closeDatabase();
});

afterEach(async () => {
  await clearDatabase();
  jest.clearAllMocks();
});

describe('Chat Endpoints', () => {
  let token;
  let userId;

  beforeEach(async () => {
    // Create a mock user and generate a token
    const User = require('../models/User');
    const user = await User.create({
      name: 'Chat User',
      email: 'chat@example.com',
      password: 'password123',
      isVerified: true
    });
    
    userId = user._id;
    token = jwt.sign({ id: user._id }, process.env.JWT_SECRET, {
      expiresIn: process.env.JWT_EXPIRE
    });
    
    // Create a mock session
    const Session = require('../models/Session');
    await Session.create({
      userId: user._id,
      token,
      ipAddress: '127.0.0.1',
      userAgent: 'jest'
    });
  });

  it('should save a chat interaction successfully', async () => {
    const chatData = {
      query: 'Hello AI',
      response: 'Hello Human',
      executionMode: 'fast',
      modelsUsed: ['gpt-3.5-turbo'],
      confidence: 0.95,
      cost: 0.001,
      executionTime: 1.5,
      orchestrationData: { details: 'Mock data' }
    };

    const res = await request(app)
      .post('/api/chat/save')
      .set('Authorization', `Bearer ${token}`)
      .send(chatData);

    expect(res.statusCode).toEqual(201);
    expect(res.body.success).toBe(true);
    expect(res.body.data.query).toBe('Hello AI');
    expect(res.body.data.userId.toString()).toBe(userId.toString());
  });

  it('should fetch chat history successfully', async () => {
    // Save a chat first
    const ChatHistory = require('../models/ChatHistory');
    await ChatHistory.create({
      userId,
      query: 'Test history',
      response: 'Resp',
      executionMode: 'fast',
      modelsUsed: ['gpt-3.5-turbo'],
      confidence: 0.99,
      cost: 0.001,
      executionTime: 1.0
    });

    const res = await request(app)
      .get('/api/chat/history')
      .set('Authorization', `Bearer ${token}`);

    expect(res.statusCode).toEqual(200);
    expect(res.body.success).toBe(true);
    expect(res.body.data.length).toBeGreaterThan(0);
    expect(res.body.data[0].query).toBe('Test history');
    // Ensure orchestration data is excluded
    expect(res.body.data[0].orchestrationData).toBeUndefined();
  });

  it('should prevent access without token', async () => {
    const res = await request(app)
      .get('/api/chat/history');

    expect(res.statusCode).toEqual(401);
  });
});
