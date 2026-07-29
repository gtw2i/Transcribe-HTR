# session_workspace.py — backend copy, all Streamlit deps removed
"""
Session workspace management. Cloud-aware file persistence with graceful degradation.
Session IDs are provided by FastAPI dependency injection — no Streamlit session state.
"""

import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from logging_config import log_error, log_info, log_warning

logger = logging.getLogger(__name__)


# =========================
# V2 JSON SCHEMA FUNCTIONS
# =========================

def create_v2_json_schema(
    root: str,
    image_filename: str,
    settings: Optional[Dict[str, Any]] = None,
    app_version: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    now_utc = datetime.utcnow().isoformat() + "Z"
    schema = {
        "schema_version": "2.0",
        "metadata": {
            "root": root,
            "image_filename": image_filename,
            "created_at": now_utc,
            "updated_at": now_utc,
            "citation": (
                "West, G. & Wallin, J. (2026). Transkrybe.ai: "
                "An AI-powered tool for historical manuscript transcription "
                "and analysis [Software]."
            ),
            "license": "BSD-2-Clause",
        },
        "runs": [],
        "harmonizations": [],
        "summaries": [],
        "ner_results": [],
        "analyses": [],
    }
    if settings:
        schema["metadata"]["settings"] = settings
    if app_version:
        schema["metadata"]["app_version"] = app_version
    if session_id:
        schema["metadata"]["session_id"] = session_id
    return schema


def create_run_record(
    model: str,
    temperature: float,
    base_prompt: str,
    domain_prompt: str,
    tokens_in: int,
    tokens_out: int,
    token_method: str,
    started_at: datetime,
    completed_at: datetime,
    outputs: List[Any],
    provider: str = "",
    profile_name: str = "",
    estimated_cost_usd=None,
    thinking_tokens: int = 0,
) -> Dict[str, Any]:
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    return {
        "run_id": str(uuid.uuid4()),
        "model": model,
        "provider": provider,
        "profile_name": profile_name,
        "temperature": temperature,
        "base_prompt": base_prompt,
        "domain_prompt": domain_prompt,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "thinking_tokens": thinking_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "token_method": token_method,
        "started_at": started_at.isoformat() + "Z",
        "completed_at": completed_at.isoformat() + "Z",
        "duration_ms": duration_ms,
        "outputs": outputs,
    }


def create_harmonization_record(
    harmonized_text: str,
    source_run_ids: List[str],
    source_indices: List[int],
    model_used: str,
    temperature: float,
    tokens_used: Dict[str, int],
    created_at: datetime,
    provider: str = "",
    system_prompt: str = "",
    task_prompt: str = "",
) -> Dict[str, Any]:
    return {
        "harmonization_id": str(uuid.uuid4()),
        "harmonized_text": harmonized_text,
        "created_at": created_at.isoformat() + "Z",
        "source_run_ids": source_run_ids,
        "source_indices": source_indices,
        "source_count": len(source_indices),
        "model_used": model_used,
        "provider": provider,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "task_prompt": task_prompt,
        "tokens_used": tokens_used,
    }


def create_summary_record(
    summary_text: str,
    source_indices: List[int],
    model_used: str,
    provider: str,
    temperature: float,
    system_prompt: str,
    tokens_used: Dict[str, Any],
    created_at: datetime,
    task_prompt: str = "",
) -> Dict[str, Any]:
    return {
        "summary_id": str(uuid.uuid4()),
        "summary_text": summary_text,
        "created_at": created_at.isoformat() + "Z",
        "source_indices": source_indices,
        "model_used": model_used,
        "provider": provider,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "task_prompt": task_prompt,
        "tokens_used": tokens_used,
    }


def create_ner_record(
    entity_bundle: Dict[str, Any],
    grounding_info: Dict[str, Any],
    tokens_usage: Dict[str, Any],
    pass2_used: bool,
    source_indices: List[int],
    model_used: str,
    provider: str,
    temperature: float,
    system_prompt: str,
    created_at: datetime,
    task_prompt: str = "",
) -> Dict[str, Any]:
    return {
        "ner_id": str(uuid.uuid4()),
        "entity_bundle": entity_bundle,
        "grounding_info": grounding_info,
        "tokens_usage": tokens_usage,
        "pass2_used": pass2_used,
        "created_at": created_at.isoformat() + "Z",
        "source_indices": source_indices,
        "model_used": model_used,
        "provider": provider,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "task_prompt": task_prompt,
    }


def append_harmonization_to_v2_json(
    v2_json: Dict[str, Any], harmonization_record: Dict[str, Any]
) -> None:
    if "harmonizations" not in v2_json:
        v2_json["harmonizations"] = []
    v2_json["harmonizations"].append(harmonization_record)
    v2_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"


def append_summary_to_v2_json(v2_json: Dict[str, Any], summary_record: Dict[str, Any]) -> None:
    if "summaries" not in v2_json:
        v2_json["summaries"] = []
    v2_json["summaries"].append(summary_record)
    v2_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"


def append_ner_result_to_v2_json(v2_json: Dict[str, Any], ner_record: Dict[str, Any]) -> None:
    if "ner_results" not in v2_json:
        v2_json["ner_results"] = []
    v2_json["ner_results"].append(ner_record)
    v2_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"


def create_analysis_record(
    report: Dict[str, Any],
    user_note: str = "",
    created_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Wrap a consistency report for storage in ``analyses[]``.

    A fresh ``analysis_id`` is minted here rather than trusting the one in
    *report*: the analyze endpoint is cached, so two identical requests receive
    the same provisional id, and two users saving the same analysis would
    otherwise write records sharing it.
    """
    record = dict(report)
    record["analysis_id"] = str(uuid.uuid4())
    record["saved_at"] = (created_at or datetime.utcnow()).isoformat() + "Z"
    if user_note:
        record["user_note"] = user_note
    return record


def append_analysis_to_v2_json(v2_json: Dict[str, Any], analysis_record: Dict[str, Any]) -> None:
    """Append a consistency analysis. Additive and non-destructive (D11)."""
    if "analyses" not in v2_json:
        v2_json["analyses"] = []
    v2_json["analyses"].append(analysis_record)
    v2_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"


def append_run_to_v2_json(v2_json: Dict[str, Any], run_record: Dict[str, Any]) -> None:
    v2_json["runs"].append(run_record)
    v2_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"


def get_canonical_json_filename(root: str) -> str:
    return f"{root}.transcription.json"


def validate_v2_json_schema(v2_json: Dict[str, Any]) -> bool:
    required_fields = ["schema_version", "metadata", "runs"]
    try:
        for f in required_fields:
            if f not in v2_json:
                return False
        # 2.1 is accepted for forward tolerance. Optional record arrays
        # (harmonizations, summaries, ner_results, analyses) are added
        # defensively on write rather than by bumping the version, so a file
        # written by an older build stays valid.
        if v2_json["schema_version"] not in ("2.0", "2.1"):
            return False
        if not isinstance(v2_json["metadata"], dict):
            return False
        if not isinstance(v2_json["runs"], list):
            return False
        for run in v2_json["runs"]:
            if not validate_run_record(run):
                return False
        return True
    except Exception:
        return False


def validate_run_record(run: Dict[str, Any]) -> bool:
    required_fields = [
        "run_id", "model", "temperature", "base_prompt", "domain_prompt",
        "tokens_in", "tokens_out", "token_method", "started_at",
        "completed_at", "duration_ms", "outputs",
    ]
    try:
        for f in required_fields:
            if f not in run:
                return False
        if not isinstance(run["outputs"], list):
            return False
        return True
    except Exception:
        return False


def normalize_filename(filename: str, preserve_root: bool = True) -> str:
    path_obj = Path(filename)
    stem = path_obj.stem
    suffix = path_obj.suffix.lower()
    extension_mapping = {".jpeg": ".jpg", ".json": ".json", ".png": ".png", ".jpg": ".jpg"}
    standardized_suffix = extension_mapping.get(suffix, suffix)
    if not preserve_root:
        stem = stem.lower().replace(" ", "_")
    return f"{stem}{standardized_suffix}"


def generate_unique_filename(target_dir: Path, filename: str, allow_overwrite: bool = False) -> str:
    if allow_overwrite:
        return filename
    target_path = target_dir / filename
    if not target_path.exists():
        return filename
    path_obj = Path(filename)
    stem = path_obj.stem
    suffix = path_obj.suffix
    counter = 1
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if not (target_dir / candidate).exists():
            return candidate
        counter += 1


# =========================
# FILE INDEX
# =========================

@dataclass
class FileRecord:
    root: str
    image_path: Optional[str] = None
    json_path: Optional[str] = None
    audio_path: Optional[str] = None
    loaded: bool = False
    dirty: bool = False
    run_count: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)

    def has_image(self) -> bool:
        return self.image_path is not None and Path(self.image_path).exists()

    def has_json(self) -> bool:
        return self.json_path is not None and Path(self.json_path).exists()

    def has_audio(self) -> bool:
        return self.audio_path is not None and Path(self.audio_path).exists()

    def is_complete_pair(self) -> bool:
        return self.has_image() and self.has_json()

    def is_complete_set(self) -> bool:
        return self.has_image() and self.has_json() and self.has_audio()


class FileIndex:
    def __init__(self, workspace: "SessionWorkspace"):
        self.workspace = workspace
        self.records: Dict[str, FileRecord] = {}

    def register_file(self, file_path: Path) -> FileRecord:
        if not file_path.is_absolute():
            raise ValueError(f"File path must be absolute: {file_path}")
        try:
            file_path.relative_to(self.workspace.workspace_path)
        except ValueError:
            raise ValueError(f"File must be within session workspace: {file_path}")

        if file_path.name.endswith(".transcription.json"):
            root = file_path.name[: -len(".transcription.json")]
            ext = ".transcription.json"
        else:
            root = file_path.stem
            ext = file_path.suffix.lower()

        if root not in self.records:
            self.records[root] = FileRecord(root=root)

        record = self.records[root]

        if ext in [".png", ".jpg", ".jpeg"]:
            record.image_path = str(file_path)
        elif ext in [".json", ".transcription.json"]:
            record.json_path = str(file_path)
            self._update_json_metadata(record, file_path)
        elif ext in [".wav", ".mp3", ".m4a", ".ogg"]:
            record.audio_path = str(file_path)

        return record

    def _update_json_metadata(self, record: FileRecord, json_path: Path) -> None:
        try:
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "runs" in data and isinstance(data["runs"], list):
                        record.run_count = len(data["runs"])
                    else:
                        transcriptions = data.get("transcriptions", [])
                        record.run_count = len(transcriptions) if isinstance(transcriptions, list) else 0
                stat = json_path.stat()
                record.summary.update({
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "file_size": stat.st_size,
                    "is_canonical": json_path.name.endswith(".transcription.json"),
                })
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            record.summary["metadata_error"] = str(e)

    def unregister_file(self, file_path: Path) -> bool:
        if file_path.name.endswith(".transcription.json"):
            root = file_path.name[: -len(".transcription.json")]
            ext = ".transcription.json"
        else:
            root = file_path.stem
            ext = file_path.suffix.lower()

        if root not in self.records:
            return False

        record = self.records[root]
        if ext in [".png", ".jpg", ".jpeg"] and record.image_path == str(file_path):
            record.image_path = None
        elif ext in [".json", ".transcription.json"] and record.json_path == str(file_path):
            record.json_path = None
            record.run_count = 0
            record.summary.clear()
        elif ext in [".wav", ".mp3", ".m4a", ".ogg"] and record.audio_path == str(file_path):
            record.audio_path = None
        else:
            return False

        if not record.has_image() and not record.has_json():
            del self.records[root]
        return True

    def find_json_for_image(self, image_filename: str) -> Optional[Path]:
        root = Path(image_filename).stem
        if root in self.records and self.records[root].json_path:
            json_path = Path(self.records[root].json_path)
            if json_path.exists():
                return json_path
            self.records[root].json_path = None

        if self.workspace.workspace_path:
            canonical_path = self.workspace.workspace_path / f"{root}.transcription.json"
            if canonical_path.exists():
                self.register_file(canonical_path)
                return canonical_path
            legacy_path = self.workspace.workspace_path / f"{root}.json"
            if legacy_path.exists():
                self.register_file(legacy_path)
                return legacy_path
        return None

    def get_all_pairs(self) -> List[FileRecord]:
        return [r for r in self.records.values() if r.is_complete_pair()]

    def get_orphaned_images(self) -> List[FileRecord]:
        return [r for r in self.records.values() if r.has_image() and not r.has_json()]

    def get_orphaned_jsons(self) -> List[FileRecord]:
        return [r for r in self.records.values() if r.has_json() and not r.has_image()]

    def populate_from_workspace(self) -> None:
        if not self.workspace.ensure_workspace() or not self.workspace.workspace_path:
            return
        self.records.clear()
        for file_path in self.workspace.get_workspace_files():
            try:
                self.register_file(file_path)
            except (ValueError, OSError):
                continue

    def to_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {root: asdict(record) for root, record in self.records.items()}

    def from_snapshot(self, snapshot: Dict[str, Dict[str, Any]]) -> None:
        self.records = {}
        for root, data in snapshot.items():
            try:
                self.records[root] = FileRecord(**data)
            except (TypeError, ValueError):
                continue

    def get_index_stats(self) -> Dict[str, int]:
        return {
            "total_records": len(self.records),
            "complete_pairs": len(self.get_all_pairs()),
            "orphaned_images": len(self.get_orphaned_images()),
            "orphaned_jsons": len(self.get_orphaned_jsons()),
        }


# =========================
# SESSION WORKSPACE
# =========================

class SessionWorkspace:
    """Per-session temp file storage. session_id must be provided explicitly."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_root = self._determine_base_root()
        self.workspace_path: Optional[Path] = None
        self.staging_path: Optional[Path] = None
        self.exports_path: Optional[Path] = None
        self.audio_path: Optional[Path] = None
        self.is_writable = False
        self._initialized = False

    def _determine_base_root(self) -> Path:
        if root := os.getenv("TRANSCRIBE_SESSION_ROOT"):
            return Path(root)
        return Path(tempfile.gettempdir()) / "transcribe_app"

    def ensure_workspace(self) -> bool:
        if self._initialized:
            return self.is_writable
        try:
            self.workspace_path = self.base_root / "sessions" / self.session_id / "workspace"
            self.staging_path = self.workspace_path / "staging"
            self.exports_path = self.workspace_path / "exports"
            self.audio_path = self.workspace_path / "audio"
            for path in [self.workspace_path, self.staging_path, self.exports_path, self.audio_path]:
                path.mkdir(parents=True, exist_ok=True)
            test_file = self.workspace_path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            self.is_writable = True
            self._initialized = True
            return True
        except (PermissionError, OSError) as e:
            logger.warning(f"Workspace is read-only; using memory-only mode. ({type(e).__name__})")
            self.is_writable = False
            self._initialized = True
            return False

    def persist_uploaded_file(
        self,
        filename: str,
        data: bytes,
        file_index: Optional["FileIndex"] = None,
        allow_overwrite: bool = True,
    ) -> Optional[Path]:
        """Save uploaded file bytes to workspace. Returns saved path or None."""
        if not self.ensure_workspace() or not self.is_writable:
            return None
        try:
            from audio_pairing import get_audio_extensions
            file_ext = Path(filename).suffix.lower()
            audio_extensions = get_audio_extensions()
            allowed_extensions = {".png", ".jpg", ".jpeg", ".json"} | audio_extensions
            if file_ext not in allowed_extensions:
                logger.warning(f"File type {file_ext} not supported.")
                return None

            normalized_name = normalize_filename(filename, preserve_root=True)
            final_name = generate_unique_filename(self.workspace_path, normalized_name, allow_overwrite=allow_overwrite)
            target_path = self.workspace_path / final_name
            target_path.write_bytes(data)

            if file_index is not None:
                try:
                    file_index.register_file(target_path)
                except Exception:
                    pass

            return target_path
        except Exception as e:
            logger.error(f"Failed to persist file '{filename}': {e}")
            return None

    def get_workspace_files(self, file_type: Optional[str] = None) -> List[Path]:
        if not self.ensure_workspace() or not self.workspace_path:
            return []
        try:
            if file_type:
                return list(self.workspace_path.glob(f"*{file_type}"))
            files = []
            for ext in [".png", ".jpg", ".jpeg", ".json"]:
                files.extend(self.workspace_path.glob(f"*{ext}"))
            files.extend(self.workspace_path.glob("*.transcription.json"))
            return files
        except Exception:
            return []

    def find_associated_files(self, filename: str) -> Dict[str, Optional[Path]]:
        if not self.ensure_workspace():
            return {"image": None, "json": None}
        root = Path(filename).stem
        result = {"image": None, "json": None}
        for ext in [".png", ".jpg"]:
            candidate = self.workspace_path / f"{root}{ext}"
            if candidate.exists():
                result["image"] = candidate
                break
        json_candidate = self.workspace_path / f"{root}.json"
        if json_candidate.exists():
            result["json"] = json_candidate
        return result

    def cleanup_session(self) -> None:
        if self.workspace_path and self.workspace_path.exists():
            try:
                shutil.rmtree(self.workspace_path.parent)
            except Exception as e:
                logger.warning(f"Failed to cleanup session workspace: {e}")

    def get_workspace_info(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "base_root": str(self.base_root),
            "workspace_path": str(self.workspace_path) if self.workspace_path else None,
            "is_writable": self.is_writable,
            "exists": self.workspace_path.exists() if self.workspace_path else False,
            "file_count": len(self.get_workspace_files()) if self.is_writable else 0,
        }


def cleanup_expired_workspaces(base_root: Optional[Path] = None, ttl_hours: int = 48) -> int:
    if base_root is None:
        if root := os.getenv("TRANSCRIBE_SESSION_ROOT"):
            base_root = Path(root)
        else:
            base_root = Path(tempfile.gettempdir()) / "transcribe_app"

    sessions_dir = base_root / "sessions"
    if not sessions_dir.exists():
        return 0

    cutoff_time = datetime.now() - timedelta(hours=ttl_hours)
    cleaned_count = 0

    try:
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
            except (OSError, ValueError):
                continue
    except Exception as e:
        logger.warning(f"Error during workspace cleanup: {e}")

    return cleaned_count
