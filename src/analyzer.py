"""Analyse downloaded creative images and generate a Markdown report.

Produces structured insights from metadata + basic image analysis,
with a reserved interface for LLM Vision deep analysis.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from src.config import AnalysisConfig

logger = logging.getLogger(__name__)


@dataclass
class ImageStats:
    path: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    file_size_kb: float = 0.0
    dominant_colours: list[str] = field(default_factory=list)
    aspect_ratio: str = ""


@dataclass
class ReportData:
    generated_at: str = ""
    total_items: int = 0
    items: list[dict] = field(default_factory=list)
    image_stats: list[ImageStats] = field(default_factory=list)


def _dominant_colours(img: Image.Image, n: int = 3) -> list[str]:
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
    return [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in counter.most_common(n)]


def _aspect_label(w: int, h: int) -> str:
    if w == 0 or h == 0:
        return "unknown"
    ratio = w / h
    if ratio > 1.3:
        return "横版"
    if ratio < 0.77:
        return "竖版"
    return "方形"


def analyze_with_llm(image_path: Path, model_config: dict[str, Any]) -> str:
    """Reserved: call vision LLM to describe the creative."""
    logger.info("LLM Vision not implemented yet (%s)", image_path.name)
    return ""


class CreativeAnalyzer:
    def __init__(self, config: AnalysisConfig) -> None:
        self._cfg = config

    def analyze(self, image_dir: Path) -> ReportData:
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

        for img_path in image_files:
            stats = self._analyze_one(img_path)
            report.image_stats.append(stats)

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
            logger.warning("Analysis failed %s: %s", path.name, exc)
        return stats


# ------------------------------------------------------------------
# Markdown report
# ------------------------------------------------------------------

def generate_markdown_report(report: ReportData, image_dir: Path) -> str:
    lines: list[str] = []
    items = report.items

    lines.append("# 广大大本周买量素材 TOP 分析报告")
    lines.append("")
    lines.append(f"> 生成时间: {report.generated_at} | 数据来源: guangdada.net 每周热门榜")
    lines.append("")

    # === Overview ===
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 采集素材数: **{report.total_items}**")

    # Popularity range
    pops = [it.get("popularity", "") for it in items if it.get("popularity")]
    if pops:
        lines.append(f"- 人气值范围: {pops[-1]} ~ {pops[0]}")

    # Industry distribution
    ind_counter: Counter[str] = Counter()
    for it in items:
        for tag in it.get("industry_tags", []):
            ind_counter[tag] += 1
    if ind_counter:
        parts = ", ".join(f"**{tag}** ({cnt})" for tag, cnt in ind_counter.most_common(8))
        lines.append(f"- 行业分布: {parts}")

    # Style distribution
    style_counter: Counter[str] = Counter()
    for it in items:
        for tag in it.get("style_tags", []):
            style_counter[tag] += 1
    if style_counter:
        parts = ", ".join(f"{tag} ({cnt})" for tag, cnt in style_counter.most_common(8))
        lines.append(f"- 创意风格: {parts}")

    # Aspect ratio
    aspect_counter: Counter[str] = Counter()
    for s in report.image_stats:
        if s.aspect_ratio and s.aspect_ratio != "unknown":
            aspect_counter[s.aspect_ratio] += 1
    if aspect_counter:
        total = sum(aspect_counter.values()) or 1
        parts = ", ".join(f"{label} {cnt*100//total}%" for label, cnt in aspect_counter.most_common())
        lines.append(f"- 版式: {parts}")

    # Duration
    durations = [it.get("duration_days", 0) for it in items if it.get("duration_days")]
    if durations:
        avg = sum(durations) / len(durations)
        lines.append(f"- 平均投放天数: **{avg:.0f}天** (最短 {min(durations)}天, 最长 {max(durations)}天)")

    lines.append("")

    # === Top advertisers ===
    adv_counter: Counter[str] = Counter()
    for it in items:
        adv = it.get("advertiser", "")
        if adv:
            adv_counter[adv] += 1
    if adv_counter:
        lines.append("## 热门广告主")
        lines.append("")
        lines.append("| 广告主 | 上榜素材数 | 发行商 |")
        lines.append("|--------|-----------|--------|")
        adv_publisher: dict[str, str] = {}
        for it in items:
            adv = it.get("advertiser", "")
            pub = it.get("publisher", "")
            if adv and pub:
                adv_publisher[adv] = pub
        for adv, cnt in adv_counter.most_common(10):
            pub = adv_publisher.get(adv, "-")
            lines.append(f"| {adv} | {cnt} | {pub} |")
        lines.append("")

    # === Item table ===
    lines.append("## 素材详情")
    lines.append("")
    lines.append("| # | 预览 | 广告主 | 人气值 | 行业 | 风格 | 投放天数 | 日期范围 |")
    lines.append("|---|------|--------|--------|------|------|---------|---------|")

    stats_by_rank: dict[int, ImageStats] = {}
    for s in report.image_stats:
        # Match by filename prefix like "01_"
        try:
            r = int(s.path.split("_")[0])
            stats_by_rank[r] = s
        except (ValueError, IndexError):
            pass

    for it in items:
        rank = it.get("rank", "")
        adv = it.get("advertiser", "") or "-"
        pop = it.get("popularity", "") or "-"
        ind = ", ".join(it.get("industry_tags", [])) or "-"
        sty = ", ".join(it.get("style_tags", [])) or "-"
        dur = it.get("duration_days", "")
        dur_str = f"{dur}天" if dur else "-"
        ds = it.get("date_start", "")
        de = it.get("date_end", "")
        date_range = f"{ds}~{de}" if ds and de else "-"

        s = stats_by_rank.get(rank)
        img_ref = f"![{rank}](./{s.path})" if s else "-"

        lines.append(f"| {rank} | {img_ref} | {adv} | {pop} | {ind} | {sty} | {dur_str} | {date_range} |")

    lines.append("")

    # === Insights ===
    lines.append("## 趋势洞察")
    lines.append("")

    if ind_counter:
        top_ind = ind_counter.most_common(1)[0]
        lines.append(f"1. **行业集中度**: 本周热门素材以「{top_ind[0]}」行业为主 ({top_ind[1]}/{report.total_items} 个素材)，")
        if len(ind_counter) > 1:
            second = ind_counter.most_common(2)[1]
            lines.append(f"   其次是「{second[0]}」({second[1]} 个)。")

    if style_counter:
        top_style = style_counter.most_common(1)[0]
        lines.append(f"2. **创意风格**: 「{top_style[0]}」是最常见的创意形式 ({top_style[1]} 次)，")
        real_person = sum(cnt for tag, cnt in style_counter.items() if "真人" in tag or "口播" in tag or "情景" in tag)
        design = sum(cnt for tag, cnt in style_counter.items() if "设计" in tag or "插画" in tag or "卡通" in tag)
        if real_person and design:
            lines.append(f"   真人类素材出现 {real_person} 次 vs 设计类 {design} 次。")

    if durations:
        long_run = [it for it in items if it.get("duration_days", 0) >= 30]
        if long_run:
            names = ", ".join(it.get("advertiser", "?")[:20] for it in long_run[:3])
            lines.append(f"3. **长效素材**: {len(long_run)} 个素材投放超过 30 天 ({names})，说明这些创意具有持久吸引力。")

    if adv_counter:
        repeat_advs = [(a, c) for a, c in adv_counter.items() if c >= 2]
        if repeat_advs:
            names = ", ".join(f"{a}({c}个)" for a, c in repeat_advs[:3])
            lines.append(f"4. **重复上榜**: {names} — 同一广告主多素材上榜，值得重点关注其投放策略。")

    lines.append("")
    return "\n".join(lines)


def save_report(report: ReportData, image_dir: Path) -> Path:
    md = generate_markdown_report(report, image_dir)
    out = image_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    logger.info("Report saved to %s", out)
    return out
