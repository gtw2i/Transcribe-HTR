# tts_engine.py
"""
Text-to-Speech Engine for Streamlit Transcribe application.
Handles OpenAI TTS API integration with comprehensive error handling and cost tracking.
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from openai import OpenAI

# Import configuration
import config
from core.retry_utils import classify_error, with_retry
from fallback import retry_kwargs_for, run_with_fallback

# Configure logging
logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Text-to-Speech engine using OpenAI's TTS models.

    Features:
    - Multiple TTS model support
    - Voice selection with historical context
    - Cost estimation and token tracking
    - Audio caching with hash-based keys
    - Comprehensive error handling
    """

    # Note: All TTS configurations are now imported from config.py to avoid duplication

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TTS Engine.

        Args:
            api_key: OpenAI API key. If None, will attempt to get from environment.
        """
        self.api_key = api_key
        self.client = None
        self.cache_dir = Path("tmp/audio")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize OpenAI client if API key provided
        if api_key:
            self._initialize_client(api_key)

    def _initialize_client(self, api_key: str) -> bool:
        """
        Initialize OpenAI client with API key.

        Args:
            api_key: OpenAI API key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("🔧 Initializing OpenAI TTS client...")
            logger.debug(
                f"🔑 API key format: {'sk-***' + api_key[-4:] if api_key.startswith('sk-') else 'INVALID_FORMAT'}"
            )

            self.client = OpenAI(api_key=api_key)
            self.api_key = api_key
            logger.info("✅ TTS Engine initialized successfully")

            # Test the connection with a simple API call
            try:
                logger.info("🧪 Testing API connection...")
                # We can't easily test audio.speech without generating audio, so we'll skip this for now
                logger.info("🟢 API connection ready (test skipped to avoid costs)")

            except Exception as test_error:
                logger.warning(
                    f"⚠️ API connection test failed (continuing anyway): {test_error}"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize TTS Engine: {type(e).__name__}: {e}")
            self.client = None
            return False

    def validate_api_key(self, api_key: str) -> Dict[str, Union[bool, str]]:
        """
        Validate that the API key works for TTS operations.

        Args:
            api_key: OpenAI API key to validate

        Returns:
            Dict with validation result and message
        """
        try:
            # Test client initialization
            test_client = OpenAI(api_key=api_key)

            # Try to make a minimal TTS request to validate
            # Note: This would use a very small amount of API credits
            # For validation, we might just check the key format instead
            if not api_key.startswith("sk-"):
                return {
                    "valid": False,
                    "message": 'API key format invalid. Should start with "sk-"',
                }

            # If we reach here, basic validation passed
            return {"valid": True, "message": "API key appears valid"}

        except Exception as e:
            return {"valid": False, "message": f"API key validation failed: {str(e)}"}

    def estimate_cost(
        self, text: str, model: str = "tts-1"
    ) -> Dict[str, Union[float, int]]:
        """
        Estimate the cost of generating TTS for the given text.

        Args:
            text: Text to convert to speech
            model: TTS model to use

        Returns:
            Dict with cost estimation details
        """
        char_count = len(text)

        if model not in config.TTS_MODELS:
            return {"error": f"Unknown model: {model}", "char_count": char_count}

        model_info = config.TTS_MODELS[model]
        max_chars = model_info["max_chars"]
        cost_per_1k = model_info["cost_per_1k_chars"]

        # Calculate estimated cost
        estimated_cost = (char_count / 1000) * cost_per_1k

        # Check if text exceeds model limits
        exceeds_limit = char_count > max_chars

        return {
            "char_count": char_count,
            "max_chars": max_chars,
            "exceeds_limit": exceeds_limit,
            "estimated_cost": round(estimated_cost, 4),
            "cost_per_1k_chars": cost_per_1k,
            "model": model,
            "model_name": model_info["name"],
        }

    def _generate_cache_key(
        self, text: str, model: str, voice: str, system_prompt: str = None
    ) -> str:
        """
        Generate a cache key for the given parameters.

        Args:
            text: Text content
            model: TTS model
            voice: Voice selection
            system_prompt: System prompt (ignored for TTS, kept for compatibility)

        Returns:
            SHA256 hash as cache key
        """
        # For TTS, only text, model, and voice affect the output
        # System prompt is ignored since TTS doesn't use instructions
        content = f"{text}|{model}|{voice}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached_audio(self, cache_key: str) -> Optional[Dict]:
        """
        Retrieve cached audio if available.

        Args:
            cache_key: Cache key to look up

        Returns:
            Dict with audio data and metadata, or None if not cached
        """
        cache_file = self.cache_dir / f"{cache_key}.wav"
        metadata_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists() and metadata_file.exists():
            try:
                import json

                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

                with open(cache_file, "rb") as f:
                    audio_data = f.read()

                logger.info(f"Retrieved cached audio: {cache_key}")
                return {
                    "audio_data": audio_data,
                    "metadata": metadata,
                    "from_cache": True,
                }
            except Exception as e:
                logger.warning(f"Failed to load cached audio {cache_key}: {e}")

        return None

    def _save_to_cache(self, cache_key: str, audio_data: bytes, metadata: Dict) -> bool:
        """
        Save audio data and metadata to cache.

        Args:
            cache_key: Cache key
            audio_data: Audio file bytes
            metadata: Metadata dictionary

        Returns:
            bool: True if successful
        """
        try:
            import json

            cache_file = self.cache_dir / f"{cache_key}.wav"
            metadata_file = self.cache_dir / f"{cache_key}.json"

            # Save audio data
            with open(cache_file, "wb") as f:
                f.write(audio_data)

            # Save metadata
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2, default=str)

            logger.info(f"Cached audio: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache audio {cache_key}: {e}")
            return False

    def generate_speech(
        self,
        text: str,
        model: str = "tts-1",
        voice: str = "onyx",
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
        original_image_filename: Optional[str] = None,
    ) -> Dict[str, Union[bytes, Dict, bool, str]]:
        """
        Generate speech from text using OpenAI TTS.

        Args:
            text: Text to convert to speech
            model: TTS model to use
            voice: Voice selection
            system_prompt: System prompt (for cache key generation)
            use_cache: Whether to use/create cache
            original_image_filename: Original image filename for naming consistency

        Returns:
            Dict with audio data, metadata, and status information
        """
        if not self.client:
            return {
                "success": False,
                "error": "TTS client not initialized. Please provide a valid API key.",
            }

        # Use default system prompt if none provided
        if system_prompt is None:
            system_prompt = config.TTS_DEFAULT_SYSTEM_PROMPT

        # Validate model and voice
        if model not in config.TTS_MODELS:
            return {"success": False, "error": f"Unsupported model: {model}"}

        if voice not in config.TTS_VOICES:
            return {"success": False, "error": f"Unsupported voice: {voice}"}

        # Check text length
        cost_info = self.estimate_cost(text, model)
        if cost_info.get("exceeds_limit", False):
            return {
                "success": False,
                "error": f'Text too long: {cost_info["char_count"]} characters (max: {cost_info["max_chars"]})',
            }

        # Generate cache key and check cache
        cache_key = self._generate_cache_key(text, model, voice, system_prompt)

        if use_cache:
            cached_result = self._get_cached_audio(cache_key)
            if cached_result:
                return {
                    "success": True,
                    "audio_data": cached_result["audio_data"],
                    "metadata": cached_result["metadata"],
                    "from_cache": True,
                    "cache_key": cache_key,
                }

        # Build fallback chain: requested model first, then the TTS fallback order
        if config.MODEL_FALLBACK_ENABLED:
            models = [model] + [m for m in config.TTS_MODEL_FALLBACK_ORDER if m != model]
        else:
            models = [model]

        logger.info(f"Generating TTS: model={model}, voice={voice}, chars={len(text)}")
        logger.debug(f"Text to be spoken length: {len(text)}")

        def call_fn(candidate_model, is_last):
            try:
                call_started = time.time()
                response = with_retry(
                    self.client.audio.speech.create,
                    model=candidate_model,
                    voice=voice,
                    input=text,
                    response_format="wav",
                    **retry_kwargs_for(is_last),
                )
                return {
                    "success": True,
                    "audio_data": response.content,
                    "generation_time": time.time() - call_started,
                }
            except Exception as exc:
                logger.error(f"TTS API call failed for model={candidate_model}: {exc}")
                return {"success": False, "error": str(exc), "error_category": classify_error(exc).value}

        result = run_with_fallback(models, call_fn, provider=config.PROVIDER_OPENAI)

        if not result["success"]:
            return {"success": False, "error": f"TTS generation failed: {result['error']}"}

        audio_data = result["audio_data"]
        generation_time = result["generation_time"]
        fallback_used = result.get("fallback_used", False)
        fallback_info = result.get("fallback_info")
        used_model = fallback_info["used_model"] if fallback_used and fallback_info else model

        logger.info(f"🎶 Audio generation completed: {len(audio_data)} bytes in {generation_time:.2f}s")

        # Cache under a key derived from the model that actually produced this
        # audio, so a fallback result isn't served as a cache hit for the
        # originally-requested model on a future identical request.
        result_cache_key = (
            self._generate_cache_key(text, used_model, voice, system_prompt)
            if used_model != model else cache_key
        )
        cost_info = self.estimate_cost(text, used_model)

        # Create metadata
        metadata = {
            "model": used_model,
            "voice": voice,
            "text_length": len(text),
            "actual_text_length": len(
                text
            ),  # Now same as text_length since no system prompt
            "generation_time": round(generation_time, 2),
            "generated_at": datetime.now().isoformat(),
            "cache_key": result_cache_key,
            "estimated_cost": cost_info["estimated_cost"],
            "voice_description": config.TTS_VOICES[voice]["description"],
        }

        # Add original image filename and text if provided
        if original_image_filename:
            metadata["original_image_filename"] = original_image_filename
        metadata["original_text"] = (
            text  # Store the original text for filename fallback
        )

        # Cache the result
        if use_cache:
            self._save_to_cache(result_cache_key, audio_data, metadata)

        logger.info(
            f"TTS generation successful: {len(audio_data)} bytes in {generation_time:.2f}s"
        )

        return {
            "success": True,
            "audio_data": audio_data,
            "metadata": metadata,
            "from_cache": False,
            "cache_key": result_cache_key,
            "model_used": used_model,
            "fallback_used": fallback_used,
            "fallback_info": fallback_info,
        }

    def clear_cache(self) -> Dict[str, Union[int, str]]:
        """
        Clear all cached audio files.

        Returns:
            Dict with cleanup statistics
        """
        try:
            audio_files = list(self.cache_dir.glob("*.wav"))
            metadata_files = list(self.cache_dir.glob("*.json"))

            files_removed = 0
            for file_path in audio_files + metadata_files:
                try:
                    file_path.unlink()
                    files_removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {file_path}: {e}")

            logger.info(f"Cache cleared: {files_removed} files removed")
            return {"files_removed": files_removed, "status": "success"}

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return {"files_removed": 0, "status": "error", "error": str(e)}

    def get_cache_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get statistics about the current cache.

        Returns:
            Dict with cache statistics
        """
        try:
            audio_files = list(self.cache_dir.glob("*.wav"))
            metadata_files = list(self.cache_dir.glob("*.json"))

            total_size = sum(f.stat().st_size for f in audio_files)
            total_size_mb = total_size / (1024 * 1024)

            return {
                "audio_files": len(audio_files),
                "metadata_files": len(metadata_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size_mb, 2),
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "audio_files": 0,
                "metadata_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
            }


# Convenience functions for easy integration
def create_tts_engine(api_key: str) -> TTSEngine:
    """Create and initialize a TTS engine with the given API key."""
    return TTSEngine(api_key)


def get_available_models() -> Dict[str, Dict]:
    """Get all available TTS models."""
    return config.TTS_MODELS


def get_available_voices() -> Dict[str, Dict]:
    """Get all available voices with descriptions."""
    return config.TTS_VOICES


def get_default_system_prompt() -> str:
    """Get the default Civil War era system prompt."""
    return config.TTS_DEFAULT_SYSTEM_PROMPT


# Initialize cache cleanup on module import
def cleanup_cache_on_startup():
    """Clean up cache files on application startup."""
    try:
        engine = TTSEngine()
        result = engine.clear_cache()
        logger.info(f"Startup cache cleanup completed: {result}")
    except Exception as e:
        logger.warning(f"Startup cache cleanup failed: {e}")


# Automatically clean cache on startup
cleanup_cache_on_startup()
