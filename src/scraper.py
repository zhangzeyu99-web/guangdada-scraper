"""Playwright-based scraper for guangdada.net ad-creative rankings.

The scraper automates login, navigates to the weekly top-creatives
page, and extracts metadata + image URLs for the TOP-N items.
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

_BASE_URL = "https://www.guangdada.net"
_LOGIN_URL = f"{_BASE_URL}/user/login"

_STATE_DIR_NAME = "guangdada_state"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# CSS selectors — centralised so page-structure changes are easy to fix.
# These are best-effort defaults; guangdada.net is a SPA and the DOM
# may change across releases.
SELECTORS = {
    "login_username": 'input[type="text"][placeholder*="邮箱"], input[name="username"], input[name="email"], #username, #email',
    "login_password": 'input[type="password"], input[name="password"], #password',
    "login_submit": 'button[type="submit"], button:has-text("登录"), .login-btn',
    "login_success_indicator": '.user-avatar, .user-info, .header-user, [class*="avatar"], [class*="user-name"]',
    "ranking_nav": 'a[href*="rank"], a:has-text("排行"), [class*="rank"]',
    "creative_card": '[class*="creative-card"], [class*="material-item"], [class*="rank-item"], .card-item',
    "creative_image": "img[src]",
    "creative_title": '[class*="title"], [class*="name"], h3, h4',
    "creative_days": '[class*="day"], [class*="duration"]',
    "creative_channel": '[class*="channel"], [class*="platform"], [class*="media"]',
    "period_weekly": 'button:has-text("周"), [class*="week"], a:has-text("本周")',
}


@dataclass
class CreativeItem:
    """A single ad-creative entry from the ranking page."""

    rank: int = 0
    title: str = ""
    image_url: str = ""
    days: str = ""
    channel: str = ""
    detail_url: str = ""
    extra: dict = field(default_factory=dict)


def _state_dir() -> Path:
    base = os.environ.get("GDD_CREDENTIAL_DIR")
    if base:
        return Path(base) / _STATE_DIR_NAME
    return Path.home() / ".openclaw" / _STATE_DIR_NAME


def _random_delay(lo: float = 0.5, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


def _pick_ua(config_ua: str) -> str:
    if config_ua:
        return config_ua
    return random.choice(_USER_AGENTS)


class GuangdadaScraper:
    """High-level façade around Playwright for guangdada.net."""

    def __init__(self, config: ScraperConfig) -> None:
        self._cfg = config
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._pw = sync_playwright().start()
        ua = _pick_ua(self._cfg.user_agent)
        state_path = _state_dir()

        launch_kwargs: dict = {
            "headless": self._cfg.headless,
        }
        self._browser = self._pw.chromium.launch(**launch_kwargs)

        context_kwargs: dict = {
            "user_agent": ua,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
        }
        if self._cfg.cookie_reuse and state_path.exists() and (state_path / "state.json").exists():
            context_kwargs["storage_state"] = str(state_path / "state.json")
            logger.info("复用已保存的浏览器状态")

        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self._cfg.timeout_ms)
        self._page = self._context.new_page()

    def stop(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._page = self._context = self._browser = self._pw = None

    def _save_state(self) -> None:
        if not self._context:
            return
        state_path = _state_dir()
        state_path.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(state_path / "state.json"))
        logger.info("浏览器状态已保存至 %s", state_path)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> bool:
        """Log in to guangdada.net.  Returns ``True`` on success."""
        assert self._page is not None
        page = self._page

        logger.info("导航到登录页 %s", _LOGIN_URL)
        page.goto(_LOGIN_URL, wait_until="networkidle")
        _random_delay(1, 2)

        if self._is_logged_in(page):
            logger.info("已处于登录状态（Cookie 复用成功）")
            return True

        logger.info("填写登录表单…")
        username_input = page.locator(SELECTORS["login_username"]).first
        username_input.click()
        username_input.fill(username)
        _random_delay(0.3, 0.8)

        password_input = page.locator(SELECTORS["login_password"]).first
        password_input.click()
        password_input.fill(password)
        _random_delay(0.3, 0.6)

        page.locator(SELECTORS["login_submit"]).first.click()
        logger.info("提交登录…")

        try:
            page.wait_for_selector(
                SELECTORS["login_success_indicator"],
                timeout=15000,
            )
        except Exception:
            logger.warning("登录后未检测到成功标识——可能需要验证码。")
            if self._cfg.headless:
                logger.error(
                    "当前为 headless 模式，无法处理验证码。"
                    "请使用 --no-headless 重试。"
                )
                return False
            logger.info("等待用户手动完成验证码（60 秒超时）…")
            try:
                page.wait_for_selector(
                    SELECTORS["login_success_indicator"],
                    timeout=60000,
                )
            except Exception:
                logger.error("登录超时。")
                return False

        logger.info("登录成功！")
        self._save_state()
        return True

    @staticmethod
    def _is_logged_in(page: Page) -> bool:
        try:
            return page.locator(SELECTORS["login_success_indicator"]).first.is_visible(timeout=3000)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Scrape ranking
    # ------------------------------------------------------------------

    def scrape_top_creatives(
        self,
        top_n: int = 20,
        period: str = "weekly",
    ) -> list[CreativeItem]:
        """Navigate to the ranking page and extract TOP-N creative items."""
        assert self._page is not None
        page = self._page
        items: list[CreativeItem] = []

        logger.info("导航到买量素材排行榜…")
        self._navigate_to_ranking(page)
        _random_delay(1, 2)

        if period == "weekly":
            self._select_period_weekly(page)
            _random_delay(1, 2)

        logger.info("等待素材卡片加载…")
        try:
            page.wait_for_selector(SELECTORS["creative_card"], timeout=self._cfg.timeout_ms)
        except Exception:
            logger.warning("未找到素材卡片选择器，尝试回退方案…")
            self._fallback_extract(page, items, top_n)
            return items[:top_n]

        self._scroll_to_load(page, target_count=top_n)

        cards = page.locator(SELECTORS["creative_card"]).all()
        logger.info("找到 %d 个素材卡片", len(cards))

        for idx, card in enumerate(cards[:top_n], start=1):
            item = self._parse_card(card, idx)
            if item.image_url:
                items.append(item)
                logger.debug("  #%d %s", item.rank, item.title or "(无标题)")

        self._save_state()
        logger.info("共提取 %d 个素材", len(items))
        return items

    def _navigate_to_ranking(self, page: Page) -> None:
        ranking_link = page.locator(SELECTORS["ranking_nav"]).first
        try:
            if ranking_link.is_visible(timeout=5000):
                ranking_link.click()
                page.wait_for_load_state("networkidle")
                return
        except Exception:
            pass

        ranking_urls = [
            f"{_BASE_URL}/ad-creatives/ranking",
            f"{_BASE_URL}/rank",
            f"{_BASE_URL}/creative/rank",
            f"{_BASE_URL}/app-ranking",
        ]
        for url in ranking_urls:
            logger.info("尝试直接访问 %s", url)
            page.goto(url, wait_until="networkidle")
            if page.url != _LOGIN_URL and "login" not in page.url:
                return
        logger.warning("无法找到排行榜页面，使用当前页面继续")

    def _select_period_weekly(self, page: Page) -> None:
        try:
            btn = page.locator(SELECTORS["period_weekly"]).first
            if btn.is_visible(timeout=3000):
                btn.click()
                page.wait_for_load_state("networkidle")
                logger.info("已选择「本周」时间范围")
        except Exception:
            logger.warning("未找到周期选择器，使用默认时间范围")

    def _scroll_to_load(self, page: Page, target_count: int) -> None:
        """Incrementally scroll down to trigger lazy-loaded cards."""
        for _ in range(10):
            count = page.locator(SELECTORS["creative_card"]).count()
            if count >= target_count:
                break
            page.evaluate("window.scrollBy(0, 800)")
            _random_delay(0.5, 1.5)

    def _parse_card(self, card, rank: int) -> CreativeItem:
        item = CreativeItem(rank=rank)
        try:
            img = card.locator(SELECTORS["creative_image"]).first
            item.image_url = img.get_attribute("src") or ""
            if item.image_url.startswith("//"):
                item.image_url = "https:" + item.image_url
        except Exception:
            pass
        try:
            item.title = (card.locator(SELECTORS["creative_title"]).first.inner_text() or "").strip()
        except Exception:
            pass
        try:
            item.days = (card.locator(SELECTORS["creative_days"]).first.inner_text() or "").strip()
        except Exception:
            pass
        try:
            item.channel = (card.locator(SELECTORS["creative_channel"]).first.inner_text() or "").strip()
        except Exception:
            pass
        try:
            link = card.locator("a[href]").first
            href = link.get_attribute("href") or ""
            if href and not href.startswith("javascript"):
                item.detail_url = href if href.startswith("http") else _BASE_URL + href
        except Exception:
            pass
        return item

    def _fallback_extract(self, page: Page, items: list[CreativeItem], top_n: int) -> None:
        """Fallback: extract all visible images on the page as creative items."""
        logger.info("使用回退方案：提取页面所有可见图片…")
        images = page.locator("img[src]").all()
        rank = 1
        for img in images:
            if rank > top_n:
                break
            src = img.get_attribute("src") or ""
            if not src or "logo" in src.lower() or "icon" in src.lower() or len(src) < 20:
                continue
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("data:"):
                continue
            item = CreativeItem(rank=rank, image_url=src)
            try:
                item.title = img.get_attribute("alt") or ""
            except Exception:
                pass
            items.append(item)
            rank += 1
