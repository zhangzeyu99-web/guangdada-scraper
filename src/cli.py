"""CLI entry-point for guangdada-scraper.

Usage::

    python -m src.cli <command> [options]

Commands:
    login       Store encrypted credentials
    logout      Remove stored credentials
    check-auth  Verify stored credentials can be decrypted
    scrape      Scrape + download + analyse (one-shot)
    analyze     Re-analyse a previously downloaded directory
    publish     Send report to Feishu
    doctor      Verify environment (Playwright, credentials, network)
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

from src.config import load_config
from src.credential_store import CredentialStore

logger = logging.getLogger("guangdada")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ======================================================================
# Sub-commands
# ======================================================================

def cmd_login(args: argparse.Namespace) -> int:
    store = CredentialStore()
    if not args.username or not args.password:
        print("错误: 请提供 --username 和 --password")
        return 1
    store.save(args.username, args.password)
    print(f"凭据已加密保存 (用户: {args.username})")
    return 0


def cmd_logout(_args: argparse.Namespace) -> int:
    store = CredentialStore()
    if not store.exists():
        print("没有已保存的凭据。")
        return 0
    store.delete()
    print("凭据已清除。")
    return 0


def cmd_check_auth(_args: argparse.Namespace) -> int:
    store = CredentialStore()
    if not store.exists():
        print("未找到凭据文件。请先执行 login。")
        return 1
    try:
        username, _pw = store.load()
        print(f"凭据有效 (用户: {username})")
        return 0
    except Exception as exc:
        print(f"凭据校验失败: {exc}")
        return 1


def cmd_scrape(args: argparse.Namespace) -> int:
    from src.analyzer import CreativeAnalyzer, save_report
    from src.image_downloader import ImageDownloader
    from src.scraper import GuangdadaScraper

    cfg = load_config(args.config)

    if args.no_headless:
        cfg.scraper.headless = False

    store = CredentialStore()
    if not store.exists():
        print("错误: 未找到凭据。请先执行 login 命令。")
        return 1
    username, password = store.load()

    top_n = args.top or 20
    period = args.period or "weekly"
    today = time.strftime("%Y-%m-%d")
    run_label = f"{today}_{period}_top{top_n}"

    scraper = GuangdadaScraper(cfg.scraper)
    try:
        scraper.start()

        if not scraper.login(username, password):
            print("错误: 登录失败。")
            return 1

        items = scraper.scrape_top_creatives(top_n=top_n, period=period)
        if not items:
            print("警告: 未抓取到任何素材。")
            return 1

        print(f"已抓取 {len(items)} 个素材条目。")

        downloader = ImageDownloader(cfg.output, run_label=run_label)
        saved = downloader.download_all(items)
        print(f"已下载 {len(saved)} 张图片至 {downloader.output_dir}")

        if not args.no_analyze:
            analyzer = CreativeAnalyzer(cfg.analysis)
            report = analyzer.analyze(downloader.output_dir)
            report_path = save_report(report, downloader.output_dir)
            print(f"\n报告已生成: {report_path.resolve()}")

            if cfg.feishu.enabled:
                from src.feishu_publisher import FeishuPublisher

                publisher = FeishuPublisher()
                publisher.publish_or_notify(
                    report_path.read_text(encoding="utf-8"),
                    f"广大大{period}买量素材 TOP{top_n}",
                    mode=cfg.feishu.mode,
                )
    finally:
        scraper.stop()

    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from src.analyzer import CreativeAnalyzer, save_report

    cfg = load_config(args.config)
    image_dir = Path(args.dir)
    if not image_dir.is_dir():
        print(f"错误: 目录不存在 — {image_dir}")
        return 1

    analyzer = CreativeAnalyzer(cfg.analysis)
    report = analyzer.analyze(image_dir)
    report_path = save_report(report, image_dir)
    print(f"报告已生成: {report_path.resolve()}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from src.feishu_publisher import FeishuPublisher

    cfg = load_config(args.config)
    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"错误: 报告文件不存在 — {report_path}")
        return 1

    content = report_path.read_text(encoding="utf-8")
    publisher = FeishuPublisher()
    result = publisher.publish_or_notify(
        content,
        f"广大大买量素材报告 — {report_path.stem}",
        mode=cfg.feishu.mode,
    )
    if result:
        print(f"飞书文档链接: {result}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Verify that the environment is properly set up."""
    ok = True
    print("=== 广大大爬虫环境诊断 ===\n")

    # 1. Playwright
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        browser.close()
        pw.stop()
        print("[OK] Playwright Chromium 可用")
    except Exception as exc:
        print(f"[FAIL] Playwright: {exc}")
        print("       修复: pip install playwright && playwright install chromium")
        ok = False

    # 2. Credentials
    store = CredentialStore()
    if store.exists():
        try:
            u, _ = store.load()
            print(f"[OK] 凭据有效 (用户: {u})")
        except Exception as exc:
            print(f"[FAIL] 凭据解密失败: {exc}")
            ok = False
    else:
        print("[WARN] 未保存凭据。使用 login 命令存储。")

    # 3. Network
    import urllib.request
    try:
        req = urllib.request.Request("https://www.guangdada.net", method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[OK] guangdada.net 可达 (HTTP {resp.status})")
    except Exception as exc:
        print(f"[FAIL] 网络: {exc}")
        ok = False

    # 4. Dependencies
    for mod_name, pkg in [("PIL", "Pillow"), ("yaml", "PyYAML"), ("cryptography", "cryptography")]:
        try:
            __import__(mod_name)
            print(f"[OK] {pkg} 已安装")
        except ImportError:
            print(f"[FAIL] {pkg} 未安装 — pip install {pkg}")
            ok = False

    # 5. Config
    cfg = load_config(args.config if hasattr(args, "config") else None)
    print(f"[INFO] 输出目录: {cfg.output.base_dir}")
    print(f"[INFO] headless: {cfg.scraper.headless}")

    print(f"\n{'所有检查通过！' if ok else '存在问题，请按提示修复。'}")
    return 0 if ok else 1


# ======================================================================
# Argument parser
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guangdada-scraper",
        description="广大大买量素材爬虫",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    parser.add_argument("--config", default=None, help="配置文件路径")

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # login
    p_login = sub.add_parser("login", help="加密存储登录凭据")
    p_login.add_argument("--username", required=True, help="广大大账号（邮箱）")
    p_login.add_argument("--password", required=True, help="广大大密码")

    # logout
    sub.add_parser("logout", help="清除已存储的凭据")

    # check-auth
    sub.add_parser("check-auth", help="验证凭据有效性")

    # scrape
    p_scrape = sub.add_parser("scrape", help="爬取 + 下载 + 分析")
    p_scrape.add_argument("--top", type=int, default=20, help="抓取前 N 条 (默认 20)")
    p_scrape.add_argument("--period", default="weekly", choices=["weekly", "daily", "monthly"], help="时间周期")
    p_scrape.add_argument("--no-analyze", action="store_true", help="只下载不分析")
    p_scrape.add_argument("--no-headless", action="store_true", help="使用有头浏览器（用于调试/验证码）")

    # analyze
    p_analyze = sub.add_parser("analyze", help="对已下载的图片目录重新分析")
    p_analyze.add_argument("--dir", required=True, help="图片目录路径")

    # publish
    p_publish = sub.add_parser("publish", help="将报告推送到飞书")
    p_publish.add_argument("--report", required=True, help="报告 Markdown 文件路径")

    # doctor
    sub.add_parser("doctor", help="环境诊断")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "login": cmd_login,
        "logout": cmd_logout,
        "check-auth": cmd_check_auth,
        "scrape": cmd_scrape,
        "analyze": cmd_analyze,
        "publish": cmd_publish,
        "doctor": cmd_doctor,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))
