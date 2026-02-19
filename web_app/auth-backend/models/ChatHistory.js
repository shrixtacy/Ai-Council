const mongoose = require('mongoose');

const chatHistorySchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    index: true
  },
  query: {
    type: String,
    required: true
  },
  response: {
    type: String,
    required: true
  },
  executionMode: {
    type: String,
    enum: ['fast', 'balanced', 'best_quality'],
    default: 'balanced'
  },
  modelsUsed: [{
    type: String
  }],
  confidence: {
    type: Number,
    min: 0,
    max: 1
  },
  cost: {
    type: Number,
    default: 0
  },
  executionTime: {
    type: Number,
    default: 0
  },
  orchestrationData: {
    subtasks: [{
      id: String,
      content: String,
      taskType: String,
      assignedModel: String,
      status: String,
      startTime: Date,
      endTime: Date,
      confidence: Number
    }],
    arbitrationDecisions: [String],
    synthesisNotes: [String]
  },
  timestamp: {
    type: Date,
    default: Date.now,
    index: true
  }
});

// Index for efficient queries
chatHistorySchema.index({ userId: 1, timestamp: -1 });

module.exports = mongoose.model('ChatHistory', chatHistorySchema);
