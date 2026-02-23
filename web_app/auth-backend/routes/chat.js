const express = require('express');
const router = express.Router();
const ChatHistory = require('../models/ChatHistory');
const { protect } = require('../middleware/auth');

// @route   POST /api/chat/save
// @desc    Save chat interaction
// @access  Private
router.post('/save', protect, async (req, res) => {
  try {
    const {
      query,
      response,
      executionMode,
      modelsUsed,
      confidence,
      cost,
      executionTime,
      orchestrationData
    } = req.body;

    const chatHistory = await ChatHistory.create({
      userId: req.user._id,
      query,
      response,
      executionMode,
      modelsUsed,
      confidence,
      cost,
      executionTime,
      orchestrationData
    });

    res.status(201).json({
      success: true,
      data: chatHistory
    });
  } catch (error) {
    console.error('Save chat error:', error);
    res.status(500).json({ success: false, message: 'Failed to save chat history' });
  }
});

// @route   GET /api/chat/history
// @desc    Get user's chat history
// @access  Private
router.get('/history', protect, async (req, res) => {
  try {
    const { page = 1, limit = 20 } = req.query;
    
    const chats = await ChatHistory.find({ userId: req.user._id })
      .sort({ timestamp: -1 })
      .limit(limit * 1)
      .skip((page - 1) * limit)
      .select('-orchestrationData'); // Exclude heavy data for list view

    const count = await ChatHistory.countDocuments({ userId: req.user._id });

    res.json({
      success: true,
      data: chats,
      totalPages: Math.ceil(count / limit),
      currentPage: page,
      total: count
    });
  } catch (error) {
    console.error('Get history error:', error);
    res.status(500).json({ success: false, message: 'Failed to fetch chat history' });
  }
});

// @route   GET /api/chat/history/:id
// @desc    Get specific chat with full orchestration data
// @access  Private
router.get('/history/:id', protect, async (req, res) => {
  try {
    const chat = await ChatHistory.findOne({
      _id: req.params.id,
      userId: req.user._id
    });

    if (!chat) {
      return res.status(404).json({ success: false, message: 'Chat not found' });
    }

    res.json({
      success: true,
      data: chat
    });
  } catch (error) {
    console.error('Get chat error:', error);
    res.status(500).json({ success: false, message: 'Failed to fetch chat' });
  }
});

// @route   GET /api/chat/analytics
// @desc    Get user's analytics
// @access  Private
router.get('/analytics', protect, async (req, res) => {
  try {
    const userId = req.user._id;

    // Total queries
    const totalQueries = await ChatHistory.countDocuments({ userId });

    // Total cost
    const costAgg = await ChatHistory.aggregate([
      { $match: { userId } },
      { $group: { _id: null, totalCost: { $sum: '$cost' } } }
    ]);
    const totalCost = costAgg[0]?.totalCost || 0;

    // Average confidence
    const confidenceAgg = await ChatHistory.aggregate([
      { $match: { userId } },
      { $group: { _id: null, avgConfidence: { $avg: '$confidence' } } }
    ]);
    const avgConfidence = confidenceAgg[0]?.avgConfidence || 0;

    // Models usage
    const modelsAgg = await ChatHistory.aggregate([
      { $match: { userId } },
      { $unwind: '$modelsUsed' },
      { $group: { _id: '$modelsUsed', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    // Execution mode distribution
    const modeAgg = await ChatHistory.aggregate([
      { $match: { userId } },
      { $group: { _id: '$executionMode', count: { $sum: 1 } } }
    ]);

    // Recent activity (last 7 days)
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const recentActivity = await ChatHistory.aggregate([
      { $match: { userId, timestamp: { $gte: sevenDaysAgo } } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$timestamp' } },
          count: { $sum: 1 },
          totalCost: { $sum: '$cost' }
        }
      },
      { $sort: { _id: 1 } }
    ]);

    // Average execution time
    const execTimeAgg = await ChatHistory.aggregate([
      { $match: { userId } },
      { $group: { _id: null, avgTime: { $avg: '$executionTime' } } }
    ]);
    const avgExecutionTime = execTimeAgg[0]?.avgTime || 0;

    res.json({
      success: true,
      analytics: {
        totalQueries,
        totalCost: parseFloat(totalCost.toFixed(4)),
        avgConfidence: parseFloat(avgConfidence.toFixed(2)),
        avgExecutionTime: parseFloat(avgExecutionTime.toFixed(2)),
        modelsUsage: modelsAgg,
        executionModes: modeAgg,
        recentActivity
      }
    });
  } catch (error) {
    console.error('Analytics error:', error);
    res.status(500).json({ success: false, message: 'Failed to fetch analytics' });
  }
});

// @route   DELETE /api/chat/history/:id
// @desc    Delete specific chat
// @access  Private
router.delete('/history/:id', protect, async (req, res) => {
  try {
    const chat = await ChatHistory.findOneAndDelete({
      _id: req.params.id,
      userId: req.user._id
    });

    if (!chat) {
      return res.status(404).json({ success: false, message: 'Chat not found' });
    }

    res.json({
      success: true,
      message: 'Chat deleted successfully'
    });
  } catch (error) {
    console.error('Delete chat error:', error);
    res.status(500).json({ success: false, message: 'Failed to delete chat' });
  }
});

module.exports = router;
