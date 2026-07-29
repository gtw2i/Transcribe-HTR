import time
import tracemalloc

import numpy as np
from transcription_utils import compute_token_disagreement


def _build_transcriptions(count: int, words_per_text: int) -> list[str]:
    base_words = [f"w{i}" for i in range(words_per_text)]
    texts = []
    for idx in range(count):
        words = base_words.copy()
        step = max(1, words_per_text // 12)
        for j in range(idx % 7, words_per_text, step):
            words[j] = f"v{idx}_{j}"
        texts.append(" ".join(words))
    return texts


def _timed_disagreement(transcriptions: list[str], level: str) -> tuple[list[np.ndarray], float]:
    started = time.perf_counter()
    result = compute_token_disagreement(transcriptions, level=level)
    elapsed = time.perf_counter() - started
    return result, elapsed


def test_word_level_disagreement_completes_under_budget_for_medium_batch():
    transcriptions = _build_transcriptions(count=10, words_per_text=180)

    result, elapsed = _timed_disagreement(transcriptions, level="word")

    assert len(result) == len(transcriptions)
    assert all(isinstance(v, np.ndarray) for v in result)
    assert elapsed < 4.0


def test_char_level_disagreement_peak_memory_stays_below_single_machine_budget():
    # 256 MB budget target for constrained single-machine scenarios.
    transcriptions = _build_transcriptions(count=6, words_per_text=90)

    tracemalloc.start()
    try:
        result, _ = _timed_disagreement(transcriptions, level="char")
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(result) == len(transcriptions)
    assert peak < 256 * 1024 * 1024


def test_disagreement_scaling_ratio_remains_within_expected_bound():
    # Compare small vs larger workload and ensure growth is bounded.
    small = _build_transcriptions(count=4, words_per_text=120)
    medium = _build_transcriptions(count=8, words_per_text=120)

    _, t_small = _timed_disagreement(small, level="word")
    _, t_medium = _timed_disagreement(medium, level="word")

    # Allow wide headroom for noisy/shared machines while still detecting runaway regressions.
    ratio = t_medium / max(t_small, 1e-6)
    assert ratio < 8.0


def test_repeated_medium_runs_do_not_show_runaway_peak_memory():
    transcriptions = _build_transcriptions(count=8, words_per_text=140)

    peaks = []
    for _ in range(3):
        tracemalloc.start()
        try:
            compute_token_disagreement(transcriptions, level="word")
            _, peak = tracemalloc.get_traced_memory()
            peaks.append(peak)
        finally:
            tracemalloc.stop()

    # Peak memory should stay in the same general band across repeated runs.
    assert max(peaks) < 256 * 1024 * 1024
    assert max(peaks) <= min(peaks) * 2.5
