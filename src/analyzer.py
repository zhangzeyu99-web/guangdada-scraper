"""Analyse downloaded creative images and generate a Markdown report.

Produces structured insights from metadata + basic image analysis,
with a reserved interface for LLM Vision deep analysis.
"""
from __future__ import annotations

import json
import logging
import math
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


def _colour_name(hex_colour: str) -> str:
    """Map a hex colour to a human-readable Chinese name."""
    try:
        r, g, b = int(hex_colour[1:3], 16), int(hex_colour[3:5], 16), int(hex_colour[5:7], 16)
    except (ValueError, IndexError):
        return hex_colour
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    if brightness < 40:
        return "深色/黑"
    if brightness > 220:
        return "浅色/白"
    if r > 180 and g < 80 and b < 80:
        return "红"
    if r > 180 and g > 100 and b < 80:
        return "橙/黄"
    if g > 150 and r < 100 and b < 100:
        return "绿"
    if b > 150 and r < 100 and g < 100:
        return "蓝"
    if r > 130 and b > 130 and g < 100:
        return "紫"
    if brightness > 160:
        return "浅色调"
    return "中间调"


def _parse_popularity(pop: str) -> float:
    """Parse '42万' → 420000, '1.5亿' → 150000000."""
    if not pop:
        return 0
    pop = pop.strip()
    try:
        if "亿" in pop:
            return float(pop.replace("亿", "")) * 1e8
        if "万" in pop:
            return float(pop.replace("万", "")) * 1e4
        return float(pop)
    except ValueError:
        return 0


def _classify_creative_type(style_tags: list[str]) -> str:
    """Classify into broad creative type based on style tags."""
    tags_set = set(style_tags)
    if tags_set & {"真人口播", "真人", "情景剧"}:
        return "真人/UGC"
    if tags_set & {"插画", "卡通", "中国风", "日系"}:
        return "插画/手绘"
    if tags_set & {"3D"}:
        return "3D渲染"
    if tags_set & {"平面设计", "现代"}:
        return "平面设计"
    return "其他"


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
# Markdown report generator
# ------------------------------------------------------------------

def generate_markdown_report(report: ReportData, image_dir: Path) -> str:
    lines: list[str] = []
    items = report.items
    total = report.total_items or len(items)

    lines.append("# 广大大本周买量素材 TOP 分析报告")
    lines.append("")
    lines.append(f"> 生成时间: {report.generated_at} | 数据来源: guangdada.net 每周热门榜")
    lines.append("")
    lines.append("---")
    lines.append("")

    # =================================================================
    # 1. Dashboard overview
    # =================================================================
    lines.append("## 1. 数据概览")
    lines.append("")

    pops = [_parse_popularity(it.get("popularity", "")) for it in items]
    pops_display = [it.get("popularity", "") for it in items if it.get("popularity")]
    durations = [it.get("duration_days", 0) for it in items if it.get("duration_days")]

    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 采集素材数 | **{total}** |")
    if pops_display:
        lines.append(f"| 人气值范围 | {pops_display[-1]} ~ {pops_display[0]} |")
        avg_pop = sum(pops) / len(pops) if pops else 0
        if avg_pop >= 1e4:
            lines.append(f"| 平均人气值 | {avg_pop/1e4:.1f}万 |")
    if durations:
        lines.append(f"| 平均投放天数 | **{sum(durations)/len(durations):.0f}天** |")
        lines.append(f"| 投放天数范围 | {min(durations)}天 ~ {max(durations)}天 |")
    lines.append("")

    # =================================================================
    # 2. Industry analysis
    # =================================================================
    ind_counter: Counter[str] = Counter()
    for it in items:
        for tag in it.get("industry_tags", []):
            ind_counter[tag] += 1

    lines.append("## 2. 行业分布")
    lines.append("")
    if ind_counter:
        lines.append("| 行业 | 素材数 | 占比 |")
        lines.append("|------|--------|------|")
        for tag, cnt in ind_counter.most_common():
            pct = cnt * 100 // total if total else 0
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            lines.append(f"| {tag} | {cnt} | {bar} {pct}% |")
        lines.append("")

        top_ind = ind_counter.most_common(1)[0]
        lines.append(f"> 本周热门素材以 **{top_ind[0]}** 行业为主，占据 {top_ind[1]}/{total} 个席位。")
        no_ind = sum(1 for it in items if not it.get("industry_tags"))
        if no_ind:
            lines.append(f"> 有 {no_ind} 个素材未标注行业分类。")
    else:
        lines.append("暂无行业标签数据。")
    lines.append("")

    # =================================================================
    # 3. Creative style analysis
    # =================================================================
    style_counter: Counter[str] = Counter()
    for it in items:
        for tag in it.get("style_tags", []):
            style_counter[tag] += 1

    type_counter: Counter[str] = Counter()
    for it in items:
        ctype = _classify_creative_type(it.get("style_tags", []))
        type_counter[ctype] += 1

    lines.append("## 3. 创意风格分析")
    lines.append("")

    if type_counter:
        lines.append("### 创意类型分布")
        lines.append("")
        lines.append("| 类型 | 素材数 | 占比 |")
        lines.append("|------|--------|------|")
        for ctype, cnt in type_counter.most_common():
            pct = cnt * 100 // total if total else 0
            lines.append(f"| {ctype} | {cnt} | {pct}% |")
        lines.append("")

    if style_counter:
        lines.append("### 风格标签频次")
        lines.append("")
        parts = " · ".join(f"**{tag}**({cnt})" for tag, cnt in style_counter.most_common(10))
        lines.append(parts)
        lines.append("")

    # =================================================================
    # 4. Color analysis
    # =================================================================
    color_counter: Counter[str] = Counter()
    for it in items:
        for tag in it.get("color_tags", []):
            color_counter[tag] += 1

    img_colour_names: Counter[str] = Counter()
    for s in report.image_stats:
        for hex_c in s.dominant_colours[:2]:
            name = _colour_name(hex_c)
            img_colour_names[name] += 1

    lines.append("## 4. 色彩分析")
    lines.append("")

    if color_counter:
        lines.append("### 广大大标注色彩")
        lines.append("")
        parts = " · ".join(f"{tag}({cnt})" for tag, cnt in color_counter.most_common())
        lines.append(parts)
        lines.append("")

    if img_colour_names:
        lines.append("### 图片实际主色调")
        lines.append("")
        lines.append("| 色系 | 出现次数 |")
        lines.append("|------|---------|")
        for name, cnt in img_colour_names.most_common(6):
            lines.append(f"| {name} | {cnt} |")
        lines.append("")

    # =================================================================
    # 5. Advertiser analysis
    # =================================================================
    adv_counter: Counter[str] = Counter()
    adv_pop: dict[str, list[float]] = {}
    adv_publisher: dict[str, str] = {}
    adv_duration: dict[str, list[int]] = {}
    for it in items:
        adv = it.get("advertiser", "")
        if not adv:
            continue
        adv_counter[adv] += 1
        pop_val = _parse_popularity(it.get("popularity", ""))
        adv_pop.setdefault(adv, []).append(pop_val)
        adv_publisher.setdefault(adv, it.get("publisher", ""))
        dur = it.get("duration_days", 0)
        if dur:
            adv_duration.setdefault(adv, []).append(dur)

    lines.append("## 5. 广告主分析")
    lines.append("")

    if adv_counter:
        lines.append("| 广告主 | 发行商 | 上榜数 | 总人气 | 平均投放天数 |")
        lines.append("|--------|--------|--------|--------|-------------|")
        for adv, cnt in adv_counter.most_common(10):
            pub = adv_publisher.get(adv, "-")
            total_pop = sum(adv_pop.get(adv, []))
            total_pop_str = f"{total_pop/1e4:.0f}万" if total_pop >= 1e4 else str(int(total_pop))
            durs = adv_duration.get(adv, [])
            avg_dur = f"{sum(durs)//len(durs)}天" if durs else "-"
            lines.append(f"| {adv} | {pub} | {cnt} | {total_pop_str} | {avg_dur} |")
        lines.append("")

        repeat_advs = [(a, c) for a, c in adv_counter.items() if c >= 2]
        if repeat_advs:
            lines.append(f"> **重复上榜广告主**: ", )
            for adv, cnt in repeat_advs:
                lines[-1] += f"{adv}（{cnt}个素材）"
            lines.append(f"> 同一广告主多素材上榜，说明其投放策略值得深入研究。")
            lines.append("")

    # =================================================================
    # 6. Duration vs popularity
    # =================================================================
    lines.append("## 6. 投放效率分析")
    lines.append("")

    items_with_both = [it for it in items if it.get("duration_days") and it.get("popularity")]
    if items_with_both:
        lines.append("| 广告主 | 人气值 | 投放天数 | 日均人气 | 效率评级 |")
        lines.append("|--------|--------|---------|---------|---------|")
        for it in items_with_both:
            adv = it.get("advertiser", "?")
            pop_str = it.get("popularity", "")
            dur = it.get("duration_days", 1)
            pop_val = _parse_popularity(pop_str)
            daily = pop_val / max(dur, 1)
            daily_str = f"{daily/1e4:.1f}万/天" if daily >= 1e4 else f"{daily:.0f}/天"

            if dur <= 7 and pop_val >= 300000:
                rating = "🔥 爆款"
            elif daily >= 50000:
                rating = "⭐ 高效"
            elif dur >= 30:
                rating = "🔄 长效"
            else:
                rating = "📊 常规"

            lines.append(f"| {adv[:25]} | {pop_str} | {dur}天 | {daily_str} | {rating} |")

        lines.append("")

        # Efficiency insight
        if len(items_with_both) >= 2:
            best = max(items_with_both, key=lambda x: _parse_popularity(x.get("popularity", "")) / max(x.get("duration_days", 1), 1))
            best_adv = best.get("advertiser", "?")
            best_daily = _parse_popularity(best.get("popularity", "")) / max(best.get("duration_days", 1), 1)
            lines.append(f"> **最高日均人气**: {best_adv} ({best_daily/1e4:.1f}万/天)，")
            if best.get("duration_days", 0) <= 7:
                lines.append(f"> 仅投放 {best.get('duration_days')} 天即达到 {best.get('popularity')} 人气，属于短期爆款型素材。")
            else:
                lines.append(f"> 持续投放 {best.get('duration_days')} 天，属于稳定长效型素材。")
        lines.append("")

    # =================================================================
    # 7. Aspect ratio & size
    # =================================================================
    aspect_counter: Counter[str] = Counter()
    for s in report.image_stats:
        if s.aspect_ratio and s.aspect_ratio != "unknown":
            aspect_counter[s.aspect_ratio] += 1

    lines.append("## 7. 版式与尺寸")
    lines.append("")
    if aspect_counter:
        lines.append("| 版式 | 数量 | 占比 | 适用场景 |")
        lines.append("|------|------|------|---------|")
        scene_map = {"竖版": "信息流/短视频", "横版": "横幅/展示广告", "方形": "社交媒体/信息流"}
        for label, cnt in aspect_counter.most_common():
            pct = cnt * 100 // total if total else 0
            scene = scene_map.get(label, "-")
            lines.append(f"| {label} | {cnt} | {pct}% | {scene} |")
        lines.append("")

    if report.image_stats:
        sizes = [f"{s.width}x{s.height}" for s in report.image_stats if s.width]
        if sizes:
            size_counter = Counter(sizes)
            lines.append("常见尺寸: " + ", ".join(f"`{sz}`({cnt})" for sz, cnt in size_counter.most_common(5)))
            lines.append("")

    # =================================================================
    # 8. Per-item detail cards
    # =================================================================
    lines.append("## 8. 素材逐条分析")
    lines.append("")

    stats_by_rank: dict[int, ImageStats] = {}
    for s in report.image_stats:
        try:
            r = int(s.path.split("_")[0])
            stats_by_rank[r] = s
        except (ValueError, IndexError):
            pass

    for it in items:
        rank = it.get("rank", 0)
        adv = it.get("advertiser", "") or "未知广告主"
        pub = it.get("publisher", "") or "-"
        pop = it.get("popularity", "") or "-"
        dur = it.get("duration_days", 0)
        ds = it.get("date_start", "")
        de = it.get("date_end", "")
        ind = it.get("industry_tags", [])
        sty = it.get("style_tags", [])
        col = it.get("color_tags", [])
        ctype = _classify_creative_type(sty)

        s = stats_by_rank.get(rank)

        lines.append(f"### #{rank} — {adv}")
        lines.append("")
        if s:
            lines.append(f"![#{rank} {adv}](./{s.path})")
            lines.append("")

        lines.append(f"| 字段 | 内容 |")
        lines.append(f"|------|------|")
        lines.append(f"| 广告主 | **{adv}** |")
        lines.append(f"| 发行商 | {pub} |")
        lines.append(f"| 周人气值 | **{pop}** |")
        lines.append(f"| 行业 | {', '.join(ind) if ind else '未分类'} |")
        lines.append(f"| 创意类型 | {ctype} |")
        lines.append(f"| 风格标签 | {', '.join(sty) if sty else '-'} |")
        lines.append(f"| 色彩标签 | {', '.join(col) if col else '-'} |")
        if dur:
            lines.append(f"| 投放时长 | {dur}天 ({ds} ~ {de}) |")
        if s:
            lines.append(f"| 尺寸 | {s.width}x{s.height} ({s.aspect_ratio}) |")
            lines.append(f"| 文件大小 | {s.file_size_kb} KB |")

        # Per-item micro insight
        pop_val = _parse_popularity(pop)
        if dur and pop_val:
            daily = pop_val / max(dur, 1)
            if dur <= 3 and pop_val >= 300000:
                lines.append(f"| 点评 | 🔥 短期爆款：仅 {dur} 天达到 {pop} 人气 |")
            elif dur >= 30:
                lines.append(f"| 点评 | 🔄 长效常青素材，已持续投放 {dur} 天 |")
            elif daily >= 50000:
                lines.append(f"| 点评 | ⭐ 高效素材，日均人气 {daily/1e4:.1f}万 |")

        lines.append("")

    # =================================================================
    # 9. Actionable takeaways
    # =================================================================
    lines.append("## 9. 可执行建议")
    lines.append("")

    suggestion_idx = 1

    # Style suggestion
    if type_counter:
        top_type = type_counter.most_common(1)[0]
        lines.append(f"{suggestion_idx}. **创意方向**: 本周 {top_type[0]} 类素材最受欢迎 ({top_type[1]}/{total})，")
        if "真人" in top_type[0] or "UGC" in top_type[0]:
            lines.append(f"   建议增加真人出镜、口播类素材的制作比例。")
        elif "平面设计" in top_type[0]:
            lines.append(f"   建议保持高质量平面设计产出，关注配色和排版规范。")
        else:
            lines.append(f"   建议参考头部素材的视觉风格进行创意迭代。")
        suggestion_idx += 1

    # Industry suggestion
    if ind_counter:
        top_ind = ind_counter.most_common(1)[0]
        lines.append(f"{suggestion_idx}. **行业机会**: {top_ind[0]} 行业素材集中度高，竞争激烈。")
        low_competition = [tag for tag, cnt in ind_counter.items() if cnt == 1]
        if low_competition:
            lines.append(f"   而 {', '.join(low_competition[:3])} 等行业竞争较少，可能存在差异化机会。")
        suggestion_idx += 1

    # Duration suggestion
    long_items = [it for it in items if it.get("duration_days", 0) >= 30]
    short_hot = [it for it in items if it.get("duration_days", 0) <= 7 and _parse_popularity(it.get("popularity", "")) >= 300000]
    if long_items:
        names = ", ".join(it.get("advertiser", "?")[:20] for it in long_items[:3])
        lines.append(f"{suggestion_idx}. **长效素材参考**: {names} 已持续投放超 30 天仍在榜，其创意方向具有长期生命力，值得拆解学习。")
        suggestion_idx += 1
    if short_hot:
        names = ", ".join(it.get("advertiser", "?")[:20] for it in short_hot[:3])
        lines.append(f"{suggestion_idx}. **爆款参考**: {names} 短期内迅速获得高人气，建议分析其「吸睛元素」和投放节奏。")
        suggestion_idx += 1

    # Format suggestion
    if aspect_counter:
        top_aspect = aspect_counter.most_common(1)[0]
        lines.append(f"{suggestion_idx}. **版式建议**: {top_aspect[0]}素材占比最高 ({top_aspect[1]}/{total})，优先制作该版式以匹配主流投放渠道。")
        suggestion_idx += 1

    # Color suggestion
    if color_counter:
        top_colors = [tag for tag, _ in color_counter.most_common(3)]
        lines.append(f"{suggestion_idx}. **配色参考**: 本周热门素材偏好 {' / '.join(top_colors)} 色调，可作为新素材配色的参考基准。")
        suggestion_idx += 1

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*本报告由 guangdada-scraper 自动生成，基于广大大每周热门创意榜数据。*")
    lines.append("")

    return "\n".join(lines)


def save_report(report: ReportData, image_dir: Path) -> Path:
    md = generate_markdown_report(report, image_dir)
    out = image_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    logger.info("Report saved to %s", out)
    return out
