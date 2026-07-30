# Logging Configuration and Usage Guide

## Overview

The Transcribe-HTR application includes a comprehensive logging system that provides:

- **Configurable logging** via environment variables and config settings
- **Structured logging** with contextual information
- **Audit logging** for user actions and system events
- **File and console output** options
- **Separation from web UI** - logs don't appear on the webpage

## Configuration

### Default Settings (config.py)

```python
# Logging configuration
ENABLE_LOGGING = True
LOG_LEVEL = "INFO"
LOG_TO_FILE = True
LOG_TO_CONSOLE = False  # Disabled to keep web UI clean
```

### Environment Variable Overrides

You can override any setting using environment variables:

```bash
# Change log level — DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
export TRANSCRIBE_HTR_LOG_LEVEL=DEBUG

# Enable console output, useful in development (default: false)
export TRANSCRIBE_HTR_LOG_TO_CONSOLE=true

# Disable file output (default: true)
export TRANSCRIBE_HTR_LOG_TO_FILE=false

# Write logs somewhere other than ./logs
export TRANSCRIBE_HTR_LOG_DIR=/var/log/transcribe-htr

# Flush every record immediately rather than buffering (default: true)
export TRANSCRIBE_HTR_LOG_FORCE_FLUSH=false
```

There is no on/off switch: logging is always configured. To silence it, set
`TRANSCRIBE_HTR_LOG_TO_FILE=false` and leave console output disabled.

## Log Files

- **Location**: `logs/` directory in the application root
- **Format**: `transcribe_htr_YYYYMMDD.log`
- **Rotation**: Daily (one file per day)
- **Structure**: Timestamped entries with module, level, function, and contextual data

### Example Log Entry

```
2025-09-14 14:52:54 - transcribe_htr - INFO - transcribe_image:45 - Starting transcription | model=gpt-4o | session_id=abc123 | n_responses=3
```

## Usage in Code

### Basic Logging

```python
from logging_config import log_info, log_warning, log_error

# Simple messages
log_info("Processing started")
log_warning("Unusual condition detected")
log_error("Operation failed")

# With context data
log_info("File processed",
         filename="document.png",
         file_size=1024,
         session_id=session_id)
```

### Audit Logging

```python
from logging_config import audit_logger
from state_manager import get_session_id

session_id = get_session_id()

# File operations
audit_logger.log_file_upload("document.png", 1024, session_id)

# Transcription events
audit_logger.log_transcription_start("gpt-4o", 3, session_id)
audit_logger.log_transcription_complete("gpt-4o", 500, True, session_id)

# JSON operations
audit_logger.log_json_save("document.transcription.json", session_id)
audit_logger.log_json_load("document.transcription.json", session_id)

# Export operations
audit_logger.log_export("markdown", 5, session_id)

# Error events
audit_logger.log_error_event("api_error", "Rate limit exceeded", session_id)
```

## Integration Status

The logging system is integrated into these modules:

### ✅ Fully Integrated

- **main.py**: App lifecycle, step transitions, errors
- **transcription_engine.py**: API calls, transcription workflow, errors
- **ui_components.py**: File uploads, user interactions
- **json_manager.py**: JSON load/save operations, validation errors
- **logging_config.py**: Core logging infrastructure

### 📋 Available for Integration

Other modules can easily add logging by importing:

```python
from logging_config import log_info, log_warning, log_error, audit_logger
from state_manager import get_session_id
```

## Benefits

### For Development
- **Debugging**: Detailed traces of application flow
- **Performance**: Track operation timing and resource usage
- **Error tracking**: Comprehensive error context and stack traces

### For Production
- **Audit trail**: Complete record of user actions
- **Monitoring**: System health and usage patterns
- **Troubleshooting**: Detailed logs for issue diagnosis
- **Compliance**: Audit logs for security and compliance requirements

### For Users
- **Clean UI**: Logs don't clutter the web interface
- **Privacy**: Sensitive data logging can be controlled
- **Performance**: Logging doesn't impact UI responsiveness

## Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational information
- **WARNING**: Something unexpected but not an error
- **ERROR**: Serious problem that prevented operation
- **CRITICAL**: Very serious error that may abort operation

## Best Practices

### When to Log

1. **Always log**:
   - Application start/stop
   - User actions (upload, transcribe, export)
   - API calls and responses
   - File operations
   - Errors and exceptions

2. **Consider logging**:
   - Performance metrics
   - Configuration changes
   - User authentication events
   - Data validation results

3. **Avoid logging**:
   - Sensitive user data (API keys, personal info)
   - High-frequency events that would spam logs
   - Redundant information already captured elsewhere

### Message Format

- Use clear, descriptive messages
- Include relevant context as key-value pairs
- Always include `session_id` for user action correlation
- Use consistent naming for parameters

### Error Handling

```python
try:
    # Operation that might fail
    result = risky_operation()
    log_info("Operation completed", result_size=len(result))
except Exception as e:
    log_error("Operation failed",
              error=str(e),
              operation="risky_operation",
              session_id=get_session_id())
    # Handle error appropriately
```

## Troubleshooting

### Logs Not Appearing

1. Check `ENABLE_LOGGING` setting in config or environment
2. Verify log directory permissions
3. Check disk space
4. Ensure proper imports in your module

### Performance Issues

1. Reduce log level (INFO → WARNING → ERROR)
2. Disable console logging in production
3. Use structured data instead of string formatting
4. Consider log rotation settings

### Configuration Issues

1. Verify environment variables are set correctly
2. Check that config.py is being imported properly
3. Ensure logging is initialized before use
4. Check for module import order issues

## Security Considerations

- **Never log sensitive data**: API keys, passwords, personal information
- **Use structured logging**: Easier to parse and filter
- **Implement log rotation**: Prevent disk space issues
- **Control access**: Secure log file permissions
- **Consider privacy**: Some jurisdictions have requirements for data logging

## Future Enhancements

Potential improvements for the logging system:

1. **Remote logging**: Send logs to external services (ELK, Splunk)
2. **Log aggregation**: Combine logs from multiple instances
3. **Alerting**: Notify on critical errors
4. **Dashboard**: Web interface for log analysis
5. **Metrics**: Export logging metrics to monitoring systems
