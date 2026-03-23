"""Tests for the image analyser and report generator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from src.analyzer import (
    CreativeAnalyzer,
    ReportData,
    generate_markdown_report,
    save_report,
    _dominant_colours,
    _aspect_label,
)
from src.config import AnalysisConfig


@pytest.fixture()
def sample_dir(tmp_path: Path) -> Path:
    """Create a temp directory with synthetic test images + metadata."""
    for i in range(1, 4):
        img = Image.new("RGB", (1080, 1920), color=(255 * (i % 2), 100, 50 * i))
        img.save(tmp_path / f"{i:02d}_sample.jpg")

    metadata = [
        {"rank": 1, "title": "Sample A", "image_url": "", "days": "7天", "channel": "Facebook", "detail_url": "", "extra": {}},
        {"rank": 2, "title": "Sample B", "image_url": "", "days": "3天", "channel": "TikTok", "detail_url": "", "extra": {}},
        {"rank": 3, "title": "Sample C", "image_url": "", "days": "14天", "channel": "Facebook", "detail_url": "", "extra": {}},
    ]
    (tmp_path / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    return tmp_path


class TestHelpers:
    def test_aspect_label_landscape(self) -> None:
        assert _aspect_label(1920, 1080) == "横版"

    def test_aspect_label_portrait(self) -> None:
        assert _aspect_label(1080, 1920) == "竖版"

    def test_aspect_label_square(self) -> None:
        assert _aspect_label(1080, 1080) == "方形"

    def test_aspect_label_zero(self) -> None:
        assert _aspect_label(0, 100) == "unknown"

    def test_dominant_colours(self) -> None:
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        colours = _dominant_colours(img, n=1)
        assert len(colours) == 1
        assert colours[0].startswith("#")


class TestAnalyzer:
    def test_analyze(self, sample_dir: Path) -> None:
        cfg = AnalysisConfig(basic_enabled=True, llm_enabled=False)
        analyzer = CreativeAnalyzer(cfg)
        report = analyzer.analyze(sample_dir)
        assert report.total_items == 3
        assert len(report.image_stats) == 3
        assert report.channel_distribution.get("Facebook") == 2
        assert report.channel_distribution.get("TikTok") == 1

    def test_analyze_produces_stats(self, sample_dir: Path) -> None:
        cfg = AnalysisConfig(basic_enabled=True)
        analyzer = CreativeAnalyzer(cfg)
        report = analyzer.analyze(sample_dir)
        for s in report.image_stats:
            assert s.width == 1080
            assert s.height == 1920
            assert s.aspect_ratio == "竖版"
            assert s.file_size_kb > 0


class TestMarkdownReport:
    def test_generate_report(self, sample_dir: Path) -> None:
        cfg = AnalysisConfig(basic_enabled=True)
        analyzer = CreativeAnalyzer(cfg)
        report = analyzer.analyze(sample_dir)
        md = generate_markdown_report(report, sample_dir)
        assert "广大大本周买量素材 TOP20 分析报告" in md
        assert "Facebook" in md
        assert "TikTok" in md
        assert "竖版" in md

    def test_save_report(self, sample_dir: Path) -> None:
        cfg = AnalysisConfig(basic_enabled=True)
        analyzer = CreativeAnalyzer(cfg)
        report = analyzer.analyze(sample_dir)
        path = save_report(report, sample_dir)
        assert path.exists()
        assert path.name == "report.md"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100
