import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Zap, CheckCircle, Clock, AlertCircle } from 'lucide-react';

const OrchestrationVisualizer = ({ orchestrationData, isProcessing }) => {
  const [activeSubtasks, setActiveSubtasks] = useState([]);

  useEffect(() => {
    if (orchestrationData?.subtasks) {
      setActiveSubtasks(orchestrationData.subtasks);
    }
  }, [orchestrationData]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'processing':
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Zap className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'processing':
        return 'bg-blue-500 animate-pulse';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  if (!isProcessing && activeSubtasks.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
      <div className="flex items-center gap-3 mb-6">
        <Brain className="w-6 h-6 text-primary-600" />
        <h3 className="text-xl font-bold text-gray-800">Live Orchestration</h3>
      </div>

      {/* Main Task */}
      <div className="mb-6">
        <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-primary-50 to-primary-100 rounded-lg">
          <div className="w-12 h-12 bg-primary-600 rounded-full flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-gray-800">Main Orchestrator</p>
            <p className="text-sm text-gray-600">Analyzing and decomposing task...</p>
          </div>
          {isProcessing && (
            <div className="w-3 h-3 bg-primary-600 rounded-full animate-pulse"></div>
          )}
        </div>
      </div>

      {/* Subtasks */}
      <div className="space-y-4">
        <AnimatePresence>
          {activeSubtasks.map((subtask, index) => (
            <motion.div
              key={subtask.id || index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: index * 0.1 }}
              className="relative"
            >
              {/* Connection Line */}
              <div className="absolute left-6 top-0 w-0.5 h-full bg-gray-200 -z-10"></div>
              
              <div className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                {/* Status Indicator */}
                <div className="relative">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    subtask.status === 'processing' ? 'bg-blue-100' :
                    subtask.status === 'completed' ? 'bg-green-100' :
                    subtask.status === 'failed' ? 'bg-red-100' : 'bg-gray-100'
                  }`}>
                    {getStatusIcon(subtask.status)}
                  </div>
                  {subtask.status === 'processing' && (
                    <div className="absolute inset-0 rounded-full border-2 border-blue-500 animate-ping"></div>
                  )}
                </div>

                {/* Subtask Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-gray-500 uppercase">
                      {subtask.taskType || 'Task'}
                    </span>
                    <span className={`w-2 h-2 rounded-full ${getStatusColor(subtask.status)}`}></span>
                  </div>
                  
                  <p className="text-sm text-gray-700 mb-2">{subtask.content}</p>
                  
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Brain className="w-3 h-3" />
                      {subtask.assignedModel || 'Assigning...'}
                    </span>
                    
                    {subtask.confidence && (
                      <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {(subtask.confidence * 100).toFixed(0)}% confidence
                      </span>
                    )}
                    
                    {subtask.startTime && subtask.endTime && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {((new Date(subtask.endTime) - new Date(subtask.startTime)) / 1000).toFixed(2)}s
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Arbitration & Synthesis */}
      {orchestrationData?.arbitrationDecisions?.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg"
        >
          <h4 className="font-semibold text-yellow-800 mb-2">⚖️ Arbitration Layer</h4>
          <ul className="text-sm text-yellow-700 space-y-1">
            {orchestrationData.arbitrationDecisions.map((decision, i) => (
              <li key={i}>• {decision}</li>
            ))}
          </ul>
        </motion.div>
      )}

      {orchestrationData?.synthesisNotes?.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg"
        >
          <h4 className="font-semibold text-green-800 mb-2">🔄 Synthesis Layer</h4>
          <ul className="text-sm text-green-700 space-y-1">
            {orchestrationData.synthesisNotes.map((note, i) => (
              <li key={i}>• {note}</li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  );
};

export default OrchestrationVisualizer;
