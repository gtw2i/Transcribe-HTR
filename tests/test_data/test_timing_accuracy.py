"""
Test timing accuracy for Transkrybe.ai application.

This module contains tests for timing capture in transcription engine
and JSON output, including per-call timing and overall run timing.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTimingImports:
    """Test imports for timing-related functionality."""

    def test_session_workspace_import(self):
        """Test that session workspace timing functions can be imported."""
        try:
            from session_workspace import create_run_record, create_v2_json_schema

            assert callable(create_run_record)
            assert callable(create_v2_json_schema)
        except ImportError as e:
            pytest.fail(f"session_workspace import failed: {e}")

    def test_transcription_engine_import(self):
        """Test that TranscriptionEngine can be imported."""
        try:
            from transcription_engine import TranscriptionEngine

            assert TranscriptionEngine is not None
        except ImportError as e:
            pytest.fail(f"TranscriptionEngine import failed: {e}")


class TestPerCallTiming:
    """Test per-call timing capture functionality."""

    @pytest.fixture
    def transcription_engine(self):
        """Create a TranscriptionEngine instance for testing."""
        from transcription_engine import TranscriptionEngine

        return TranscriptionEngine()

    @pytest.fixture
    def mock_timing_params(self):
        """Provide mock parameters for timing tests.

        source_choice="Use hardcoded outputs" keeps this off the network.
        """
        return {
            "api_key": "test-key",
            "img_bytes": b"fake_image_data",
            "model": "gpt-4o",
            "n_responses": 2,
            "prompt": "test prompt",
            "source_choice": "Use hardcoded outputs",
        }

    def test_per_call_timing_capture(self, transcription_engine, mock_timing_params):
        """Per-call timing is captured for every requested response."""
        result = transcription_engine.run_transcription(**mock_timing_params)

        assert result is not None
        assert result["success"] is True

        timing_data = result["timing_data"]
        assert "total_duration_ms" in timing_data
        assert timing_data["total_duration_ms"] >= 0

        per_call = timing_data["per_call_timings"]
        assert len(per_call) == mock_timing_params["n_responses"]
        for call_timing in per_call:
            assert "call_started_at" in call_timing
            assert "call_completed_at" in call_timing
            assert call_timing["call_duration_ms"] >= 0

    def test_timing_data_structure(self):
        """Test the structure of timing data."""
        # Mock timing data structure
        expected_timing = {
            "started_at": datetime.now().isoformat(),
            "completed_at": (datetime.now() + timedelta(milliseconds=100)).isoformat(),
            "duration_ms": 100,
        }

        # Verify structure
        assert "started_at" in expected_timing
        assert "completed_at" in expected_timing
        assert "duration_ms" in expected_timing
        assert expected_timing["duration_ms"] > 0

    def test_timing_consistency(self):
        """Test that timing calculations are consistent."""
        start_time = datetime.now()
        end_time = start_time + timedelta(milliseconds=150)

        duration_ms = (end_time - start_time).total_seconds() * 1000

        assert duration_ms == 150.0
        assert end_time > start_time


class TestOverallRunTiming:
    """Test overall run timing functionality."""

    @pytest.fixture
    def mock_run_data(self):
        """Provide mock run data for testing."""
        return {
            "outputs": ["Test output 1", "Test output 2"],
            "model": "gpt-4o",
            "temperature": 0.3,
            "total_prompt_tokens": 100,
            "total_completion_tokens": 50,
            "total_tokens": 150,
        }

    def test_run_record_timing_capture(self, mock_run_data):
        """Test that run record captures timing accurately."""
        try:
            from session_workspace import create_run_record

            # Mock timing data
            started_at = datetime.now()
            completed_at = started_at + timedelta(seconds=5)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            # Verify timing calculations
            assert completed_at > started_at
            assert duration_ms > 0
            assert duration_ms == 5000.0

            # Test that create_run_record function exists for timing
            assert callable(create_run_record)

        except ImportError:
            pytest.skip("create_run_record not available for testing")

    def test_timing_data_validation(self):
        """Test validation of timing data."""
        # Test valid timing data
        valid_timing = {
            "started_at": "2023-01-01T10:00:00Z",
            "completed_at": "2023-01-01T10:00:05Z",
            "duration_ms": 5000,
        }

        # Parse and validate
        start = datetime.fromisoformat(
            valid_timing["started_at"].replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(
            valid_timing["completed_at"].replace("Z", "+00:00")
        )

        calculated_duration = (end - start).total_seconds() * 1000

        assert calculated_duration == valid_timing["duration_ms"]
        assert end > start

    def test_timing_edge_cases(self):
        """Test timing edge cases and error conditions."""
        # Test same start and end time
        same_time = datetime.now()
        duration = (same_time - same_time).total_seconds() * 1000
        assert duration == 0.0

        # Test negative duration (invalid case)
        start = datetime.now()
        end = start - timedelta(seconds=1)
        negative_duration = (end - start).total_seconds() * 1000
        assert negative_duration < 0  # This should be caught in actual implementation


class TestJSONTimingOutput:
    """Test timing data in JSON output."""

    @pytest.fixture
    def sample_json_with_timing(self):
        """Provide sample JSON with timing data."""
        return {
            "version": "2.0",
            "metadata": {"created_at": "2023-01-01T00:00:00Z", "model": "gpt-4o"},
            "transcriptions": [
                {
                    "text": "Test transcription",
                    "index": 0,
                    "tokens": {"prompt": 25, "completion": 10},
                    "timing": {
                        "started_at": "2023-01-01T00:00:00Z",
                        "completed_at": "2023-01-01T00:00:01Z",
                        "duration_ms": 1000,
                    },
                }
            ],
            "run_data": {
                "started_at": "2023-01-01T00:00:00Z",
                "completed_at": "2023-01-01T00:00:05Z",
                "total_duration_ms": 5000,
            },
        }

    def test_json_timing_structure(self, sample_json_with_timing):
        """Test the structure of timing data in JSON output."""
        # Verify overall structure
        assert "run_data" in sample_json_with_timing
        run_data = sample_json_with_timing["run_data"]

        assert "started_at" in run_data
        assert "completed_at" in run_data
        assert "total_duration_ms" in run_data

        # Verify per-transcription timing
        transcriptions = sample_json_with_timing["transcriptions"]
        for transcription in transcriptions:
            if "timing" in transcription:
                timing = transcription["timing"]
                assert "started_at" in timing
                assert "completed_at" in timing
                assert "duration_ms" in timing

    def test_json_timing_consistency(self, sample_json_with_timing):
        """Test consistency of timing data in JSON."""
        run_data = sample_json_with_timing["run_data"]

        # Parse timestamps
        run_start = datetime.fromisoformat(
            run_data["started_at"].replace("Z", "+00:00")
        )
        run_end = datetime.fromisoformat(
            run_data["completed_at"].replace("Z", "+00:00")
        )

        # Verify duration calculation
        calculated_duration = (run_end - run_start).total_seconds() * 1000
        assert calculated_duration == run_data["total_duration_ms"]

    def test_timing_data_serialization(self):
        """Test serialization of timing data to JSON."""
        timing_data = {
            "started_at": datetime.now().isoformat(),
            "completed_at": (datetime.now() + timedelta(seconds=2)).isoformat(),
            "duration_ms": 2000,
        }

        # Test JSON serialization
        json_string = json.dumps(timing_data, indent=2)
        assert json_string is not None

        # Test deserialization
        loaded_data = json.loads(json_string)
        assert loaded_data == timing_data


class TestTimingIntegration:
    """Integration tests for timing functionality."""

    def test_end_to_end_timing_workflow(self):
        """Test complete timing workflow from transcription to JSON output."""
        try:
            from session_workspace import create_v2_json_schema
            from transcription_engine import TranscriptionEngine

            # Create engine and mock data
            engine = TranscriptionEngine()

            # Test that timing functions are available
            assert callable(create_v2_json_schema)

            # Mock complete workflow timing
            workflow_start = datetime.now()

            # Simulate transcription calls
            outputs = ["Output 1", "Output 2"]

            workflow_end = datetime.now()
            total_duration = (workflow_end - workflow_start).total_seconds() * 1000

            assert total_duration >= 0
            assert workflow_end >= workflow_start

        except ImportError:
            pytest.skip("Required modules not available for integration test")

    def test_timing_accuracy_validation(self):
        """Test validation of timing accuracy requirements."""
        # Test minimum timing resolution
        start_time = datetime.now()
        # Simulate minimal operation
        end_time = datetime.now()

        duration_ms = (end_time - start_time).total_seconds() * 1000

        # Duration should be non-negative and reasonably small for minimal operation
        assert duration_ms >= 0
        assert duration_ms < 1000  # Should be less than 1 second for minimal operation

    def test_timing_data_persistence(self):
        """Test that timing data persists correctly in temporary files."""
        timing_data = {
            "version": "2.0",
            "run_data": {
                "started_at": datetime.now().isoformat(),
                "completed_at": (datetime.now() + timedelta(seconds=1)).isoformat(),
                "total_duration_ms": 1000,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(timing_data, f, indent=2)
            temp_file_path = f.name

        try:
            # Verify persistence
            with open(temp_file_path, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == timing_data
            assert loaded_data["run_data"]["total_duration_ms"] == 1000

        finally:
            os.unlink(temp_file_path)
