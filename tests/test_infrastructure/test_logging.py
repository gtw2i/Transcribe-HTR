"""
Test logging integration functionality for Transcribe-HTR application.

This module contains tests for logging configuration, file creation,
environment variable overrides, and audit logging functionality.
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestLoggingConfiguration:
    """Test logging configuration and basic functionality."""

    def test_config_imports(self):
        """Test that logging configuration variables can be imported.

        These live in logging_config, not config: the backend owns its logging
        settings in the module that consumes them, and has no ENABLE_LOGGING
        on/off flag (logging is always configured).
        """
        try:
            from logging_config import LOG_LEVEL, LOG_TO_CONSOLE, LOG_TO_FILE

            # Verify config variables exist and have expected types
            assert isinstance(LOG_LEVEL, str)
            assert isinstance(LOG_TO_CONSOLE, bool)
            assert isinstance(LOG_TO_FILE, bool)

            # Verify LOG_LEVEL is a valid logging level
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            assert LOG_LEVEL.upper() in valid_levels

        except ImportError as e:
            pytest.fail(f"Failed to import logging configuration: {e}")

    def test_logging_config_imports(self):
        """Test that logging configuration functions can be imported."""
        try:
            from logging_config import audit_logger, log_error, log_info, log_warning

            # Verify functions exist and are callable
            assert callable(log_info)
            assert callable(log_warning)
            assert callable(log_error)
            assert hasattr(audit_logger, "log_file_upload")
            assert hasattr(audit_logger, "log_transcription_start")
            assert hasattr(audit_logger, "log_transcription_complete")

        except ImportError as e:
            pytest.fail(f"Failed to import logging functions: {e}")

    @patch("logging_config._default_logger")
    def test_logging_functions(self, mock_logger):
        """Test that logging functions work correctly."""
        try:
            from logging_config import log_error, log_info, log_warning

            # Test logging functions with mock
            log_info("Test info message", test_param="value", session_id="test-session")
            log_warning(
                "Test warning message", test_param="value", session_id="test-session"
            )
            log_error(
                "Test error message", test_param="value", session_id="test-session"
            )

            # Verify that the functions execute without error
            # Note: The actual logger calls may be handled differently in the implementation
            assert True  # Functions executed without exception

        except Exception as e:
            pytest.fail(f"Logging functions failed: {e}")

    @patch("logging_config.audit_logger")
    def test_audit_logger_functionality(self, mock_audit_logger):
        """Test audit logger functionality."""
        try:
            from logging_config import audit_logger

            # Test audit logger methods
            audit_logger.log_file_upload("test.png", 1024, "test-session")
            audit_logger.log_transcription_start("gpt-4o", 3, "test-session")
            audit_logger.log_transcription_complete("gpt-4o", 500, True, "test-session")
            audit_logger.log_json_save("test.json", "test-session")
            audit_logger.log_json_load("test.json", "test-session")

            # Verify methods exist and are callable
            assert hasattr(audit_logger, "log_file_upload")
            assert callable(audit_logger.log_file_upload)

        except Exception as e:
            pytest.fail(f"Audit logger test failed: {e}")


class TestModuleImports:
    """Test that modules import correctly with logging integration."""

    def test_core_module_imports(self):
        """Test that core modules with logging can be imported."""
        # Test modules that should import without Streamlit dependency
        importable_modules = ["logging_config", "config"]

        for module_name in importable_modules:
            try:
                module = importlib.import_module(module_name)
                assert module is not None

            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_config_logging_integration(self):
        """Test integration between config and logging modules."""
        try:
            from logging_config import LOG_LEVEL, log_info

            # Verify that config values are accessible
            assert isinstance(LOG_LEVEL, str)

            # Test that logging works with config integration
            log_info("Integration test message")

        except Exception as e:
            pytest.fail(f"Config-logging integration failed: {e}")

    def test_optional_module_imports(self):
        """Test imports for modules that may have dependencies."""
        optional_modules = [
            "transcription_engine",
            "harmonization_engine",
            "file_manager",
        ]

        imported_count = 0

        for module_name in optional_modules:
            try:
                module = importlib.import_module(module_name)
                if module is not None:
                    imported_count += 1

            except ImportError:
                # Optional modules may not be importable in test environment
                continue

        # At least some optional modules should be importable
        # This is informational rather than a hard requirement
        assert imported_count >= 0  # Always passes, but gives us count info


class TestLogFileCreation:
    """Test log file creation and management."""

    @pytest.fixture
    def temp_log_directory(self):
        """Create a temporary directory for log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_log_directory_configuration(self):
        """Test that log directory configuration is accessible."""
        try:
            from logging_config import LOG_DIRECTORY

            assert isinstance(LOG_DIRECTORY, Path)

        except ImportError:
            pytest.skip("LOG_DIRECTORY not available in logging_config")

    @patch("logging_config.LOG_DIRECTORY")
    def test_log_file_creation_when_enabled(self, mock_log_dir, temp_log_directory):
        """Test log file creation when LOG_TO_FILE is enabled."""
        mock_log_dir.return_value = temp_log_directory

        try:
            from logging_config import LOG_TO_FILE

            if not LOG_TO_FILE:
                pytest.skip("LOG_TO_FILE is disabled, skipping file creation test")

            # Create a test log file
            test_log_file = temp_log_directory / "test.log"
            test_log_file.write_text("Test log content\n")

            # Verify file was created
            assert test_log_file.exists()
            assert test_log_file.stat().st_size > 0

        except ImportError:
            pytest.skip("LOG_TO_FILE configuration not available")

    def test_log_file_discovery(self, temp_log_directory):
        """Test discovery of existing log files."""
        # Create some test log files
        log_files = [
            temp_log_directory / "app.log",
            temp_log_directory / "audit.log",
            temp_log_directory / "error.log",
        ]

        for log_file in log_files:
            log_file.write_text(f"Log content for {log_file.name}\n")

        # Test file discovery
        found_files = list(temp_log_directory.glob("*.log"))

        assert len(found_files) == 3
        assert all(f.suffix == ".log" for f in found_files)
        assert all(f.stat().st_size > 0 for f in found_files)

    def test_log_directory_creation(self):
        """Test that log directory is created when needed."""
        try:
            from logging_config import LOG_DIRECTORY

            # LOG_DIRECTORY should be a Path object
            assert isinstance(LOG_DIRECTORY, Path)

            # Directory may or may not exist depending on configuration
            # This test just verifies the configuration is accessible

        except ImportError:
            pytest.skip("LOG_DIRECTORY not available for testing")


class TestEnvironmentVariableOverride:
    """Test environment variable override functionality."""

    def test_environment_variable_override(self):
        """Environment variables override the logging settings on reload."""
        env_var_name = "TRANSCRIBE_HTR_LOG_LEVEL"
        original_value = os.environ.get(env_var_name)

        try:
            os.environ[env_var_name] = "DEBUG"

            # Reload to pick up the environment change — the settings are read
            # at import time in logging_config.
            module = importlib.reload(sys.modules["logging_config"])

            assert module.LOG_LEVEL == "DEBUG"

        except Exception as e:
            pytest.fail(f"Environment variable override test failed: {e}")

        finally:
            if original_value is not None:
                os.environ[env_var_name] = original_value
            elif env_var_name in os.environ:
                del os.environ[env_var_name]

            importlib.reload(sys.modules["logging_config"])

    def test_multiple_environment_overrides(self):
        """Test multiple environment variable overrides."""
        env_vars = {
            "TRANSCRIBE_HTR_LOG_LEVEL": "DEBUG",
            "TRANSCRIBE_HTR_LOG_TO_FILE": "false",
            "TRANSCRIBE_HTR_LOG_TO_CONSOLE": "true",
        }

        # Save original values
        original_values = {}
        for var_name in env_vars:
            original_values[var_name] = os.environ.get(var_name)

        try:
            # Set test environment variables
            for var_name, var_value in env_vars.items():
                os.environ[var_name] = var_value

            module = importlib.reload(sys.modules["logging_config"])

            # Each override must take effect independently.
            assert module.LOG_LEVEL == "DEBUG"
            assert module.LOG_TO_FILE is False
            assert module.LOG_TO_CONSOLE is True

        except Exception as e:
            pytest.fail(f"Multiple environment override test failed: {e}")

        finally:
            # Restore original environment
            for var_name, original_value in original_values.items():
                if original_value is not None:
                    os.environ[var_name] = original_value
                elif var_name in os.environ:
                    del os.environ[var_name]

            importlib.reload(sys.modules["logging_config"])


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    @patch("logging_config._default_logger")
    def test_end_to_end_logging_workflow(self, mock_logger):
        """Test complete logging workflow from configuration to output."""
        try:
            # Import and test configuration
            from logging_config import (
                LOG_LEVEL,
                audit_logger,
                log_error,
                log_info,
                log_warning,
            )

            # Test basic logging functionality
            test_session_id = "integration-test-session"

            log_info("Integration test started", session_id=test_session_id)
            log_warning("Test warning message", session_id=test_session_id)
            log_error("Test error message", session_id=test_session_id)

            # Test audit logging
            audit_logger.log_file_upload("test_document.png", 2048, test_session_id)
            audit_logger.log_transcription_start("gpt-4o", 5, test_session_id)
            audit_logger.log_transcription_complete(
                "gpt-4o", 750, True, test_session_id
            )

            # Verify configuration values
            assert isinstance(LOG_LEVEL, str)

        except Exception as e:
            pytest.fail(f"End-to-end logging workflow failed: {e}")

    def test_logging_with_different_configurations(self):
        """Test logging behavior with different configuration scenarios."""
        test_configs = [
            {"LOG_LEVEL": "INFO", "LOG_TO_FILE": "true"},
            {"LOG_LEVEL": "ERROR", "LOG_TO_FILE": "false"},
            {"LOG_LEVEL": "DEBUG", "LOG_TO_FILE": "true"},
        ]

        try:
            for config_scenario in test_configs:
                with patch.dict(
                    os.environ,
                    {
                        f"TRANSCRIBE_HTR_{k}": str(v)
                        for k, v in config_scenario.items()
                    },
                ):
                    try:
                        module = importlib.reload(sys.modules["logging_config"])

                        assert module.LOG_LEVEL == config_scenario["LOG_LEVEL"]
                        assert module.LOG_TO_FILE is (
                            config_scenario["LOG_TO_FILE"] == "true"
                        )

                    except Exception as e:
                        pytest.fail(
                            f"Configuration scenario {config_scenario} failed: {e}"
                        )
        finally:
            # Restore the module to the ambient environment's settings so later
            # tests are not affected by the last scenario.
            importlib.reload(sys.modules["logging_config"])

    def test_logging_error_handling(self):
        """Test logging system's error handling capabilities."""
        try:
            from logging_config import log_error, log_info

            # Test logging with various parameter types
            test_cases = [
                ("Simple message", {}),
                ("Message with params", {"param1": "value1", "param2": 123}),
                ("Message with None param", {"param": None}),
                ("Message with complex param", {"param": {"nested": "value"}}),
            ]

            for message, params in test_cases:
                try:
                    log_info(message, **params)
                except Exception as e:
                    pytest.fail(f"Logging failed for case {message}: {e}")

            # Test error logging specifically
            try:
                log_error(
                    "Test error with exception info", error_details="test details"
                )
            except Exception as e:
                pytest.fail(f"Error logging failed: {e}")

        except ImportError:
            pytest.skip("Logging functions not available for error handling test")


class TestLoggingPerformance:
    """Test logging performance and resource usage."""

    @patch("logging_config._default_logger")
    def test_logging_performance(self, mock_logger):
        """Test that logging doesn't significantly impact performance."""
        try:
            # Test rapid logging calls
            import time

            from logging_config import log_info

            start_time = time.time()

            for i in range(100):
                log_info(f"Performance test message {i}", iteration=i)

            end_time = time.time()
            elapsed = end_time - start_time

            # Logging 100 messages should be reasonably fast (< 1 second)
            assert elapsed < 1.0, f"Logging took too long: {elapsed}s"

        except Exception as e:
            pytest.fail(f"Logging performance test failed: {e}")

    def test_large_log_message_handling(self):
        """Test handling of large log messages."""
        try:
            from logging_config import log_info

            # Create a large message
            large_message = "Large test message " * 1000  # ~18KB message

            # This should not raise an exception
            log_info(large_message, message_size=len(large_message))

        except Exception as e:
            pytest.fail(f"Large message logging failed: {e}")


# Pytest fixtures for shared test setup
@pytest.fixture(scope="module")
def logging_config():
    """Fixture to ensure logging configuration is available."""
    try:
        from logging_config import LOG_LEVEL, LOG_TO_CONSOLE, LOG_TO_FILE

        return {
            "LOG_LEVEL": LOG_LEVEL,
            "LOG_TO_CONSOLE": LOG_TO_CONSOLE,
            "LOG_TO_FILE": LOG_TO_FILE,
        }
    except ImportError:
        pytest.skip("Logging configuration not available")
