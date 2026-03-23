"""Playwright-based scraper for guangdada.net ad-creative rankings.

Navigates to the weekly hot-charts page inside the SPA at::

    https://guangdada.net/modules/creative/charts/hot-charts

and extracts structured metadata + image URLs for the TOP-N items.
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.config import ScraperConfig

logger = logging.getLogger(__name__)

_BASE_URL = "https://guangdada.net"
_LOGIN_URL = f"{_BASE_URL}/modules/auth/login"

_CHART_URLS = {
    "weekly": f"{_BASE_URL}/modules/creative/charts/hot-charts",
    "daily": f"{_BASE_URL}/modules/creative/charts/hot-charts",
    "surge": f"{_BASE_URL}/modules/creative/charts/surge-charts",
    "new": f"{_BASE_URL}/modules/creative/charts/new-charts",
    "monthly": f"{_BASE_URL}/modules/creative/charts/hot-charts",
}

_STATE_DIR_NAME = "guangdada_state"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

SELECTORS = {
    "login_username": 'input[type="text"][placeholder*="邮箱"], input[type="text"][placeholder*="email"], input[type="email"], input[name="username"]',
    "login_password": 'input[type="password"]',
    "login_submit": 'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
    "login_success_indicator": '[class*="avatar"], [class*="userInfo"]',
}

_STYLE_KEYWORDS = frozenset([
    "现代", "复古", "简约", "写实", "卡通", "插画", "平面设计", "3D",
    "真人", "真人口播", "口播", "情景剧", "玩法特色", "录屏",
    "暗色", "亮色", "多彩", "彩虹色", "中国风", "日系", "欧美",
])


@dataclass
class CreativeItem:
    """A single ad-creative entry from the ranking page."""
    rank: int = 0
    advertiser: str = ""
    publisher: str = ""
    image_url: str = ""
    app_icon_url: str = ""
    popularity: str = ""
    industry_tags: list = field(default_factory=list)
    style_tags: list = field(default_factory=list)
    color_tags: list = field(default_factory=list)
    duration_days: int = 0
    date_start: str = ""
    date_end: str = ""
    detail_url: str = ""

    @property
    def title(self) -> str:
        return self.advertiser or self.popularity

    @property
    def days(self) -> str:
        if self.duration_days:
            return f"{self.duration_days}天 ({self.date_start}~{self.date_end})"
        return ""

    @property
    def channel(self) -> str:
        return ", ".join(self.industry_tags)


def _state_dir() -> Path:
    base = os.environ.get("GDD_CREDENTIAL_DIR")
    if base:
        return Path(base) / _STATE_DIR_NAME
    return Path.home() / ".openclaw" / _STATE_DIR_NAME


def _random_delay(lo: float = 0.5, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


class GuangdadaScraper:
    def __init__(self, config: ScraperConfig, debug_dir: Optional[Path] = None) -> None:
        self._cfg = config
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._debug_dir = debug_dir
        self._debug_step = 0

    def _debug_snapshot(self, label: str) -> None:
        if not self._debug_dir or not self._page:
            return
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        self._debug_step += 1
        prefix = f"{self._debug_step:02d}_{label}"
        try:
            self._page.screenshot(path=str(self._debug_dir / f"{prefix}.png"), full_page=True)
        except Exception:
            pass
        try:
            (self._debug_dir / f"{prefix}.html").write_text(self._page.content(), encoding="utf-8")
        except Exception:
            pass
        logger.info("[debug] %s  url=%s", prefix, self._page.url)

    # -- Lifecycle --

    def start(self) -> None:
        self._pw = sync_playwright().start()
        ua = self._cfg.user_agent or random.choice(_USER_AGENTS)
        state_path = _state_dir()

        self._browser = self._pw.chromium.launch(headless=self._cfg.headless)
        ctx_kwargs: dict = {
            "user_agent": ua,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
        }
        if self._cfg.cookie_reuse and (state_path / "state.json").is_file():
            ctx_kwargs["storage_state"] = str(state_path / "state.json")
            logger.info("Reusing saved browser state")

        self._context = self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(self._cfg.timeout_ms)
        self._page = self._context.new_page()

    def stop(self) -> None:
        for obj in (self._context, self._browser, self._pw):
            try:
                if obj:
                    obj.close() if hasattr(obj, "close") else obj.stop()
            except Exception:
                pass
        self._page = self._context = self._browser = self._pw = None

    def _save_state(self) -> None:
        if not self._context:
            return
        p = _state_dir()
        p.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(p / "state.json"))

    # -- Login --

    def login(self, username: str, password: str) -> bool:
        assert self._page is not None
        page = self._page

        page.goto(_LOGIN_URL, wait_until="networkidle")
        _random_delay(1, 2)
        self._debug_snapshot("login_page")

        if "login" not in page.url.lower() and "auth" not in page.url.lower():
            logger.info("Already logged in")
            return True
        try:
            page.locator(SELECTORS["login_success_indicator"]).first.is_visible(timeout=2000)
            logger.info("Already logged in (avatar visible)")
            return True
        except Exception:
            pass

        logger.info("Filling login form...")
        page.locator(SELECTORS["login_username"]).first.fill(username)
        _random_delay(0.3, 0.8)
        page.locator(SELECTORS["login_password"]).first.fill(password)
        _random_delay(0.3, 0.6)
        page.locator(SELECTORS["login_submit"]).first.click()

        try:
            page.wait_for_url("**/modules/**", timeout=15000)
        except Exception:
            self._debug_snapshot("login_timeout")
            if not self._cfg.headless:
                logger.info("Waiting for manual captcha (60s)...")
                try:
                    page.wait_for_url("**/modules/**", timeout=60000)
                except Exception:
                    return False
            else:
                logger.error("Login failed (headless). Use --no-headless for captcha.")
                return False

        logger.info("Login success!")
        self._debug_snapshot("login_success")
        self._save_state()
        return True

    # -- Scrape --

    def scrape_top_creatives(self, top_n: int = 20, period: str = "weekly") -> list[CreativeItem]:
        assert self._page is not None
        page = self._page

        chart_url = _CHART_URLS.get(period, _CHART_URLS["weekly"])
        logger.info("Navigating to %s", chart_url)
        page.goto(chart_url, wait_until="networkidle")
        _random_delay(2, 3)
        self._debug_snapshot("chart_page")

        for _ in range(10):
            page.evaluate("window.scrollBy(0, 600)")
            _random_delay(0.3, 0.8)
        self._debug_snapshot("after_scroll")

        items = self._extract_items_js(page, top_n)
        self._save_state()
        logger.info("Extracted %d items", len(items))
        return items

    def _extract_items_js(self, page: Page, top_n: int) -> list[CreativeItem]:
        try:
            raw = page.evaluate(_JS_EXTRACT, top_n)
        except Exception as e:
            logger.warning("JS extraction error: %s", e)
            return []

        items: list[CreativeItem] = []
        for r in raw:
            src = r.get("creativeSrc", "")
            if src.startswith("//"):
                src = "https:" + src

            # Classify tags
            industry = []
            style = []
            colors = []
            for tag in r.get("allTags", []):
                if any(c in tag for c in "色") and len(tag) <= 4:
                    colors.append(tag)
                elif tag in _STYLE_KEYWORDS or any(kw in tag for kw in ["设计", "口播", "真人", "情景", "录屏", "插画", "卡通", "3D"]):
                    style.append(tag)
                else:
                    industry.append(tag)

            items.append(CreativeItem(
                rank=r.get("rank", 0),
                advertiser=r.get("advertiser", ""),
                publisher=r.get("publisher", ""),
                image_url=src,
                app_icon_url=r.get("appIconSrc", ""),
                popularity=r.get("popularity", ""),
                industry_tags=industry,
                style_tags=style,
                color_tags=colors,
                duration_days=r.get("durationDays", 0),
                date_start=r.get("dateStart", ""),
                date_end=r.get("dateEnd", ""),
            ))
        return items


# JS executed inside the browser to extract structured card data
_JS_EXTRACT = """(topN) => {
    const cards = document.querySelectorAll('div.rounded-lg.border');
    const results = [];
    const skip = new Set(['落地页','收藏','仅看该广告主','周人气值总量','创意AI标签','投放时间','天','~']);
    let rank = 0;

    for (const card of cards) {
        if (rank >= topN) break;
        const imgs = card.querySelectorAll('img');
        if (imgs.length === 0) continue;
        rank++;

        // Separate creative image vs app icon
        let creativeSrc = '', appIconSrc = '';
        for (const img of imgs) {
            const s = img.src || '';
            if (!s || s.startsWith('data:')) continue;
            if ((s.includes('sp2cdn') || s.includes('sp_opera')) && !creativeSrc) creativeSrc = s;
            else if (s.includes('appcdn')) appIconSrc = s;
            else if (img.classList.contains('object-cover') && !creativeSrc) creativeSrc = s;
        }

        // Leaf text nodes
        const leaves = [];
        card.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0 && el.textContent) {
                leaves.push({
                    t: el.textContent.trim(),
                    cls: el.className || '',
                    pcls: (el.parentElement && el.parentElement.className) || '',
                });
            }
        });

        // Advertiser + publisher: first two non-tag, non-number, non-label texts
        let advertiser = '', publisher = '';
        let ni = 0;
        for (const l of leaves) {
            const t = l.t;
            if (!t || skip.has(t) || t.length > 60) continue;
            if (/^\\d/.test(t) || /^[#\\d万亿]+$/.test(t)) continue;
            if (l.pcls.includes('ant-tag') || l.cls.includes('ant-tag')) continue;
            if (l.cls.includes('font-medium') || l.cls.includes('text-[#999]')) continue;
            if (ni === 0) { advertiser = t; ni++; }
            else if (ni === 1) { publisher = t; break; }
        }

        // Popularity
        let popularity = '';
        for (const l of leaves) {
            if (l.cls.includes('font-medium') && /[\\d万亿]+/.test(l.t)) {
                popularity = l.t; break;
            }
        }

        // All .ant-tag texts
        const allTags = [];
        card.querySelectorAll('.ant-tag').forEach(t => {
            const txt = t.textContent.trim();
            if (txt) allTags.push(txt);
        });

        // Duration + dates
        let durationDays = 0, dateStart = '', dateEnd = '';
        for (let i = 0; i < leaves.length; i++) {
            const t = leaves[i].t;
            if (/^\\d+$/.test(t) && i+1 < leaves.length && leaves[i+1].t === '天') durationDays = parseInt(t);
            if (/^\\d{4}-\\d{2}-\\d{2}$/.test(t)) {
                if (!dateStart) dateStart = t;
                else if (!dateEnd) dateEnd = t;
            }
        }

        results.push({rank, advertiser, publisher, popularity, creativeSrc, appIconSrc, allTags, durationDays, dateStart, dateEnd});
    }
    return results;
}"""
