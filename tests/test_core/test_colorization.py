"""Tests for the colour helpers in backend/core/transcription_utils.py.

Colorization used matplotlib colormaps, and the NER path called
matplotlib.cm.get_cmap, which matplotlib 3.9 removed — so on a fresh install
"Named Entities" colorization raised AttributeError. The palette and gradient
are now plain Python; these tests pin that they still match matplotlib's
output and that the app no longer imports matplotlib at startup.
"""

import subprocess
import sys
from pathlib import Path

import pytest

import transcription_utils as tu

BACKEND = Path(__file__).resolve().parents[2] / "backend"


class TestNerColorization:
    BUNDLE = {
        "entities": [
            {"entity_id": "E1", "canonical": "Robert E. Lee", "observed_variants": ["Lee"]},
            {"entity_id": "E2", "canonical": "Richmond", "observed_variants": ["Richmond"]},
        ]
    }

    def test_highlights_entities_with_a_legend(self):
        html = tu.colorize_ner_gemini("General Lee rode to Richmond.", self.BUNDLE, 0)
        assert html is not None
        assert ">Lee</span>" in html and ">Richmond</span>" in html
        assert tu.TAB10[0] in html and tu.TAB10[1] in html  # legend swatches
        assert "E1: Robert E. Lee" in html

    def test_returns_none_when_nothing_matches(self):
        assert tu.colorize_ner_gemini("Nothing here.", self.BUNDLE, 0) is None

    def test_palette_cycles_past_ten_entities(self):
        bundle = {
            "entities": [
                {"entity_id": f"E{i}", "canonical": f"w{i}", "observed_variants": [f"w{i}"]}
                for i in range(12)
            ]
        }
        text = " ".join(f"w{i}" for i in range(12))
        assert tu.colorize_ner_gemini(text, bundle, 0) is not None


class TestGradient:
    def test_endpoints_and_clamping(self):
        assert tu.gradient_rgb(0) == (0, 128, 0)
        assert tu.gradient_rgb(1) == (255, 0, 0)
        assert tu.gradient_rgb(-5) == tu.gradient_rgb(0)
        assert tu.gradient_rgb(7) == tu.gradient_rgb(1)

    def test_word_and_char_colorizers_render(self):
        assert "rgba(0, 128, 0, 0.0)" in tu.colorize_words("a b", [0, 1])
        assert "rgba(255, 0, 0, 0.4)" in tu.colorize_chars("ab", [0, 1])


class TestMatchesMatplotlib:
    """matplotlib remains a dependency (consistency figures), so compare against it."""

    def test_palette_is_matplotlib_tab10(self):
        mpl = pytest.importorskip("matplotlib")
        from matplotlib.colors import to_hex

        assert tu.TAB10 == [to_hex(c) for c in mpl.colormaps["tab10"].colors]

    def test_gradient_matches_the_old_colormap(self):
        pytest.importorskip("matplotlib")
        from matplotlib.colors import LinearSegmentedColormap

        cmap = LinearSegmentedColormap.from_list("g", ["green", "yellow", "orange", "red"])
        for i in range(101):
            v = i / 100
            expected = [int(c * 255) for c in cmap(v)[:3]]
            got = tu.gradient_rgb(v)
            assert all(abs(a - b) <= 3 for a, b in zip(got, expected)), (v, got, expected)


def test_importing_the_app_does_not_import_matplotlib(tmp_path):
    """Startup cost: matplotlib should load only when a figure is rendered."""
    code = (
        "import sys; import main; "
        "print('matplotlib' in sys.modules)"
    )
    env = {
        **__import__("os").environ,
        "TRANSCRIBE_HTR_LOG_DIR": str(tmp_path / "logs"),
        "TRANSCRIBE_HTR_CACHE_DIR": str(tmp_path / "cache"),
        "TRANSCRIBE_HTR_DATA_DIR": str(tmp_path / "data"),
    }
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "False"
