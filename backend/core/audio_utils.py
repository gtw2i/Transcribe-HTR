# audio_utils.py
"""
Audio utilities for Streamlit Transcribe TTS functionality.
Handles audio file operations, duration calculation, format validation, and player integration.
"""

import io
import logging
import tempfile
import wave
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

# Configure logging
logger = logging.getLogger(__name__)

# Try to import optional audio libraries
try:
    import soundfile as sf

    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    logger.warning("soundfile not available - some audio utilities will be limited")


class AudioUtils:
    """
    Audio utilities for TTS functionality.

    Provides:
    - Audio file validation and metadata extraction
    - Duration calculation from audio data
    - Format conversion utilities
    - Streamlit audio player integration
    - Audio file download preparation
    """

    # Supported audio formats
    SUPPORTED_FORMATS = {
        "wav": {
            "mime_type": "audio/wav",
            "extension": ".wav",
            "description": "WAV (Waveform Audio File Format)",
        },
        "mp3": {
            "mime_type": "audio/mpeg",
            "extension": ".mp3",
            "description": "MP3 (MPEG Audio Layer III)",
        },
        "ogg": {
            "mime_type": "audio/ogg",
            "extension": ".ogg",
            "description": "OGG Vorbis",
        },
    }

    @staticmethod
    def validate_audio_data(
        audio_data: bytes, expected_format: str = "wav"
    ) -> Dict[str, Union[bool, str, int]]:
        """
        Validate audio data and extract basic information.

        Args:
            audio_data: Raw audio bytes
            expected_format: Expected audio format

        Returns:
            Dict with validation results and metadata
        """
        if not audio_data or len(audio_data) == 0:
            return {"valid": False, "error": "Empty audio data", "size": 0}

        try:
            # Basic size validation
            size_mb = len(audio_data) / (1024 * 1024)

            # Check for common audio file headers
            if expected_format == "wav":
                if not audio_data.startswith(b"RIFF"):
                    return {
                        "valid": False,
                        "error": "Invalid WAV file header",
                        "size": len(audio_data),
                    }

                if b"WAVE" not in audio_data[:12]:
                    return {
                        "valid": False,
                        "error": "Invalid WAV file format",
                        "size": len(audio_data),
                    }

            return {
                "valid": True,
                "size": len(audio_data),
                "size_mb": round(size_mb, 2),
                "format": expected_format,
            }

        except Exception as e:
            logger.error(f"Audio validation failed: {e}")
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "size": len(audio_data) if audio_data else 0,
            }

    @staticmethod
    def get_audio_duration(audio_data: bytes, format: str = "wav") -> Optional[float]:
        """
        Calculate audio duration from audio data.

        Args:
            audio_data: Raw audio bytes
            format: Audio format (wav, mp3, etc.)

        Returns:
            Duration in seconds, or None if calculation fails
        """
        try:
            if format == "wav":
                return AudioUtils._get_wav_duration(audio_data)
            elif HAS_SOUNDFILE:
                return AudioUtils._get_duration_with_soundfile(audio_data)
            else:
                logger.warning(
                    "Cannot calculate duration - soundfile library not available"
                )
                return None

        except Exception as e:
            logger.error(f"Duration calculation failed: {e}")
            return None

    @staticmethod
    def _get_wav_duration(audio_data: bytes) -> Optional[float]:
        """
        Calculate WAV file duration using built-in wave module.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Duration in seconds
        """
        try:
            # Create a BytesIO object from audio data
            audio_io = io.BytesIO(audio_data)

            # Open with wave module
            with wave.open(audio_io, "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)

                logger.debug(f"WAV duration calculated: {duration:.2f} seconds")
                return duration

        except Exception as e:
            logger.error(f"WAV duration calculation failed: {e}")
            return None

    @staticmethod
    def _get_duration_with_soundfile(audio_data: bytes) -> Optional[float]:
        """
        Calculate audio duration using soundfile library (supports multiple formats).

        Args:
            audio_data: Audio bytes

        Returns:
            Duration in seconds
        """
        try:
            # Create temporary file for soundfile to read
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()

                # Get audio info
                info = sf.info(temp_file.name)
                duration = info.duration

                logger.debug(f"Audio duration calculated: {duration:.2f} seconds")
                return duration

        except Exception as e:
            logger.error(f"Soundfile duration calculation failed: {e}")
            return None

    @staticmethod
    def get_audio_metadata(
        audio_data: bytes, format: str = "wav"
    ) -> Dict[str, Union[str, int, float]]:
        """
        Extract comprehensive metadata from audio data.

        Args:
            audio_data: Raw audio bytes
            format: Audio format

        Returns:
            Dict with audio metadata
        """
        metadata = {
            "format": format,
            "size_bytes": len(audio_data),
            "size_mb": round(len(audio_data) / (1024 * 1024), 2),
            "duration": None,
            "sample_rate": None,
            "channels": None,
            "bit_depth": None,
        }

        try:
            # Get duration
            duration = AudioUtils.get_audio_duration(audio_data, format)
            if duration:
                metadata["duration"] = round(duration, 2)
                metadata["duration_formatted"] = AudioUtils.format_duration(duration)

            # Get detailed WAV info if possible
            if format == "wav":
                wav_info = AudioUtils._get_wav_info(audio_data)
                metadata.update(wav_info)

        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            metadata["error"] = str(e)

        return metadata

    @staticmethod
    def _get_wav_info(audio_data: bytes) -> Dict[str, Union[int, str]]:
        """
        Extract detailed WAV file information.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Dict with WAV-specific metadata
        """
        wav_info = {}

        try:
            audio_io = io.BytesIO(audio_data)

            with wave.open(audio_io, "rb") as wav_file:
                wav_info.update(
                    {
                        "sample_rate": wav_file.getframerate(),
                        "channels": wav_file.getnchannels(),
                        "bit_depth": wav_file.getsampwidth() * 8,
                        "frames": wav_file.getnframes(),
                        "compression": wav_file.getcomptype(),
                    }
                )

        except Exception as e:
            logger.error(f"WAV info extraction failed: {e}")
            wav_info["error"] = str(e)

        return wav_info

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to MM:SS format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "01:23")
        """
        if seconds is None:
            return "00:00"

        try:
            minutes = int(seconds // 60)
            seconds_remainder = int(seconds % 60)
            return f"{minutes:02d}:{seconds_remainder:02d}"
        except:
            return "00:00"

    @staticmethod
    def prepare_for_streamlit_audio(
        audio_data: bytes, format: str = "wav"
    ) -> Dict[str, Union[bytes, str]]:
        """
        Prepare audio data for Streamlit audio player.

        Args:
            audio_data: Raw audio bytes
            format: Audio format

        Returns:
            Dict with audio data and metadata for Streamlit
        """
        try:
            # Validate audio data
            validation = AudioUtils.validate_audio_data(audio_data, format)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}

            # Get metadata
            metadata = AudioUtils.get_audio_metadata(audio_data, format)

            # Prepare for Streamlit
            mime_type = AudioUtils.SUPPORTED_FORMATS.get(format, {}).get(
                "mime_type", "audio/wav"
            )

            return {
                "success": True,
                "audio_data": audio_data,
                "mime_type": mime_type,
                "metadata": metadata,
                "duration_formatted": metadata.get("duration_formatted", "00:00"),
                "size_formatted": f"{metadata['size_mb']} MB",
            }

        except Exception as e:
            logger.error(f"Streamlit audio preparation failed: {e}")
            return {"success": False, "error": f"Audio preparation failed: {str(e)}"}

    @staticmethod
    def prepare_for_download(
        audio_data: bytes, filename: str, format: str = "wav"
    ) -> Dict[str, Union[bytes, str]]:
        """
        Prepare audio data for download.

        Args:
            audio_data: Raw audio bytes
            filename: Base filename (without extension)
            format: Audio format

        Returns:
            Dict with download-ready audio data and metadata
        """
        try:
            # Ensure proper file extension
            extension = AudioUtils.SUPPORTED_FORMATS.get(format, {}).get(
                "extension", ".wav"
            )
            if not filename.endswith(extension):
                filename = f"{filename}{extension}"

            # Get metadata
            metadata = AudioUtils.get_audio_metadata(audio_data, format)
            mime_type = AudioUtils.SUPPORTED_FORMATS.get(format, {}).get(
                "mime_type", "audio/wav"
            )

            return {
                "success": True,
                "audio_data": audio_data,
                "filename": filename,
                "mime_type": mime_type,
                "size_mb": metadata["size_mb"],
                "duration": metadata.get("duration_formatted", "00:00"),
            }

        except Exception as e:
            logger.error(f"Download preparation failed: {e}")
            return {"success": False, "error": f"Download preparation failed: {str(e)}"}

    @staticmethod
    def create_audio_player_html(
        audio_data: bytes,
        format: str = "wav",
        autoplay: bool = False,
        controls: bool = True,
    ) -> str:
        """
        Create custom HTML audio player (alternative to Streamlit's built-in player).

        Args:
            audio_data: Raw audio bytes
            format: Audio format
            autoplay: Whether to autoplay
            controls: Whether to show controls

        Returns:
            HTML string for custom audio player
        """
        try:
            import base64

            mime_type = AudioUtils.SUPPORTED_FORMATS.get(format, {}).get(
                "mime_type", "audio/wav"
            )

            # Encode audio data to base64
            audio_b64 = base64.b64encode(audio_data).decode()

            # Create HTML
            autoplay_attr = "autoplay" if autoplay else ""
            controls_attr = "controls" if controls else ""

            html = f"""
            <audio {controls_attr} {autoplay_attr} style="width: 100%;">
                <source src="data:{mime_type};base64,{audio_b64}" type="{mime_type}">
                Your browser does not support the audio element.
            </audio>
            """

            return html

        except Exception as e:
            logger.error(f"HTML audio player creation failed: {e}")
            return f"<p>Error creating audio player: {str(e)}</p>"

    @staticmethod
    def get_format_info() -> Dict[str, Dict]:
        """Get information about supported audio formats."""
        return AudioUtils.SUPPORTED_FORMATS.copy()

    @staticmethod
    def cleanup_temp_files(temp_dir: Union[str, Path]) -> Dict[str, Union[int, str]]:
        """
        Clean up temporary audio files.

        Args:
            temp_dir: Directory containing temporary files

        Returns:
            Dict with cleanup statistics
        """
        try:
            temp_path = Path(temp_dir)
            if not temp_path.exists():
                return {"files_removed": 0, "status": "directory_not_found"}

            # Find audio files
            audio_extensions = [".wav", ".mp3", ".ogg"]
            audio_files = []
            for ext in audio_extensions:
                audio_files.extend(temp_path.glob(f"*{ext}"))

            # Remove files
            files_removed = 0
            for file_path in audio_files:
                try:
                    file_path.unlink()
                    files_removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")

            logger.info(f"Audio cleanup completed: {files_removed} files removed")
            return {"files_removed": files_removed, "status": "success"}

        except Exception as e:
            logger.error(f"Audio cleanup failed: {e}")
            return {"files_removed": 0, "status": "error", "error": str(e)}


# Convenience functions for common operations
def validate_audio(audio_data: bytes, format: str = "wav") -> bool:
    """Quick audio validation check."""
    result = AudioUtils.validate_audio_data(audio_data, format)
    return result.get("valid", False)


def get_duration(audio_data: bytes, format: str = "wav") -> Optional[float]:
    """Quick duration calculation."""
    return AudioUtils.get_audio_duration(audio_data, format)


def format_duration(seconds: float) -> str:
    """Quick duration formatting."""
    return AudioUtils.format_duration(seconds)


def prepare_streamlit_audio(audio_data: bytes, format: str = "wav") -> Dict:
    """Quick Streamlit audio preparation."""
    return AudioUtils.prepare_for_streamlit_audio(audio_data, format)


def prepare_download(audio_data: bytes, filename: str, format: str = "wav") -> Dict:
    """Quick download preparation."""
    return AudioUtils.prepare_for_download(audio_data, filename, format)


# Audio format validation
def is_supported_format(format: str) -> bool:
    """Check if audio format is supported."""
    return format.lower() in AudioUtils.SUPPORTED_FORMATS


def get_mime_type(format: str) -> str:
    """Get MIME type for audio format."""
    return AudioUtils.SUPPORTED_FORMATS.get(format.lower(), {}).get(
        "mime_type", "audio/wav"
    )


# Logging setup for audio operations
def setup_audio_logging(level: str = "INFO"):
    """Setup logging for audio utilities."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(__name__).setLevel(numeric_level)
