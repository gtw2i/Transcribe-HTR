"""
Shared test fixtures and configuration for audio system tests.

This module provides:
- Common test fixtures
- Mock data generators
- Test utilities and helpers
- Audio system test configuration
"""

import io
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock

import pytest

# Test configuration constants
TEST_TTS_MODELS = ["tts-1", "tts-1-hd"]
TEST_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
TEST_AUDIO_FORMATS = [".wav", ".mp3", ".m4a", ".ogg"]
TEST_SAMPLE_TRANSCRIPTIONS = [
    "The Battle of Gettysburg was fought July 1–3, 1863.",
    "Dear Mother, I write to you from the encampment near Richmond.",
    "The regiment marched through Virginia in the autumn of 1864.",
]


@pytest.fixture(scope="session")
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="transkrybe_test_")
    workspace_path = Path(temp_dir)

    # Create standard directory structure
    (workspace_path / "tmp" / "audio").mkdir(parents=True)
    (workspace_path / "workspace").mkdir(parents=True)
    (workspace_path / "logs").mkdir(parents=True)

    yield workspace_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def isolated_workspace(temp_workspace):
    """Create an isolated workspace for each test."""
    test_dir = temp_workspace / f"test_{pytest.current_pytest_case_id}"
    test_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (test_dir / "tmp" / "audio").mkdir(parents=True, exist_ok=True)
    (test_dir / "workspace").mkdir(parents=True, exist_ok=True)

    yield test_dir

    # Cleanup after test
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for TTS testing."""
    mock_client = Mock()

    # Mock TTS audio response
    mock_response = Mock()
    mock_response.content = b"fake_tts_audio_data_" + b"x" * 1000  # Simulate audio data
    mock_response.response.headers = {"content-type": "audio/wav"}

    mock_client.audio.speech.create.return_value = mock_response

    return mock_client


class AudioTestDataGenerator:
    """Generate test data for audio system testing."""

    @staticmethod
    def create_fake_audio_file(
        path: Path, metadata: Optional[Dict] = None, audio_size: int = 1024
    ) -> Path:
        """Create a fake audio file with optional metadata."""
        # Create fake audio data
        audio_data = b"FAKE_AUDIO_" + b"x" * (audio_size - 11)
        path.write_bytes(audio_data)

        # Create metadata file if provided
        if metadata:
            metadata_path = path.with_suffix(".json")
            metadata_path.write_text(json.dumps(metadata, indent=2))

        return path

    @staticmethod
    def create_tts_cache_files(cache_dir: Path, count: int = 3) -> List[Dict]:
        """Create fake TTS cache files for testing."""
        cache_files = []

        for i in range(count):
            hash_id = f"hash{i:03d}"
            audio_path = cache_dir / f"{hash_id}.wav"

            metadata = {
                "source": "tts_generated",
                "voice": TEST_TTS_VOICES[i % len(TEST_TTS_VOICES)],
                "model": TEST_TTS_MODELS[i % len(TEST_TTS_MODELS)],
                "original_text": TEST_SAMPLE_TRANSCRIPTIONS[
                    i % len(TEST_SAMPLE_TRANSCRIPTIONS)
                ],
                "timestamp": f"2025-01-01T{10+i:02d}:00:00",
                "duration_seconds": 5.0 + i,
                "cost_estimate": 0.01 * (i + 1),
            }

            AudioTestDataGenerator.create_fake_audio_file(
                audio_path, metadata, audio_size=1024 * (i + 1)
            )

            cache_files.append(
                {"path": audio_path, "metadata": metadata, "hash_id": hash_id}
            )

        return cache_files

    @staticmethod
    def create_uploaded_audio_files(workspace_dir: Path, count: int = 2) -> List[Dict]:
        """Create fake uploaded audio files for testing."""
        uploaded_files = []

        filenames = [
            "civil_war_letter.wav",
            "battle_report.mp3",
            "soldier_diary.m4a",
            "historical_document.ogg",
        ]

        for i in range(min(count, len(filenames))):
            filename = filenames[i]
            audio_path = workspace_dir / filename

            metadata = {
                "source": "uploaded",
                "original_filename": filename,
                "upload_timestamp": f"2025-01-01T{12+i:02d}:30:00",
                "size_bytes": 2048 * (i + 1),
            }

            AudioTestDataGenerator.create_fake_audio_file(
                audio_path, metadata, audio_size=metadata["size_bytes"]
            )

            uploaded_files.append(
                {"path": audio_path, "metadata": metadata, "filename": filename}
            )

        return uploaded_files

    @staticmethod
    def create_mock_uploaded_file(filename: str, content: bytes) -> Mock:
        """Create a mock uploaded file (name/read/size/type)."""
        mock_file = Mock()
        mock_file.name = filename
        mock_file.read.return_value = content
        mock_file.size = len(content)
        mock_file.type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"

        return mock_file


@pytest.fixture
def audio_test_data():
    """Provide audio test data generator."""
    return AudioTestDataGenerator


@pytest.fixture
def sample_transcriptions():
    """Provide sample Civil War transcriptions for testing."""
    return TEST_SAMPLE_TRANSCRIPTIONS.copy()


@pytest.fixture
def tts_test_config():
    """Provide TTS testing configuration."""
    return {
        "models": TEST_TTS_MODELS,
        "voices": TEST_TTS_VOICES,
        "test_api_key": "sk-test-key-for-testing-only",
        "cache_ttl_hours": 24,
        "max_text_length": 4096,
    }


@pytest.fixture
def audio_format_config():
    """Provide audio format testing configuration."""
    return {
        "supported_formats": TEST_AUDIO_FORMATS,
        "max_file_size_mb": 25,
        "sample_rates": [22050, 44100, 48000],
        "bit_depths": [16, 24, 32],
    }


class MockAudioUtils:
    """Mock audio utilities for testing."""

    @staticmethod
    def mock_validate_audio_file(filepath: Path) -> Dict[str, Any]:
        """Mock audio file validation."""
        return {
            "valid": True,
            "format": filepath.suffix.lower()[1:],  # Remove dot
            "duration_seconds": 5.2,
            "sample_rate": 44100,
            "channels": 1,
        }

    @staticmethod
    def mock_get_audio_duration(filepath: Path) -> float:
        """Mock audio duration calculation."""
        # Base duration on file size for predictable testing
        try:
            size = filepath.stat().st_size
            return max(1.0, size / 1000)  # Roughly 1 second per KB
        except:
            return 5.0  # Default duration


class MockTTSEngine:
    """Mock TTS engine for testing."""

    def __init__(self, api_key: str = "test-key"):
        self.api_key = api_key
        self.generation_count = 0

    def generate_speech(
        self, text: str, voice: str = "alloy", model: str = "tts-1"
    ) -> Dict[str, Any]:
        """Mock speech generation."""
        self.generation_count += 1

        # Simulate different responses
        if "error" in text.lower():
            return {"success": False, "error": "Simulated TTS error"}

        # Generate fake audio data
        audio_data = f"FAKE_TTS_{voice}_{model}_{len(text)}".encode() + b"x" * 1000

        return {
            "success": True,
            "audio_data": audio_data,
            "metadata": {
                "voice": voice,
                "model": model,
                "text_length": len(text),
                "timestamp": "2025-01-01T12:00:00",
                "duration_seconds": len(text) / 20,  # Rough estimate
            },
            "cache_hit": False,
            "cost_estimate": 0.015,
        }

    def validate_api_key(self) -> bool:
        """Mock API key validation."""
        return self.api_key.startswith("sk-")


@pytest.fixture
def mock_tts_engine():
    """Provide mock TTS engine."""
    return MockTTSEngine()


@pytest.fixture
def mock_audio_utils():
    """Provide mock audio utilities."""
    return MockAudioUtils()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for audio system testing."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may be slower)"
    )
    config.addinivalue_line(
        "markers", "tts_api: marks tests that would make actual TTS API calls"
    )
    config.addinivalue_line(
        "markers", "file_operations: marks tests that perform file system operations"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection."""
    # Add markers based on test names and locations
    for item in items:
        # Mark integration tests
        if "integration" in item.name.lower() or "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark TTS API tests
        if "tts" in item.name.lower() and "api" in item.name.lower():
            item.add_marker(pytest.mark.tts_api)

        # Mark file operation tests
        if any(
            keyword in item.name.lower()
            for keyword in ["file", "save", "load", "cache"]
        ):
            item.add_marker(pytest.mark.file_operations)


# Test utilities
class TestAssertions:
    """Custom assertions for audio system testing."""

    @staticmethod
    def assert_valid_audio_metadata(metadata: Dict[str, Any]):
        """Assert that audio metadata has required fields."""
        required_fields = ["source", "timestamp"]
        for field in required_fields:
            assert field in metadata, f"Missing required metadata field: {field}"

    @staticmethod
    def assert_valid_tts_response(response: Dict[str, Any]):
        """Assert that TTS response has correct structure."""
        assert "success" in response

        if response["success"]:
            assert "audio_data" in response
            assert "metadata" in response
            assert isinstance(response["audio_data"], bytes)
        else:
            assert "error" in response

    @staticmethod
    def assert_audio_file_exists(filepath: Path):
        """Assert that audio file exists and has content."""
        assert filepath.exists(), f"Audio file does not exist: {filepath}"
        assert filepath.stat().st_size > 0, f"Audio file is empty: {filepath}"


@pytest.fixture
def test_assertions():
    """Provide test assertion utilities."""
    return TestAssertions
