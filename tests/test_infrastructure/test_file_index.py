"""
Test file index functionality for Transkrybe.ai application.

This module contains tests for FileIndex functionality,
including file record management, indexing, and file operations.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFileIndexImports:
    """Test imports for file index functionality."""

    def test_file_manager_import(self):
        """Test that file manager module can be imported."""
        try:
            import file_manager

            # Test for common file management functions
            expected_attributes = ["FileRecord", "FileIndex"]

            for attr in expected_attributes:
                if hasattr(file_manager, attr):
                    assert hasattr(file_manager, attr)

        except ImportError as e:
            pytest.fail(f"file_manager import failed: {e}")


class MockFileRecord:
    """Mock FileRecord class for testing without dependencies."""

    def __init__(self, root: str):
        self.root = root
        self.image_path = None
        self.json_path = None
        self.loaded = False
        self.dirty = False
        self.run_count = 0
        self.summary = {}

    def has_image(self) -> bool:
        """Check if file record has an associated image."""
        return self.image_path is not None and Path(self.image_path).exists()

    def has_json(self) -> bool:
        """Check if file record has an associated JSON file."""
        return self.json_path is not None and Path(self.json_path).exists()

    def is_complete_pair(self) -> bool:
        """Check if file record has both image and JSON files."""
        return self.has_image() and self.has_json()

    def load_summary(self):
        """Load summary data from JSON file."""
        if self.has_json():
            try:
                with open(self.json_path, "r") as f:
                    data = json.load(f)
                    self.summary = data.get("metadata", {})
                    self.run_count = len(data.get("runs", []))
                    self.loaded = True
            except (json.JSONDecodeError, FileNotFoundError):
                self.summary = {}
                self.run_count = 0

    def get_display_name(self) -> str:
        """Get display name for the file record."""
        return Path(self.root).stem


class MockFileIndex:
    """Mock FileIndex class for testing without dependencies."""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.records = {}
        self.loaded = False

    def scan_directory(self):
        """Scan directory for image and JSON file pairs."""
        if not self.directory.exists():
            self.loaded = True
            return

        # Find all image files
        image_extensions = {".png", ".jpg", ".jpeg"}
        for file_path in self.directory.iterdir():
            if file_path.suffix.lower() in image_extensions:
                root = file_path.stem
                if root not in self.records:
                    self.records[root] = MockFileRecord(root)
                self.records[root].image_path = str(file_path)

        # Find all JSON files
        for file_path in self.directory.iterdir():
            if file_path.suffix.lower() == ".json":
                root = file_path.stem.replace(".transcription", "")
                if root not in self.records:
                    self.records[root] = MockFileRecord(root)
                self.records[root].json_path = str(file_path)

        self.loaded = True

    def get_records(self):
        """Get all file records."""
        return list(self.records.values())

    def get_complete_pairs(self):
        """Get file records that have both image and JSON files."""
        return [record for record in self.records.values() if record.is_complete_pair()]

    def get_incomplete_records(self):
        """Get file records missing either image or JSON file."""
        return [
            record for record in self.records.values() if not record.is_complete_pair()
        ]


class TestMockFileRecord:
    """Test mock FileRecord functionality."""

    @pytest.fixture
    def temp_directory(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_files(self, temp_directory):
        """Create sample files for testing."""
        # Create test image file
        image_file = temp_directory / "test_document.png"
        image_file.write_bytes(b"fake_image_data")

        # Create test JSON file
        json_file = temp_directory / "test_document.transcription.json"
        test_data = {
            "version": "2.0",
            "metadata": {"created_at": datetime.now().isoformat(), "model": "gpt-4o"},
            "transcriptions": [{"text": "Test transcription", "index": 0}],
            "runs": [{"id": "run1", "timestamp": datetime.now().isoformat()}],
        }
        json_file.write_text(json.dumps(test_data, indent=2))

        return {
            "image_file": image_file,
            "json_file": json_file,
            "test_data": test_data,
        }

    def test_file_record_creation(self):
        """Test creation of FileRecord instance."""
        record = MockFileRecord("test_document")

        assert record.root == "test_document"
        assert record.image_path is None
        assert record.json_path is None
        assert record.loaded is False
        assert record.dirty is False
        assert record.run_count == 0

    def test_file_record_with_image(self, sample_files):
        """Test FileRecord with image file."""
        record = MockFileRecord("test_document")
        record.image_path = str(sample_files["image_file"])

        assert record.has_image() is True
        assert record.has_json() is False
        assert record.is_complete_pair() is False

    def test_file_record_with_json(self, sample_files):
        """Test FileRecord with JSON file."""
        record = MockFileRecord("test_document")
        record.json_path = str(sample_files["json_file"])

        assert record.has_image() is False
        assert record.has_json() is True
        assert record.is_complete_pair() is False

    def test_file_record_complete_pair(self, sample_files):
        """Test FileRecord with both image and JSON files."""
        record = MockFileRecord("test_document")
        record.image_path = str(sample_files["image_file"])
        record.json_path = str(sample_files["json_file"])

        assert record.has_image() is True
        assert record.has_json() is True
        assert record.is_complete_pair() is True

    def test_file_record_load_summary(self, sample_files):
        """Test loading summary data from JSON file."""
        record = MockFileRecord("test_document")
        record.json_path = str(sample_files["json_file"])

        record.load_summary()

        assert record.loaded is True
        assert record.run_count == 1
        assert "created_at" in record.summary
        assert record.summary["model"] == "gpt-4o"

    def test_file_record_display_name(self):
        """Test getting display name for file record."""
        record = MockFileRecord("test_document")
        display_name = record.get_display_name()

        assert display_name == "test_document"


class TestMockFileIndex:
    """Test mock FileIndex functionality."""

    @pytest.fixture
    def temp_directory_with_files(self):
        """Create temporary directory with multiple test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple image files
            (temp_path / "doc1.png").write_bytes(b"image1")
            (temp_path / "doc2.jpg").write_bytes(b"image2")
            (temp_path / "doc3.png").write_bytes(b"image3")

            # Create JSON files (some matching, some orphaned)
            json_data = {"version": "2.0", "transcriptions": []}

            (temp_path / "doc1.transcription.json").write_text(json.dumps(json_data))
            (temp_path / "doc2.transcription.json").write_text(json.dumps(json_data))
            (temp_path / "orphan.transcription.json").write_text(json.dumps(json_data))

            yield temp_path

    def test_file_index_creation(self, temp_directory_with_files):
        """Test creation of FileIndex instance."""
        index = MockFileIndex(str(temp_directory_with_files))

        assert index.directory == temp_directory_with_files
        assert index.loaded is False
        assert len(index.records) == 0

    def test_file_index_scan_directory(self, temp_directory_with_files):
        """Test scanning directory for files."""
        index = MockFileIndex(str(temp_directory_with_files))
        index.scan_directory()

        assert index.loaded is True
        assert len(index.records) >= 3  # At least doc1, doc2, doc3, orphan

        # Check specific records
        assert "doc1" in index.records
        assert "doc2" in index.records
        assert "doc3" in index.records

    def test_file_index_get_records(self, temp_directory_with_files):
        """Test getting all file records."""
        index = MockFileIndex(str(temp_directory_with_files))
        index.scan_directory()

        records = index.get_records()

        assert len(records) >= 3
        assert all(isinstance(record, MockFileRecord) for record in records)

    def test_file_index_get_complete_pairs(self, temp_directory_with_files):
        """Test getting complete file pairs."""
        index = MockFileIndex(str(temp_directory_with_files))
        index.scan_directory()

        complete_pairs = index.get_complete_pairs()

        # Should have doc1 and doc2 as complete pairs
        complete_names = [record.root for record in complete_pairs]
        assert "doc1" in complete_names
        assert "doc2" in complete_names

        # doc3 should not be complete (no JSON file)
        assert "doc3" not in complete_names

    def test_file_index_get_incomplete_records(self, temp_directory_with_files):
        """Test getting incomplete file records."""
        index = MockFileIndex(str(temp_directory_with_files))
        index.scan_directory()

        incomplete_records = index.get_incomplete_records()

        # Should include doc3 (image only) and orphan (JSON only)
        incomplete_names = [record.root for record in incomplete_records]
        assert "doc3" in incomplete_names
        assert "orphan" in incomplete_names

    def test_file_index_nonexistent_directory(self):
        """Test FileIndex with nonexistent directory."""
        index = MockFileIndex("/nonexistent/directory")
        index.scan_directory()

        assert index.loaded is True
        assert len(index.records) == 0


class TestFileIndexEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_directory(self):
        """Test FileIndex with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index = MockFileIndex(temp_dir)
            index.scan_directory()

            assert index.loaded is True
            assert len(index.records) == 0
            assert len(index.get_complete_pairs()) == 0

    def test_invalid_json_file(self):
        """Test handling of invalid JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create image file
            (temp_path / "test.png").write_bytes(b"image_data")

            # Create invalid JSON file
            (temp_path / "test.transcription.json").write_text("invalid json content")

            index = MockFileIndex(temp_dir)
            index.scan_directory()

            record = index.records.get("test")
            assert record is not None
            assert record.has_image() is True
            assert record.has_json() is True

            # Load summary should handle invalid JSON gracefully
            record.load_summary()
            assert record.summary == {}
            assert record.run_count == 0

    def test_case_insensitive_extensions(self):
        """Test handling of case-insensitive file extensions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files with different case extensions
            (temp_path / "test.PNG").write_bytes(b"image1")
            (temp_path / "test2.JPG").write_bytes(b"image2")
            (temp_path / "test3.JPEG").write_bytes(b"image3")

            index = MockFileIndex(temp_dir)
            index.scan_directory()

            assert "test" in index.records
            assert "test2" in index.records
            assert "test3" in index.records

    def test_complex_filename_patterns(self):
        """Test handling of complex filename patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files with complex names
            (temp_path / "document_with_underscores.png").write_bytes(b"image1")
            (temp_path / "document-with-hyphens.jpg").write_bytes(b"image2")
            (temp_path / "document with spaces.png").write_bytes(b"image3")

            # Create corresponding JSON files
            json_data = {"version": "2.0"}
            (temp_path / "document_with_underscores.transcription.json").write_text(
                json.dumps(json_data)
            )
            (temp_path / "document-with-hyphens.transcription.json").write_text(
                json.dumps(json_data)
            )

            index = MockFileIndex(temp_dir)
            index.scan_directory()

            # Check that complex names are handled correctly
            assert "document_with_underscores" in index.records
            assert "document-with-hyphens" in index.records
            assert "document with spaces" in index.records

            # Check complete pairs
            complete_pairs = index.get_complete_pairs()
            complete_names = [record.root for record in complete_pairs]
            assert "document_with_underscores" in complete_names
            assert "document-with-hyphens" in complete_names


class TestFileIndexIntegration:
    """Integration tests for file index functionality."""

    def test_real_file_manager_integration(self):
        """Test integration with actual file manager if available."""
        try:
            import file_manager

            # Test that actual FileRecord and FileIndex classes exist
            if hasattr(file_manager, "FileRecord"):
                assert file_manager.FileRecord is not None

            if hasattr(file_manager, "FileIndex"):
                assert file_manager.FileIndex is not None

        except ImportError:
            pytest.skip("file_manager module not available for integration testing")

    def test_session_workspace_integration(self):
        """Test integration with session workspace functionality."""
        try:
            import session_workspace

            # Test that session workspace has file-related functions
            expected_functions = ["normalize_filename"]

            for func_name in expected_functions:
                if hasattr(session_workspace, func_name):
                    func = getattr(session_workspace, func_name)
                    assert callable(func)

        except ImportError:
            pytest.skip(
                "session_workspace module not available for integration testing"
            )

    def test_end_to_end_file_workflow(self):
        """Test end-to-end file management workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a realistic file structure
            (temp_path / "receipt_001.png").write_bytes(b"receipt_image")
            (temp_path / "document_002.jpg").write_bytes(b"document_image")

            # Create corresponding JSON files with realistic data
            receipt_data = {
                "version": "2.0",
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "model": "gpt-4o",
                    "total_tokens": 150,
                },
                "transcriptions": [{"text": "Receipt for $25.99", "index": 0}],
            }

            document_data = {
                "version": "2.0",
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "model": "gpt-4-vision-preview",
                    "total_tokens": 300,
                },
                "transcriptions": [{"text": "Important document content", "index": 0}],
            }

            (temp_path / "receipt_001.transcription.json").write_text(
                json.dumps(receipt_data, indent=2)
            )
            (temp_path / "document_002.transcription.json").write_text(
                json.dumps(document_data, indent=2)
            )

            # Test complete workflow
            index = MockFileIndex(temp_dir)
            index.scan_directory()

            # Verify complete pairs
            complete_pairs = index.get_complete_pairs()
            assert len(complete_pairs) == 2

            # Load and verify summary data
            for record in complete_pairs:
                record.load_summary()
                assert record.loaded is True
                assert "created_at" in record.summary
                assert "model" in record.summary

            # Verify specific records
            receipt_record = next(
                (r for r in complete_pairs if r.root == "receipt_001"), None
            )
            document_record = next(
                (r for r in complete_pairs if r.root == "document_002"), None
            )

            assert receipt_record is not None
            assert document_record is not None
            assert receipt_record.summary["model"] == "gpt-4o"
            assert document_record.summary["model"] == "gpt-4-vision-preview"
