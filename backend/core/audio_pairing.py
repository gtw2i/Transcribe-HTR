"""
Audio file pairing utilities. Handles pairing of uploaded audio files with images
and JSONs by base name.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_audio_extensions() -> set:
    """Get supported audio file extensions."""
    return {".wav", ".mp3", ".m4a", ".ogg"}


def extract_base_name(filename: str) -> str:
    """
    Extract base name from filename for pairing.

    Examples:
        'document.jpg' -> 'document'
        'letter.transcription.json' -> 'letter'
        'report.wav' -> 'report'
    """
    path = Path(filename)

    if path.name.endswith(".transcription.json"):
        return path.name[: -len(".transcription.json")]

    return path.stem


def find_audio_files_for_root(
    directory: Path,
    root: str,
) -> List[Path]:
    """Find all audio files in directory that match the given root name."""
    audio_extensions = get_audio_extensions()
    matches = []
    for ext in audio_extensions:
        candidate = directory / f"{root}{ext}"
        if candidate.exists():
            matches.append(candidate)
    return matches


def get_audio_pairs(
    directory: Path,
    image_roots: List[str],
) -> Dict[str, Optional[Path]]:
    """Return a mapping of root → audio path (or None) for each image root."""
    return {
        root: (find_audio_files_for_root(directory, root) or [None])[0]
        for root in image_roots
    }


def is_audio_file(filename: str) -> bool:
    """Return True if the filename has a supported audio extension."""
    return Path(filename).suffix.lower() in get_audio_extensions()
