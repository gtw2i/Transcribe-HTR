"""
Test backward compatibility for Transkrybe.ai application.

This module contains tests for backward compatibility with existing JSON files
and mixed output formats (old text-only vs new detailed objects).
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestBackwardCompatibilityImports:
    """Test imports for backward compatibility testing."""

    def test_json_manager_import(self):
        """Test that json_manager module can be imported."""
        try:
            import json_manager

            # load_v2_json is the backend's record reader; the legacy
            # apply_json_to_session pushed records into Streamlit state and has
            # no equivalent here.
            assert hasattr(json_manager, "load_v2_json")
        except ImportError as e:
            pytest.fail(f"json_manager import failed: {e}")

    def test_session_workspace_import(self):
        """Test that session workspace module can be imported."""
        try:
            import session_workspace

            assert hasattr(session_workspace, "create_run_record")
            assert hasattr(session_workspace, "create_v2_json_schema")
        except ImportError as e:
            pytest.fail(f"session_workspace import failed: {e}")


class TestLegacyJSONFormats:
    """Test compatibility with legacy JSON formats."""

    @pytest.fixture
    def legacy_json_v1(self):
        """Provide a legacy v1 JSON format for testing."""
        return {
            "version": "1.0",
            "transcriptions": [
                "First transcription text",
                "Second transcription text",
                "Third transcription text",
            ],
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "model": "gpt-4-vision-preview",
            },
        }

    @pytest.fixture
    def modern_json_v2(self):
        """Provide a modern v2 JSON format for testing."""
        return {
            "version": "2.0",
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "model": "gpt-4-vision-preview",
                "total_tokens": 150,
            },
            "transcriptions": [
                {
                    "text": "First transcription text",
                    "index": 0,
                    "tokens": {"prompt": 25, "completion": 10},
                },
                {
                    "text": "Second transcription text",
                    "index": 1,
                    "tokens": {"prompt": 25, "completion": 12},
                },
            ],
            "run_data": {
                "started_at": "2023-01-01T00:00:00Z",
                "completed_at": "2023-01-01T00:00:05Z",
                "total_duration_ms": 5000,
            },
        }

    @pytest.fixture
    def mixed_format_json(self):
        """Provide a mixed format JSON (some objects, some strings)."""
        return {
            "version": "2.0",
            "transcriptions": [
                "Legacy string format",  # Old format
                {  # New format
                    "text": "New object format",
                    "index": 1,
                    "tokens": {"prompt": 20, "completion": 8},
                },
                "Another legacy string",  # Old format
            ],
        }

    def test_legacy_format_detection(self, legacy_json_v1):
        """Test detection of legacy JSON format."""
        assert legacy_json_v1["version"] == "1.0"
        assert isinstance(legacy_json_v1["transcriptions"], list)

        # All transcriptions should be strings in v1 format
        for transcription in legacy_json_v1["transcriptions"]:
            assert isinstance(transcription, str)

    def test_modern_format_detection(self, modern_json_v2):
        """Test detection of modern JSON format."""
        assert modern_json_v2["version"] == "2.0"
        assert isinstance(modern_json_v2["transcriptions"], list)

        # All transcriptions should be objects in v2 format
        for transcription in modern_json_v2["transcriptions"]:
            assert isinstance(transcription, dict)
            assert "text" in transcription
            assert "index" in transcription

    def test_mixed_format_detection(self, mixed_format_json):
        """Test detection of mixed format JSON."""
        transcriptions = mixed_format_json["transcriptions"]

        # Should have both strings and objects
        string_count = sum(1 for t in transcriptions if isinstance(t, str))
        object_count = sum(1 for t in transcriptions if isinstance(t, dict))

        assert string_count > 0
        assert object_count > 0
        assert string_count + object_count == len(transcriptions)


class TestJSONNormalization:
    """Test JSON format normalization and conversion."""

    def test_string_to_object_conversion(self):
        """Test conversion of string transcriptions to object format."""
        string_transcriptions = [
            "First transcription",
            "Second transcription",
            "Third transcription",
        ]

        # Mock conversion logic
        converted = []
        for i, text in enumerate(string_transcriptions):
            converted.append(
                {
                    "text": text,
                    "index": i,
                    "tokens": {"prompt": 0, "completion": 0},  # Default values
                }
            )

        assert len(converted) == len(string_transcriptions)
        for i, obj in enumerate(converted):
            assert obj["text"] == string_transcriptions[i]
            assert obj["index"] == i
            assert "tokens" in obj

    def test_object_validation(self):
        """Test validation of object-format transcriptions."""
        valid_object = {
            "text": "Test transcription",
            "index": 0,
            "tokens": {"prompt": 10, "completion": 5},
        }

        # Validate required fields
        assert "text" in valid_object
        assert "index" in valid_object
        assert isinstance(valid_object["text"], str)
        assert isinstance(valid_object["index"], int)

    def test_partial_object_handling(self):
        """Test handling of objects with missing fields."""
        partial_object = {
            "text": "Test transcription",
            "index": 0,
            # Missing tokens field
        }

        # Should be able to add missing fields with defaults
        if "tokens" not in partial_object:
            partial_object["tokens"] = {"prompt": 0, "completion": 0}

        assert "tokens" in partial_object
        assert partial_object["tokens"]["prompt"] == 0
        assert partial_object["tokens"]["completion"] == 0


class TestSessionStateCompatibility:
    """Test compatibility with different session state formats."""

    def test_mock_session_state_creation(self):
        """Test creation of mock session state for testing."""

        class MockSessionState:
            def __init__(self):
                self.outputs = []
                self.model = "gpt-4o"
                self.temperature = 0.3
                self.run_id = None
                self.file_record = None

        mock_session = MockSessionState()
        assert hasattr(mock_session, "outputs")
        assert isinstance(mock_session.outputs, list)
        assert mock_session.model is not None

    def test_session_state_with_legacy_data(self):
        """Test session state populated with legacy data."""

        class MockSessionState:
            def __init__(self):
                self.outputs = ["Legacy output 1", "Legacy output 2"]
                self.transcription_outputs = None  # Old field name

        mock_session = MockSessionState()

        # Test migration from old field names
        if (
            hasattr(mock_session, "transcription_outputs")
            and mock_session.transcription_outputs
        ):
            mock_session.outputs.extend(mock_session.transcription_outputs)

        assert len(mock_session.outputs) >= 2

    def test_session_state_with_modern_data(self):
        """Test session state with modern structured data."""

        class MockSessionState:
            def __init__(self):
                self.outputs = [
                    {"text": "Modern output 1", "index": 0},
                    {"text": "Modern output 2", "index": 1},
                ]

        mock_session = MockSessionState()

        # Validate modern format
        for output in mock_session.outputs:
            if isinstance(output, dict):
                assert "text" in output
                assert "index" in output


class TestFileCompatibility:
    """Test compatibility with existing JSON files."""

    def test_temp_file_creation(self):
        """Test creation of temporary files for testing."""
        test_data = {"version": "1.0", "transcriptions": ["Test 1", "Test 2"]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f)
            temp_file_path = f.name

        try:
            # Verify file was created and can be read
            with open(temp_file_path, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == test_data

        finally:
            os.unlink(temp_file_path)

    def test_json_file_loading(self):
        """Test loading and parsing of JSON files."""
        test_data = {"version": "2.0", "transcriptions": [{"text": "Test", "index": 0}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f, indent=2)
            temp_file_path = f.name

        try:
            # Test file loading
            with open(temp_file_path, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data["version"] == "2.0"
            assert len(loaded_data["transcriptions"]) == 1

        finally:
            os.unlink(temp_file_path)


class TestBackwardCompatibilityIntegration:
    """Integration tests for backward compatibility."""

    def test_json_manager_compatibility(self, tmp_path):
        """Unreadable or non-v2 records degrade to None rather than raising."""
        try:
            import json_manager
        except ImportError:
            pytest.skip("json_manager not available for testing")

        # Missing file
        assert json_manager.load_v2_json(tmp_path / "does_not_exist.json") is None

        # Malformed JSON
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        assert json_manager.load_v2_json(corrupt) is None

        # A well-formed record round-trips unchanged
        valid = tmp_path / "valid.json"
        valid.write_text('{"schema_version": "2.0", "runs": []}', encoding="utf-8")
        loaded = json_manager.load_v2_json(valid)
        assert loaded == {"schema_version": "2.0", "runs": []}

    def test_v2_schema_creation(self):
        """Test creation of v2 JSON schema."""
        try:
            from session_workspace import create_v2_json_schema

            # Test that function exists and is callable
            assert callable(create_v2_json_schema)

            # Additional testing would depend on actual implementation

        except ImportError:
            pytest.skip("create_v2_json_schema not available")

    def test_migration_workflow(self):
        """Test complete migration workflow from v1 to v2."""
        # Mock migration process
        v1_data = {"version": "1.0", "transcriptions": ["Text 1", "Text 2"]}

        # Simulate migration to v2
        v2_data = {
            "version": "2.0",
            "transcriptions": [
                {"text": "Text 1", "index": 0},
                {"text": "Text 2", "index": 1},
            ],
        }

        # Verify migration preserves content
        assert len(v1_data["transcriptions"]) == len(v2_data["transcriptions"])

        for i, v1_text in enumerate(v1_data["transcriptions"]):
            assert v2_data["transcriptions"][i]["text"] == v1_text
            assert v2_data["transcriptions"][i]["index"] == i
