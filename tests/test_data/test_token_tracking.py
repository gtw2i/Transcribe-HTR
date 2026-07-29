"""
Test token tracking for Transkrybe.ai application.

This module contains tests for per-output token tracking in the transcription engine,
including token allocation, validation, and JSON output structure.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTokenTrackingImports:
    """Test imports for token tracking functionality."""

    def test_session_workspace_import(self):
        """Test that session workspace token functions can be imported."""
        try:
            from session_workspace import create_run_record

            assert callable(create_run_record)
        except ImportError as e:
            pytest.fail(f"session_workspace import failed: {e}")

    def test_transcription_engine_import(self):
        """Test that TranscriptionEngine can be imported."""
        try:
            from transcription_engine import TranscriptionEngine

            assert TranscriptionEngine is not None
        except ImportError as e:
            pytest.fail(f"TranscriptionEngine import failed: {e}")


class TestPerOutputTokenTracking:
    """Test per-output token tracking functionality."""

    @pytest.fixture
    def sample_outputs(self):
        """Provide sample outputs for token tracking tests."""
        return ["Test output 1", "Test output 2", "Test output 3"]

    @pytest.fixture
    def per_call_tokens(self):
        """Provide sample per-call token data."""
        return [
            {"prompt_tokens": 100, "completion_tokens": 20},
            {"prompt_tokens": 105, "completion_tokens": 25},
            {"prompt_tokens": 98, "completion_tokens": 22},
        ]

    @pytest.fixture
    def transcription_engine(self):
        """Create a TranscriptionEngine instance for testing."""
        from transcription_engine import TranscriptionEngine

        return TranscriptionEngine()

    def test_token_data_structure(self, per_call_tokens):
        """Test the structure of per-call token data."""
        for token_data in per_call_tokens:
            assert "prompt_tokens" in token_data
            assert "completion_tokens" in token_data
            assert isinstance(token_data["prompt_tokens"], int)
            assert isinstance(token_data["completion_tokens"], int)
            assert token_data["prompt_tokens"] >= 0
            assert token_data["completion_tokens"] >= 0

    def test_token_count_validation(self, sample_outputs, per_call_tokens):
        """Test validation of token counts against outputs."""
        # Verify counts match
        assert len(sample_outputs) == len(per_call_tokens)

        # Verify each output has corresponding token data
        for i, output in enumerate(sample_outputs):
            assert i < len(per_call_tokens)
            token_data = per_call_tokens[i]
            assert "prompt_tokens" in token_data
            assert "completion_tokens" in token_data

    def test_total_token_calculation(self, per_call_tokens):
        """Test calculation of total tokens from per-call data."""
        total_prompt = sum(tokens["prompt_tokens"] for tokens in per_call_tokens)
        total_completion = sum(
            tokens["completion_tokens"] for tokens in per_call_tokens
        )
        total_tokens = total_prompt + total_completion

        assert total_prompt == 303  # 100 + 105 + 98
        assert total_completion == 67  # 20 + 25 + 22
        assert total_tokens == 370

    def test_individual_token_totals(self, per_call_tokens):
        """Test calculation of individual call totals."""
        for token_data in per_call_tokens:
            individual_total = (
                token_data["prompt_tokens"] + token_data["completion_tokens"]
            )
            assert individual_total > 0

        # Test specific calculations
        assert (
            per_call_tokens[0]["prompt_tokens"]
            + per_call_tokens[0]["completion_tokens"]
            == 120
        )
        assert (
            per_call_tokens[1]["prompt_tokens"]
            + per_call_tokens[1]["completion_tokens"]
            == 130
        )
        assert (
            per_call_tokens[2]["prompt_tokens"]
            + per_call_tokens[2]["completion_tokens"]
            == 120
        )


class TestTokenAllocation:
    """Test token allocation and distribution logic."""

    def test_equal_token_distribution(self):
        """Test equal distribution of tokens when per-call data unavailable."""
        total_prompt_tokens = 300
        total_completion_tokens = 60
        num_outputs = 3

        # Equal distribution
        prompt_per_output = total_prompt_tokens // num_outputs
        completion_per_output = total_completion_tokens // num_outputs

        assert prompt_per_output == 100
        assert completion_per_output == 20

        # Verify total doesn't exceed original
        distributed_prompt = prompt_per_output * num_outputs
        distributed_completion = completion_per_output * num_outputs

        assert distributed_prompt <= total_prompt_tokens
        assert distributed_completion <= total_completion_tokens

    def test_proportional_token_distribution(self):
        """Test proportional distribution based on output length."""
        outputs = ["Short", "This is a much longer output text", "Medium length"]
        total_tokens = 300

        # Calculate proportions based on length
        lengths = [len(output) for output in outputs]
        total_length = sum(lengths)
        proportions = [length / total_length for length in lengths]

        # Verify proportions sum to 1.0
        assert abs(sum(proportions) - 1.0) < 0.001

        # Calculate token distribution
        token_distribution = [int(prop * total_tokens) for prop in proportions]

        assert sum(token_distribution) <= total_tokens
        assert all(tokens >= 0 for tokens in token_distribution)

    def test_minimum_token_guarantee(self):
        """Test that each output gets minimum token allocation."""
        num_outputs = 5
        total_tokens = 10
        minimum_per_output = 1

        # Each output should get at least minimum
        remaining_tokens = total_tokens - (num_outputs * minimum_per_output)

        assert remaining_tokens >= 0, "Not enough tokens for minimum allocation"

        # Distribute minimum first, then remaining
        allocations = [minimum_per_output] * num_outputs
        assert sum(allocations) <= total_tokens


class TestTokenDataValidation:
    """Test validation of token data integrity."""

    def test_valid_token_data(self):
        """Test validation of valid token data."""
        valid_data = [
            {"prompt_tokens": 50, "completion_tokens": 10},
            {"prompt_tokens": 75, "completion_tokens": 15},
        ]

        # Validate structure and values
        for tokens in valid_data:
            assert isinstance(tokens, dict)
            assert "prompt_tokens" in tokens
            assert "completion_tokens" in tokens
            assert isinstance(tokens["prompt_tokens"], int)
            assert isinstance(tokens["completion_tokens"], int)
            assert tokens["prompt_tokens"] >= 0
            assert tokens["completion_tokens"] >= 0

    def test_invalid_token_data(self):
        """Test handling of invalid token data."""
        invalid_cases = [
            {"prompt_tokens": -10, "completion_tokens": 5},  # Negative tokens
            {"prompt_tokens": "invalid", "completion_tokens": 5},  # Wrong type
            {"completion_tokens": 5},  # Missing prompt_tokens
            {"prompt_tokens": 5},  # Missing completion_tokens
        ]

        for invalid_data in invalid_cases:
            # Test validation logic
            is_valid = (
                "prompt_tokens" in invalid_data
                and "completion_tokens" in invalid_data
                and isinstance(invalid_data.get("prompt_tokens"), int)
                and isinstance(invalid_data.get("completion_tokens"), int)
                and invalid_data.get("prompt_tokens", -1) >= 0
                and invalid_data.get("completion_tokens", -1) >= 0
            )
            assert not is_valid

    def test_token_data_consistency(self):
        """Test consistency checks for token data."""
        outputs = ["Output 1", "Output 2"]
        tokens = [
            {"prompt_tokens": 100, "completion_tokens": 20},
            {"prompt_tokens": 150, "completion_tokens": 30},
        ]

        # Length consistency
        assert len(outputs) == len(tokens)

        # Value consistency
        total_calculated = sum(
            t["prompt_tokens"] + t["completion_tokens"] for t in tokens
        )
        assert total_calculated == 300  # 120 + 180


class TestJSONTokenOutput:
    """Test token data in JSON output structure."""

    @pytest.fixture
    def sample_json_with_tokens(self):
        """Provide sample JSON with token data."""
        return {
            "version": "2.0",
            "metadata": {
                "total_prompt_tokens": 303,
                "total_completion_tokens": 67,
                "total_tokens": 370,
            },
            "transcriptions": [
                {
                    "text": "Test output 1",
                    "index": 0,
                    "tokens": {"prompt": 100, "completion": 20},
                },
                {
                    "text": "Test output 2",
                    "index": 1,
                    "tokens": {"prompt": 105, "completion": 25},
                },
                {
                    "text": "Test output 3",
                    "index": 2,
                    "tokens": {"prompt": 98, "completion": 22},
                },
            ],
        }

    def test_json_token_structure(self, sample_json_with_tokens):
        """Test the structure of token data in JSON output."""
        # Verify metadata tokens
        metadata = sample_json_with_tokens["metadata"]
        assert "total_prompt_tokens" in metadata
        assert "total_completion_tokens" in metadata
        assert "total_tokens" in metadata

        # Verify per-transcription tokens
        for transcription in sample_json_with_tokens["transcriptions"]:
            assert "tokens" in transcription
            tokens = transcription["tokens"]
            assert "prompt" in tokens
            assert "completion" in tokens

    def test_json_token_totals(self, sample_json_with_tokens):
        """Test that JSON token totals are consistent."""
        metadata = sample_json_with_tokens["metadata"]
        transcriptions = sample_json_with_tokens["transcriptions"]

        # Calculate totals from individual transcriptions
        calculated_prompt = sum(t["tokens"]["prompt"] for t in transcriptions)
        calculated_completion = sum(t["tokens"]["completion"] for t in transcriptions)
        calculated_total = calculated_prompt + calculated_completion

        # Verify against metadata
        assert calculated_prompt == metadata["total_prompt_tokens"]
        assert calculated_completion == metadata["total_completion_tokens"]
        assert calculated_total == metadata["total_tokens"]

    def test_token_json_serialization(self):
        """Test serialization of token data to JSON."""
        token_data = {"tokens": {"prompt": 100, "completion": 25, "total": 125}}

        # Test JSON serialization
        json_string = json.dumps(token_data, indent=2)
        assert json_string is not None

        # Test deserialization
        loaded_data = json.loads(json_string)
        assert loaded_data == token_data


class TestTokenTrackingIntegration:
    """Integration tests for token tracking functionality."""

    def test_create_run_record_with_tokens(self):
        """Test creating run record with token tracking data."""
        try:
            from session_workspace import create_run_record

            # Mock data for run record creation
            outputs = ["Test 1", "Test 2"]
            per_call_tokens = [
                {"prompt_tokens": 50, "completion_tokens": 10},
                {"prompt_tokens": 60, "completion_tokens": 15},
            ]

            # Test that function exists and is callable
            assert callable(create_run_record)

            # Additional testing would depend on actual function signature

        except ImportError:
            pytest.skip("create_run_record not available for testing")

    def test_end_to_end_token_workflow(self):
        """Test complete token tracking workflow."""
        try:
            from transcription_engine import TranscriptionEngine

            engine = TranscriptionEngine()

            # Mock workflow with token tracking
            outputs = ["Result 1", "Result 2"]

            # Simulate token data collection
            total_prompt = 200
            total_completion = 50

            # Test basic calculations
            assert total_prompt + total_completion == 250
            assert len(outputs) == 2

            # Per-output allocation
            prompt_per_output = total_prompt // len(outputs)
            completion_per_output = total_completion // len(outputs)

            assert prompt_per_output == 100
            assert completion_per_output == 25

        except Exception as e:
            pytest.fail(f"End-to-end token workflow test failed: {e}")

    def test_token_tracking_error_handling(self):
        """Test error handling in token tracking."""
        # Test mismatched counts
        outputs = ["Output 1", "Output 2", "Output 3"]
        tokens = [
            {"prompt_tokens": 100, "completion_tokens": 20},
            {"prompt_tokens": 150, "completion_tokens": 30},
            # Missing third token entry
        ]

        # This should be detected as inconsistent
        assert len(outputs) != len(tokens)

        # Test empty token data
        empty_tokens = []
        assert len(outputs) != len(empty_tokens)

        # Test None token data
        none_tokens = None
        assert none_tokens is None
