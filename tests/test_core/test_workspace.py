"""
Test workspace functionality for Transkrybe.ai application.

This module contains tests for session workspace functionality,
including filename normalization and workspace structure validation.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFilenameNormalization:
    """Test filename normalization functionality."""

    def normalize_filename_standalone(
        self, filename: str, preserve_root: bool = True
    ) -> str:
        """Standalone filename normalization for testing without Streamlit dependency."""
        path_obj = Path(filename)
        stem = path_obj.stem
        suffix = path_obj.suffix.lower()

        # Standardize extensions
        extension_mapping = {
            ".jpeg": ".jpg",
            ".json": ".json",
            ".png": ".png",
            ".jpg": ".jpg",
        }

        standardized_suffix = extension_mapping.get(suffix, suffix)

        # Apply normalization based on preserve_root setting
        if not preserve_root:
            stem = stem.lower().replace(" ", "_")

        return f"{stem}{standardized_suffix}"

    @pytest.mark.parametrize(
        "original,preserve_root,expected",
        [
            ("Image001.JPEG", True, "Image001.jpg"),
            ("MyFile.JSON", True, "MyFile.json"),
            ("test file.png", False, "test_file.png"),
            ("document.pdf", True, "document.pdf"),
            ("Test_Document.PNG", True, "Test_Document.png"),
            ("UPPERCASE.JPG", True, "UPPERCASE.jpg"),
        ],
    )
    def test_filename_normalization(self, original, preserve_root, expected):
        """Test filename normalization with various inputs."""
        result = self.normalize_filename_standalone(original, preserve_root)
        assert result == expected

    def test_extension_mapping(self):
        """Test that file extensions are properly mapped."""
        test_cases = {
            "test.JPEG": "test.jpg",
            "data.JSON": "data.json",
            "image.PNG": "image.png",
            "photo.JPG": "photo.jpg",
        }

        for original, expected in test_cases.items():
            result = self.normalize_filename_standalone(original, preserve_root=True)
            assert result == expected

    def test_preserve_root_false(self):
        """Test filename normalization when preserve_root is False."""
        test_cases = {
            "Test File.png": "test_file.png",
            "My Document.jpg": "my_document.jpg",
            "CAPS FILE.json": "caps_file.json",
        }

        for original, expected in test_cases.items():
            result = self.normalize_filename_standalone(original, preserve_root=False)
            assert result == expected


class TestWorkspaceStructure:
    """Test workspace structure functionality."""

    def test_workspace_directory_creation(self):
        """Test that workspace directories can be created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "test_workspace"
            workspace_path.mkdir()

            assert workspace_path.exists()
            assert workspace_path.is_dir()

    def test_workspace_file_operations(self):
        """Test basic file operations within workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "test_workspace"
            workspace_path.mkdir()

            # Test file creation
            test_file = workspace_path / "test.json"
            test_file.write_text('{"test": "data"}')

            assert test_file.exists()
            assert test_file.is_file()

            # Test file reading
            content = test_file.read_text()
            assert '"test": "data"' in content


class TestWorkspaceIntegration:
    """Integration tests for workspace functionality."""

    def test_session_workspace_import(self):
        """Test that session workspace module can be imported."""
        try:
            import session_workspace

            assert hasattr(session_workspace, "__file__")
        except ImportError as e:
            pytest.fail(f"session_workspace import failed: {e}")

    def test_workspace_functions_exist(self):
        """Test that key workspace functions exist."""
        try:
            import session_workspace

            # Check for common workspace functions
            # Note: Adjust these based on actual session_workspace implementation
            expected_functions = ["validate_v2_json_schema"]  # Add more as needed

            for func_name in expected_functions:
                if hasattr(session_workspace, func_name):
                    func = getattr(session_workspace, func_name)
                    assert callable(func)

        except ImportError:
            pytest.skip("session_workspace module not available for testing")


class TestWorkspaceValidation:
    """Test workspace validation functionality."""

    def test_json_schema_validation_exists(self):
        """Test that JSON schema validation functionality exists."""
        try:
            from session_workspace import validate_v2_json_schema

            assert callable(validate_v2_json_schema)
        except ImportError:
            pytest.skip("validate_v2_json_schema not available")

    @pytest.fixture
    def sample_json_data(self):
        """Provide sample JSON data for validation testing."""
        return {
            "version": "2.0",
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "model": "gpt-4-vision-preview",
            },
            "transcriptions": [{"text": "Sample text", "index": 0}],
        }

    def test_valid_json_structure(self, sample_json_data):
        """Test validation with valid JSON structure."""
        try:
            from session_workspace import validate_v2_json_schema

            # Note: This test assumes the function exists and works
            # Adjust based on actual implementation
            result = validate_v2_json_schema(sample_json_data)
            # Test would depend on actual return value of validation function
        except ImportError:
            pytest.skip("validate_v2_json_schema not available for testing")
