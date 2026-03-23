---
name: guangdada-scraper
description: 爬取广大大 (guangdada.net) 本周买量素材 TOP20，保存图片到本地，分析并生成 Markdown 报告。支持飞书推送。
version: 1.0.0
tags: [guangdada, scraper, ad-creative, socialpeta]
---

# 广大大买量素材爬虫

爬取广大大 (guangdada.net) 本周买量素材 TOP20，批量下载图片到本地，分析素材趋势并生成 Markdown 报告。

## 功能概述

| 模块 | 说明 |
|------|------|
| **凭据管理** (credential_store) | Fernet 加密存储广大大账号密码，密钥与密文分离 |
| **页面抓取** (scraper) | Playwright 自动登录广大大，导航到买量排行榜，提取 TOP20 素材数据 |
| **图片下载** (image_downloader) | 批量下载素材图片，自动去重，断点续传 |
| **素材分析** (analyzer) | Pillow 基础分析 + LLM Vision 预留接口，生成 Markdown 报告 |
| **飞书推送** (feishu_publisher) | 消息通知 + 飞书文档发布预留接口 |

## 架构

```text
config.yaml + ~/.openclaw/guangdada.credentials.enc
    ↓
┌─────────────────────────────────────────┐
│          Guangdada Scraper              │
│                                         │
│  ┌───────────────┐  ┌────────────────┐  │
│  │CredentialStore│  │   Scraper      │  │
│  └───────────────┘  └────────────────┘  │
│  ┌───────────────┐  ┌────────────────┐  │
│  │ImageDownloader│  │   Analyzer     │  │
│  └───────────────┘  └────────────────┘  │
│  ┌───────────────┐                      │
│  │FeishuPublisher│                      │
│  └───────────────┘                      │
└─────────────────────────────────────────┘
    ↓               ↓              ↓
  images/      metadata.json    report.md
```

## 安装步骤

### 1. 进入项目目录

```bash
cd skills/guangdada-scraper
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装浏览器引擎

```bash
playwright install chromium
```

### 4. 存储登录凭据

```bash
python -m src.cli login --username your_email --password your_password
```

### 5. 验证安装

```bash
python -m src.cli doctor
```

## 配置说明

配置文件为 `config.yaml`，位于 skill 根目录。所有配置项支持通过 `GDD_` 前缀的环境变量覆盖。

| 环境变量 | 对应配置 | 说明 |
|----------|---------|------|
| `GDD_CREDENTIAL_DIR` | — | 凭据存储目录（默认 `~/.openclaw/`）|
| `GDD_HEADLESS` | `scraper.headless` | 无头模式开关 |
| `GDD_TIMEOUT_MS` | `scraper.timeout_ms` | 页面超时（毫秒）|
| `GDD_OUTPUT_DIR` | `output.base_dir` | 输出目录 |
| `GDD_LLM_ENABLED` | `analysis.llm_enabled` | AI 分析开关 |
| `GDD_LLM_MODEL` | `analysis.llm_model` | LLM 模型名 |
| `GDD_FEISHU_ENABLED` | `feishu.enabled` | 飞书开关 |
| `GDD_FEISHU_MODE` | `feishu.mode` | 飞书模式 (notify/doc/both) |

配置加载优先级：
1. CLI 参数
2. 环境变量 `GDD_*`
3. 当前目录 `config.yaml`
4. `~/.config/guangdada-scraper/config.yaml`

## 使用示例

### CLI 命令

```bash
# 凭据管理
python -m src.cli login --username xxx --password yyy
python -m src.cli logout
python -m src.cli check-auth

# 爬取 + 下载 + 分析（一键完成）
python -m src.cli scrape
python -m src.cli scrape --top 10
python -m src.cli scrape --period weekly
python -m src.cli scrape --no-analyze

# 单独分析已下载图片
python -m src.cli analyze --dir output/guangdada/2026-03-23_weekly_top20/

# 飞书推送
python -m src.cli publish --report output/guangdada/.../report.md

# 诊断
python -m src.cli doctor
```

## 目录结构

```text
skills/guangdada-scraper/
├── SKILL.md                     # 本文件
├── requirements.txt             # Python 依赖
├── config.yaml.template         # 配置模板
├── src/
│   ├── __init__.py
│   ├── __main__.py              # python -m src 入口
│   ├── cli.py                   # CLI 命令行入口
│   ├── config.py                # 配置加载器
│   ├── credential_store.py      # Fernet 加密凭据管理
│   ├── scraper.py               # Playwright 浏览器自动化
│   ├── image_downloader.py      # 图片下载
│   ├── analyzer.py              # 分析 + 报告生成
│   └── feishu_publisher.py      # 飞书接口
├── test/
│   ├── test_credential_store.py
│   ├── test_analyzer.py
│   └── test_config.py
└── examples/
    └── config.yaml.example
```

运行时产生的目录：
```text
output/guangdada/          # 爬取结果（图片 + 报告）
~/.openclaw/               # 加密凭据 + 浏览器状态
```

## 安全说明

- 登录凭据使用 Fernet (AES-128-CBC + HMAC-SHA256) 加密存储
- 密钥文件 (`guangdada.key`) 与加密凭据 (`guangdada.credentials.enc`) 分离
- 密钥文件权限设为 600（仅当前用户可读）
- Cookie 状态文件存储在 `~/.openclaw/guangdada_state/`，不进入版本控制
- 所有敏感信息仅在运行时解密到内存

## 故障排查

### 1. Playwright 未安装浏览器

```
错误: Browser not found
```

**解决**: 运行 `playwright install chromium`

### 2. 登录失败

```
错误: Login failed — possible captcha
```

**解决**: 使用 `--no-headless` 参数以有头模式运行，手动完成验证码

### 3. 页面结构变化

```
错误: Selector not found
```

**解决**: 广大大可能更新了页面结构，需要更新 `scraper.py` 中的选择器配置

## 技术说明

- Python 3.9+（推荐 3.10+）
- Playwright Chromium 浏览器引擎
- 遵循 PEP8 代码风格
- 日志通过标准 `logging` 模块输出
