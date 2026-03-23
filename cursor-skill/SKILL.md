---
name: guangdada-scraper
description: "爬取广大大买量素材排行榜。当用户提到 广大大/买量素材/素材排行/guangdada/创意排行/投放素材 等关键词时激活。"
version: 1.0.0
tags: [guangdada, scraper, ad-creative, 买量素材]
---

# 广大大买量素材爬虫 — 自然语言指令

当用户用自然语言描述以下意图时，自动翻译为 CLI 命令执行。

## 前置条件

- Python 3.9+ 已安装
- 依赖已安装 (`pip install -r skills/guangdada-scraper/requirements.txt`)
- Playwright 浏览器已安装 (`playwright install chromium`)
- 广大大登录凭据已存储 (`python -m src.cli login`)

## 命令映射

工作目录: `D:\project\openclaw\skills\guangdada-scraper`

| 用户意图 | 命令 |
|---------|------|
| "看看这周买量素材排行" / "广大大TOP20" / "本周素材榜" | `python -m src.cli scrape` |
| "抓取广大大TOP10" / "只要前10" | `python -m src.cli scrape --top 10` |
| "看看今天的买量素材" / "每日素材排行" | `python -m src.cli scrape --period daily` |
| "月度买量素材排行" | `python -m src.cli scrape --period monthly` |
| "只下载图片不要分析" | `python -m src.cli scrape --no-analyze` |
| "有验证码，用有头浏览器" / "调试模式" | `python -m src.cli scrape --no-headless` |
| "重新分析之前下载的素材" / "分析这个目录" | `python -m src.cli analyze --dir <目录路径>` |
| "把报告发到飞书" / "推送报告" | `python -m src.cli publish --report <报告路径>` |
| "存储广大大账号" / "登录广大大" | `python -m src.cli login --username xxx --password yyy` |
| "清除广大大登录信息" / "登出" | `python -m src.cli logout` |
| "检查广大大凭据" / "认证还有效吗" | `python -m src.cli check-auth` |
| "检查爬虫环境" / "诊断" | `python -m src.cli doctor` |

## 执行规则

1. **工作目录**: 所有命令在 `skills/guangdada-scraper/` 目录下执行
2. **默认值**: 未指定 top 时默认 20，未指定 period 时默认 weekly
3. **中文输出**: 命令完成后用中文总结结果，告知图片保存位置和报告链接
4. **错误引导**: 如未登录则提示先执行 login；如 Playwright 未安装则引导安装
5. **安全提醒**: login 命令执行后提醒用户凭据已加密存储，密钥位于 ~/.openclaw/
6. **报告链接**: scrape 完成后主动输出报告文件的完整路径

## 典型工作流

用户说: "帮我看看这周广大大买量素材TOP20"

→ 执行步骤:
1. `cd skills/guangdada-scraper`
2. `python -m src.cli scrape --top 20 --period weekly`
3. 等待完成，告知用户图片和报告位置

用户说: "把刚才的报告发到飞书"

→ 找到最新的 report.md 路径，执行:
1. `python -m src.cli publish --report output/guangdada/<最新目录>/report.md`
