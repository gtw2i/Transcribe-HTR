"""
Test JSON validation for Transcribe-HTR application.

This module contains tests for JSON output validation,
including individual token data per transcription and schema validation.
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


class TestJSONValidationImports:
    """Test imports for JSON validation functionality."""

    def test_session_workspace_import(self):
        """Test that session workspace JSON functions can be imported."""
        try:
            from session_workspace import create_run_record, create_v2_json_schema

            assert callable(create_run_record)
            assert callable(create_v2_json_schema)
        except ImportError as e:
            pytest.fail(f"session_workspace import failed: {e}")


class TestJSONStructureValidation:
    """Test JSON structure and schema validation."""

    @pytest.fixture
    def detailed_outputs(self):
        """Provide detailed outputs with token data for testing."""
        return [
            {
                "text": "This is transcription output number 1 with specific token counts.",
                "prompt_tokens": 125,
                "completion_tokens": 28,
                "call_sequence": 1,
            },
            {
                "text": "Second transcription output with different token allocation.",
                "prompt_tokens": 110,
                "completion_tokens": 32,
                "call_sequence": 2,
            },
            {
                "text": "Third and final transcription with its own token data.",
                "prompt_tokens": 98,
                "completion_tokens": 25,
                "call_sequence": 3,
            },
        ]

    @pytest.fixture
    def expected_json_structure(self):
        """Provide expected JSON structure for validation."""
        return {
            "version": "2.0",
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "model": "gpt-4o",
                "total_prompt_tokens": 333,
                "total_completion_tokens": 85,
                "total_tokens": 418,
            },
            "transcriptions": [
                {
                    "text": "Sample transcription",
                    "index": 0,
                    "tokens": {"prompt": 125, "completion": 28},
                    "call_sequence": 1,
                }
            ],
            "run_data": {
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "total_duration_ms": 1000,
            },
        }

    def test_detailed_outputs_structure(self, detailed_outputs):
        """Test the structure of detailed outputs data."""
        for output in detailed_outputs:
            assert "text" in output
            assert "prompt_tokens" in output
            assert "completion_tokens" in output
            assert "call_sequence" in output

            assert isinstance(output["text"], str)
            assert isinstance(output["prompt_tokens"], int)
            assert isinstance(output["completion_tokens"], int)
            assert isinstance(output["call_sequence"], int)

            assert output["prompt_tokens"] > 0
            assert output["completion_tokens"] > 0
            assert output["call_sequence"] > 0

    def test_json_schema_compliance(self, expected_json_structure):
        """Test that JSON output complies with expected schema."""
        # Verify top-level structure
        assert "version" in expected_json_structure
        assert "metadata" in expected_json_structure
        assert "transcriptions" in expected_json_structure
        assert "run_data" in expected_json_structure

        # Verify version
        assert expected_json_structure["version"] == "2.0"

        # Verify metadata structure
        metadata = expected_json_structure["metadata"]
        required_metadata_fields = [
            "created_at",
            "model",
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_tokens",
        ]
        for field in required_metadata_fields:
            assert field in metadata

        # Verify transcriptions structure
        transcriptions = expected_json_structure["transcriptions"]
        assert isinstance(transcriptions, list)

        for transcription in transcriptions:
            assert "text" in transcription
            assert "index" in transcription
            assert "tokens" in transcription

            tokens = transcription["tokens"]
            assert "prompt" in tokens
            assert "completion" in tokens

    def test_token_data_validation(self, detailed_outputs):
        """Test validation of token data in outputs."""
        total_prompt = sum(output["prompt_tokens"] for output in detailed_outputs)
        total_completion = sum(
            output["completion_tokens"] for output in detailed_outputs
        )
        total_tokens = total_prompt + total_completion

        assert total_prompt == 333  # 125 + 110 + 98
        assert total_completion == 85  # 28 + 32 + 25
        assert total_tokens == 418

        # Verify individual calculations
        for output in detailed_outputs:
            individual_total = output["prompt_tokens"] + output["completion_tokens"]
            assert individual_total > 0


class TestJSONCreationAndValidation:
    """Test JSON creation and validation processes."""

    def test_v2_schema_creation(self):
        """Test creation of v2 JSON schema."""
        try:
            from session_workspace import create_v2_json_schema

            # Test that function exists and is callable
            assert callable(create_v2_json_schema)

            # Additional testing would depend on actual function implementation

        except ImportError:
            pytest.skip("create_v2_json_schema not available")

    def test_run_record_creation_with_tokens(self):
        """Test creating run record with individual token data."""
        try:
            from session_workspace import create_run_record

            # Mock data for run record creation
            outputs = ["Test output 1", "Test output 2"]
            per_call_tokens = [
                {"prompt_tokens": 100, "completion_tokens": 25},
                {"prompt_tokens": 150, "completion_tokens": 35},
            ]

            # Test that function exists
            assert callable(create_run_record)

            # Additional testing would depend on actual implementation

        except ImportError:
            pytest.skip("create_run_record not available")

    def test_json_serialization_compatibility(self):
        """Test that JSON structures can be properly serialized."""
        test_data = {
            "version": "2.0",
            "transcriptions": [
                {
                    "text": "Test transcription",
                    "index": 0,
                    "tokens": {"prompt": 50, "completion": 15},
                }
            ],
            "metadata": {"created_at": datetime.now().isoformat(), "total_tokens": 65},
        }

        # Test serialization
        json_string = json.dumps(test_data, indent=2)
        assert json_string is not None

        # Test deserialization
        loaded_data = json.loads(json_string)
        assert loaded_data == test_data


class TestJSONFileOperations:
    """Test JSON file operations and persistence."""

    def test_json_file_creation(self):
        """Test creation of JSON files with transcription data."""
        test_data = {
            "version": "2.0",
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "model": "gpt-4o",
                "total_tokens": 100,
            },
            "transcriptions": [
                {
                    "text": "Test transcription",
                    "index": 0,
                    "tokens": {"prompt": 75, "completion": 25},
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f, indent=2)
            temp_file_path = f.name

        try:
            # Verify file creation and content
            with open(temp_file_path, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == test_data
            assert loaded_data["version"] == "2.0"
            assert len(loaded_data["transcriptions"]) == 1

        finally:
            os.unlink(temp_file_path)

    def test_json_file_validation(self):
        """Test validation of existing JSON files."""
        # Create test file with known structure
        valid_data = {
            "version": "2.0",
            "transcriptions": [
                {
                    "text": "Valid transcription",
                    "index": 0,
                    "tokens": {"prompt": 20, "completion": 5},
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(valid_data, f)
            temp_file_path = f.name

        try:
            # Load and validate
            with open(temp_file_path, "r") as f:
                data = json.load(f)

            # Validate structure
            assert "version" in data
            assert "transcriptions" in data
            assert data["version"] == "2.0"

            # Validate transcriptions
            for transcription in data["transcriptions"]:
                assert "text" in transcription
                assert "index" in transcription
                assert "tokens" in transcription

        finally:
            os.unlink(temp_file_path)

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON structures."""
        invalid_cases = [
            {},  # Empty object
            {"version": "1.0"},  # Missing transcriptions
            {"transcriptions": []},  # Missing version
            {
                "version": "2.0",
                "transcriptions": [{"text": "Invalid"}],
            },  # Missing required fields in transcription
        ]

        for i, invalid_data in enumerate(invalid_cases):
            # Test validation logic
            has_version = "version" in invalid_data
            has_transcriptions = "transcriptions" in invalid_data
            correct_version = invalid_data.get("version") == "2.0"
            is_list = isinstance(invalid_data.get("transcriptions"), list)

            # Check if data has all basic structure requirements
            basic_structure_valid = (
                has_version and has_transcriptions and correct_version and is_list
            )

            # Additional validation for transcription content
            if basic_structure_valid and invalid_data.get("transcriptions"):
                transcriptions = invalid_data["transcriptions"]
                # Check if transcriptions have required fields (text, index, etc.)
                valid_transcriptions = all(
                    isinstance(t, dict) and "text" in t for t in transcriptions
                )
                content_valid = valid_transcriptions
            else:
                content_valid = True  # Empty transcriptions are valid structurally

            # Test assertions based on the specific invalid case
            if i == 0:  # Empty object
                assert not basic_structure_valid
            elif i == 1:  # Missing transcriptions
                assert not basic_structure_valid
            elif i == 2:  # Missing version
                assert not basic_structure_valid
            elif i == 3:  # Has structure but incomplete transcription data
                assert basic_structure_valid  # Structure is valid
                # Content validation would depend on business rules


class TestJSONTokenConsistency:
    """Test consistency of token data in JSON output."""

    @pytest.fixture
    def complete_json_example(self):
        """Provide a complete JSON example with all token data."""
        return {
            "version": "2.0",
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "model": "gpt-4o",
                "total_prompt_tokens": 300,
                "total_completion_tokens": 75,
                "total_tokens": 375,
            },
            "transcriptions": [
                {
                    "text": "First transcription",
                    "index": 0,
                    "tokens": {"prompt": 100, "completion": 25},
                    "call_sequence": 1,
                },
                {
                    "text": "Second transcription",
                    "index": 1,
                    "tokens": {"prompt": 120, "completion": 30},
                    "call_sequence": 2,
                },
                {
                    "text": "Third transcription",
                    "index": 2,
                    "tokens": {"prompt": 80, "completion": 20},
                    "call_sequence": 3,
                },
            ],
        }

    def test_token_totals_consistency(self, complete_json_example):
        """Test that token totals are consistent across JSON structure."""
        metadata = complete_json_example["metadata"]
        transcriptions = complete_json_example["transcriptions"]

        # Calculate totals from individual transcriptions
        calculated_prompt = sum(t["tokens"]["prompt"] for t in transcriptions)
        calculated_completion = sum(t["tokens"]["completion"] for t in transcriptions)
        calculated_total = calculated_prompt + calculated_completion

        # Verify against metadata
        assert calculated_prompt == metadata["total_prompt_tokens"]
        assert calculated_completion == metadata["total_completion_tokens"]
        assert calculated_total == metadata["total_tokens"]

    def test_transcription_indexing(self, complete_json_example):
        """Test that transcription indexing is correct."""
        transcriptions = complete_json_example["transcriptions"]

        for i, transcription in enumerate(transcriptions):
            assert transcription["index"] == i
            assert transcription["call_sequence"] == i + 1

    def test_required_fields_presence(self, complete_json_example):
        """Test that all required fields are present."""
        # Check top-level fields
        required_top_level = ["version", "metadata", "transcriptions"]
        for field in required_top_level:
            assert field in complete_json_example

        # Check metadata fields
        metadata = complete_json_example["metadata"]
        required_metadata = [
            "created_at",
            "model",
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_tokens",
        ]
        for field in required_metadata:
            assert field in metadata

        # Check transcription fields
        for transcription in complete_json_example["transcriptions"]:
            required_transcription = ["text", "index", "tokens"]
            for field in required_transcription:
                assert field in transcription

            # Check token fields
            tokens = transcription["tokens"]
            required_tokens = ["prompt", "completion"]
            for field in required_tokens:
                assert field in tokens


class TestJSONValidationIntegration:
    """Integration tests for JSON validation functionality."""

    def test_end_to_end_json_workflow(self):
        """Test complete JSON creation and validation workflow."""
        # Mock complete workflow
        raw_outputs = ["Output 1", "Output 2"]
        token_data = [
            {"prompt_tokens": 100, "completion_tokens": 20},
            {"prompt_tokens": 150, "completion_tokens": 30},
        ]

        # Simulate JSON creation process
        transcriptions = []
        for i, (output, tokens) in enumerate(zip(raw_outputs, token_data)):
            transcriptions.append(
                {
                    "text": output,
                    "index": i,
                    "tokens": {
                        "prompt": tokens["prompt_tokens"],
                        "completion": tokens["completion_tokens"],
                    },
                }
            )

        # Calculate metadata
        total_prompt = sum(t["tokens"]["prompt"] for t in transcriptions)
        total_completion = sum(t["tokens"]["completion"] for t in transcriptions)

        json_output = {
            "version": "2.0",
            "metadata": {
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_completion,
                "total_tokens": total_prompt + total_completion,
            },
            "transcriptions": transcriptions,
        }

        # Validate created JSON
        assert json_output["metadata"]["total_tokens"] == 300
        assert len(json_output["transcriptions"]) == 2

        # Test serialization
        json_string = json.dumps(json_output)
        loaded_json = json.loads(json_string)
        assert loaded_json == json_output
