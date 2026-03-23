"""Download creative images to local storage.

Each scrape run produces a timestamped directory under the configured
``output.base_dir``, e.g.::

    output/guangdada/2026-03-23_weekly_top20/
        01_素材标题.jpg
        02_素材标题.png
        ...
        metadata.json
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import dataclasses
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from src.config import OutputConfig
from src.scraper import CreativeItem

logger = logging.getLogger(__name__)

_TIMEOUT = 30


def _sanitize_filename(name: str, max_len: int = 40) -> str:
    """Remove characters that are illegal in file names."""
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name)
    name = name.strip(". ")
    return name[:max_len] if name else "untitled"


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _guess_extension(url: str, content_type: str = "") -> str:
    ct_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    for ct, ext in ct_map.items():
        if ct in content_type:
            return ext
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if path.endswith(ext):
            return ext
    return ".jpg"


class ImageDownloader:
    """Download creative images to a local directory."""

    def __init__(self, config: OutputConfig, run_label: Optional[str] = None) -> None:
        self._cfg = config
        if run_label is None:
            today = time.strftime("%Y-%m-%d")
            run_label = f"{today}_weekly_top20"
        self._out_dir = Path(config.base_dir) / run_label
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )

    @property
    def output_dir(self) -> Path:
        return self._out_dir

    def download_all(self, items: list[CreativeItem]) -> list[Path]:
        """Download images for every *item*; return list of saved paths."""
        self._out_dir.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        seen_hashes: set[str] = set()

        for item in items:
            if not item.image_url:
                logger.warning("  #%d 没有图片 URL，跳过", item.rank)
                continue

            url_h = _url_hash(item.image_url)
            if url_h in seen_hashes:
                logger.debug("  #%d 重复图片，跳过", item.rank)
                continue
            seen_hashes.add(url_h)

            path = self._download_one(item)
            if path:
                saved.append(path)

        self._write_metadata(items)
        logger.info("已下载 %d 张图片至 %s", len(saved), self._out_dir)
        return saved

    def _download_one(self, item: CreativeItem) -> Optional[Path]:
        name = item.advertiser or item.title or "untitled"
        title = _sanitize_filename(name)
        prefix = f"{item.rank:02d}"

        try:
            resp = self._session.get(item.image_url, timeout=_TIMEOUT, stream=True)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("  #%d 下载失败 (%s): %s", item.rank, item.image_url, exc)
            return None

        ext = _guess_extension(item.image_url, resp.headers.get("content-type", ""))
        filename = f"{prefix}_{title}{ext}"
        dest = self._out_dir / filename

        if dest.exists():
            logger.debug("  #%d 文件已存在，跳过: %s", item.rank, dest.name)
            return dest

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("  #%d 已保存: %s (%.1f KB)", item.rank, dest.name, dest.stat().st_size / 1024)
        return dest

    def _write_metadata(self, items: list[CreativeItem]) -> None:
        meta_path = self._out_dir / "metadata.json"
        data = []
        for it in items:
            d = dataclasses.asdict(it)
            d["title"] = it.title
            d["days"] = it.days
            d["channel"] = it.channel
            data.append(d)
        meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Metadata written to %s", meta_path)
