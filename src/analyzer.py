"""Analyse downloaded creative images and generate a Markdown report.

Two analysis tiers:

1. **Basic** (offline, Pillow-only) — dimensions, file size, dominant
   colours via K-means, aspect-ratio distribution.
2. **LLM Vision** (optional) — reserved interface for calling a vision
   model through the OpenClaw model channel to describe content, style,
   and copy patterns.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from src.config import AnalysisConfig

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class ImageStats:
    path: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    file_size_kb: float = 0.0
    dominant_colours: list[str] = field(default_factory=list)
    aspect_ratio: str = ""
    llm_description: str = ""


@dataclass
class ReportData:
    generated_at: str = ""
    total_items: int = 0
    items: list[dict] = field(default_factory=list)
    image_stats: list[ImageStats] = field(default_factory=list)
    channel_distribution: dict[str, int] = field(default_factory=dict)
    size_distribution: dict[str, int] = field(default_factory=dict)
    llm_summary: str = ""


# ------------------------------------------------------------------
# Colour helpers (simple K-means on pixel sample)
# ------------------------------------------------------------------

def _dominant_colours(img: Image.Image, n: int = 3) -> list[str]:
    """Return the top-*n* dominant colours as hex strings."""
    small = img.copy()
    small.thumbnail((64, 64))
    if small.mode != "RGB":
        small = small.convert("RGB")

    try:
        pixels = list(small.get_flattened_data())
    except AttributeError:
        pixels = list(small.getdata())
    if not pixels:
        return []

    counter: Counter[tuple[int, int, int]] = Counter()
    for px in pixels:
        quantized = (px[0] // 32 * 32, px[1] // 32 * 32, px[2] // 32 * 32)
        counter[quantized] += 1

    return [
        f"#{r:02x}{g:02x}{b:02x}"
        for (r, g, b), _ in counter.most_common(n)
    ]


def _aspect_label(w: int, h: int) -> str:
    if w == 0 or h == 0:
        return "unknown"
    ratio = w / h
    if ratio > 1.3:
        return "横版"
    if ratio < 0.77:
        return "竖版"
    return "方形"


# ------------------------------------------------------------------
# LLM Vision interface (reserved)
# ------------------------------------------------------------------

def analyze_with_llm(
    image_path: Path,
    model_config: dict[str, Any],
) -> str:
    """Call a vision-capable LLM to describe the creative.

    This is a **reserved interface**.  When an OpenClaw model channel
    that supports vision is available, implement the HTTP call here
    and return a text description.

    Parameters
    ----------
    image_path:
        Local path to the image file.
    model_config:
        Dict with at least ``{"model": "<channel-name>"}``.  May
        contain ``api_base``, ``api_key``, etc. depending on the
        provider.

    Returns
    -------
    str
        Natural-language description of the image content.
    """
    logger.info("LLM Vision 分析暂未实现 — 预留接口 (%s)", image_path.name)
    return ""


# ------------------------------------------------------------------
# Core analyser
# ------------------------------------------------------------------

class CreativeAnalyzer:
    """Analyse a set of downloaded creative images."""

    def __init__(self, config: AnalysisConfig) -> None:
        self._cfg = config

    def analyze(self, image_dir: Path) -> ReportData:
        """Run analysis on all images inside *image_dir*."""
        meta_path = image_dir / "metadata.json"
        metadata: list[dict] = []
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        image_files = sorted(
            p for p in image_dir.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        )

        report = ReportData(
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_items=len(image_files),
            items=metadata,
        )

        channel_counter: Counter[str] = Counter()
        size_counter: Counter[str] = Counter()

        for img_path in image_files:
            stats = self._analyze_one(img_path)
            report.image_stats.append(stats)
            size_counter[stats.aspect_ratio] += 1

        for item in metadata:
            ch = item.get("channel", "")
            if ch:
                channel_counter[ch] += 1

        report.channel_distribution = dict(channel_counter.most_common())
        report.size_distribution = dict(size_counter.most_common())

        if self._cfg.llm_enabled and self._cfg.llm_model:
            report.llm_summary = self._run_llm_summary(image_files)

        return report

    def _analyze_one(self, path: Path) -> ImageStats:
        stats = ImageStats(path=path.name)
        try:
            stats.file_size_kb = round(path.stat().st_size / 1024, 1)
            with Image.open(path) as img:
                stats.width, stats.height = img.size
                stats.format = img.format or path.suffix.lstrip(".").upper()
                if self._cfg.basic_enabled:
                    stats.dominant_colours = _dominant_colours(img)
                stats.aspect_ratio = _aspect_label(stats.width, stats.height)
        except Exception as exc:
            logger.warning("分析失败 %s: %s", path.name, exc)
        return stats

    def _run_llm_summary(self, image_files: list[Path]) -> str:
        """Batch-call LLM Vision for all images and produce a summary."""
        descriptions: list[str] = []
        model_cfg = {"model": self._cfg.llm_model}
        for path in image_files:
            desc = analyze_with_llm(path, model_cfg)
            if desc:
                descriptions.append(f"#{path.stem}: {desc}")
        if not descriptions:
            return ""
        return "\n".join(descriptions)


# ------------------------------------------------------------------
# Markdown report generator
# ------------------------------------------------------------------

def generate_markdown_report(report: ReportData, image_dir: Path) -> str:
    """Render a ``ReportData`` object into a Markdown string."""
    lines: list[str] = []

    lines.append("# 广大大本周买量素材 TOP20 分析报告")
    lines.append("")
    lines.append(f"> 生成时间: {report.generated_at} | 数据来源: guangdada.net")
    lines.append("")

    # ---- Overview ----
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 采集素材数: {report.total_items}")

    if report.channel_distribution:
        parts = ", ".join(f"{ch} ({cnt})" for ch, cnt in report.channel_distribution.items())
        lines.append(f"- 主要媒体渠道: {parts}")

    if report.size_distribution:
        total = sum(report.size_distribution.values()) or 1
        parts = ", ".join(
            f"{label} ({cnt}/{total}, {cnt * 100 // total}%)"
            for label, cnt in report.size_distribution.items()
        )
        lines.append(f"- 版式分布: {parts}")

    if report.image_stats:
        sizes = [f"{s.width}x{s.height}" for s in report.image_stats if s.width]
        if sizes:
            common = Counter(sizes).most_common(3)
            parts = ", ".join(f"{sz} ({cnt})" for sz, cnt in common)
            lines.append(f"- 常见尺寸: {parts}")

    lines.append("")

    # ---- Item table ----
    lines.append("## TOP20 素材列表")
    lines.append("")
    lines.append("| 排名 | 预览 | 标题 | 投放天数 | 渠道 | 尺寸 | 文件大小 |")
    lines.append("|------|------|------|---------|------|------|---------|")

    for item_meta, stats in _zip_items(report):
        rank = item_meta.get("rank", "")
        title = item_meta.get("title", "") or "-"
        days = item_meta.get("days", "") or "-"
        channel = item_meta.get("channel", "") or "-"
        img_ref = f"![{rank}](./{stats.path})" if stats.path else "-"
        size = f"{stats.width}x{stats.height}" if stats.width else "-"
        fsize = f"{stats.file_size_kb} KB" if stats.file_size_kb else "-"
        lines.append(f"| {rank} | {img_ref} | {title} | {days} | {channel} | {size} | {fsize} |")

    lines.append("")

    # ---- Colour palette ----
    all_colours: Counter[str] = Counter()
    for s in report.image_stats:
        for c in s.dominant_colours:
            all_colours[c] += 1
    if all_colours:
        lines.append("## 色彩趋势")
        lines.append("")
        top_colours = all_colours.most_common(6)
        lines.append("最常出现的主色调:")
        lines.append("")
        for colour, cnt in top_colours:
            lines.append(f"- `{colour}` ({cnt} 次)")
        lines.append("")

    # ---- LLM summary ----
    if report.llm_summary:
        lines.append("## AI 趋势总结")
        lines.append("")
        lines.append(report.llm_summary)
        lines.append("")
    else:
        lines.append("## 趋势总结")
        lines.append("")
        lines.append("> LLM Vision 分析未启用。启用后将在此输出 AI 归纳的素材风格、文案特点和视觉趋势。")
        lines.append("> 设置 `analysis.llm_enabled: true` 和 `analysis.llm_model` 以开启。")
        lines.append("")

    return "\n".join(lines)


def _zip_items(report: ReportData):
    """Yield ``(item_dict, ImageStats)`` pairs, filling gaps."""
    stats_by_name: dict[str, ImageStats] = {s.path: s for s in report.image_stats}
    empty = ImageStats()

    if report.items:
        for item in report.items:
            fname_candidates = [
                s for s in report.image_stats
                if s.path.startswith(f"{item.get('rank', 0):02d}_")
            ]
            stats = fname_candidates[0] if fname_candidates else empty
            yield item, stats
    else:
        for stats in report.image_stats:
            yield {"rank": "", "title": stats.path}, stats


def save_report(report: ReportData, image_dir: Path) -> Path:
    """Write the Markdown report to *image_dir* / ``report.md``."""
    md = generate_markdown_report(report, image_dir)
    out = image_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    logger.info("报告已保存至 %s", out)
    return out
