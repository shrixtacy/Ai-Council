import json
import io
import logging
import inspect
from ai_council.core.logger import configure_json_logging, get_logger, trace_id, span_id

def test_json_logging_structure():
    # Capture output in a StringIO stream
    log_stream = io.StringIO()
    
    # Configure json logging
    configure_json_logging(level="DEBUG")
    
    # Overwrite the stream of the handler to capture output
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.stream = log_stream
            
    # Get the context adapter
    logger = get_logger("my.test.module")
    
    # Set context variables
    trace_id.set("test-trace-123")
    span_id.set("test-span-456")
    
    # Log the message
    logger.info("This is a structured log entry", extra={"user_id": 999, "action": "login"})
    
    # Process the output
    output = log_stream.getvalue().strip()
    
    lines = output.split("\n")
    assert len(lines) == 1, "Expected exactly one log line"
    
    try:
        log_record = json.loads(lines[0])
    except json.JSONDecodeError:
        assert False, f"Log output is not valid JSON: {output}"
        
    # Standard format expectations
    assert "timestamp" in log_record
    assert log_record["level"] == "INFO"
    assert log_record["name"] == "my.test.module"
    assert "This is a structured log entry" in log_record["message"]
    
    # Context injected expectations
    assert log_record["trace_id"] == "test-trace-123"
    assert log_record["span_id"] == "test-span-456"
    
    # Extra fields expectations
    assert log_record["user_id"] == 999
    assert log_record["action"] == "login"
    
    print("Structured logging is fully functional!")
