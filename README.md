# guangdada-scraper

广大大 (guangdada.net / SocialPeta) 买量素材 TOP20 爬虫，封装为 [OpenClaw](https://github.com/nicepkg/openclaw) Skill。

自动登录广大大 → 抓取本周买量素材排行榜 → 下载图片到本地 → 分析并生成 Markdown 报告。

## 功能特性

- **一键爬取**：`python -m src.cli scrape` 完成登录、抓取、下载、分析全流程
- **凭据加密**：Fernet (AES-128-CBC + HMAC-SHA256) 加密存储账号密码，密钥与密文分离
- **Cookie 复用**：首次登录后保存浏览器状态，后续免重复登录
- **图片分析**：自动统计尺寸、版式、主色调，生成结构化 Markdown 报告
- **LLM Vision 预留**：可接入 OpenClaw 模型通道，用 AI 分析素材内容与趋势
- **飞书集成**：消息通知立即可用，飞书文档发布接口已预留（等待 openclaw-lark 插件）
- **反爬策略**：随机延时、UA 伪装、模拟滚动、验证码 headful 降级

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/zhangzeyu99-web/guangdada-scraper.git
cd guangdada-scraper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 存储登录凭据

```bash
python -m src.cli login --username your_email@example.com --password your_password
```

凭据会被加密存储到 `~/.openclaw/` 目录，不会以明文形式保存在任何地方。

### 4. 运行爬虫

```bash
python -m src.cli scrape
```

完成后会输出：
- 图片目录：`output/guangdada/YYYY-MM-DD_weekly_top20/`
- 分析报告：`output/guangdada/YYYY-MM-DD_weekly_top20/report.md`

### 5. 环境诊断

```bash
python -m src.cli doctor
```

## 作为 OpenClaw Skill 安装

如果你正在使用 [OpenClaw](https://github.com/nicepkg/openclaw)，可以将此仓库作为 Skill 安装：

### 方式一：直接复制到 skills 目录

```bash
# 进入你的 OpenClaw 项目
cd your-openclaw-project

# 克隆到 skills 目录
git clone https://github.com/zhangzeyu99-web/guangdada-scraper.git skills/guangdada-scraper

# 安装依赖
cd skills/guangdada-scraper
pip install -r requirements.txt
playwright install chromium
```

### 方式二：复制 Cursor IDE 技能文件（可选）

将 `cursor-skill/SKILL.md` 复制到 `.cursor/skills/guangdada-scraper/SKILL.md`，即可通过自然语言触发爬虫（如对 AI 说"帮我看看这周广大大买量素材排行"）。

## CLI 命令参考

### 凭据管理

```bash
python -m src.cli login --username xxx --password yyy   # 加密存储凭据
python -m src.cli logout                                 # 清除凭据
python -m src.cli check-auth                             # 验证凭据有效性
```

### 爬取

```bash
python -m src.cli scrape                      # 爬取本周 TOP20（默认）
python -m src.cli scrape --top 10             # 只取 TOP10
python -m src.cli scrape --period daily       # 每日排行
python -m src.cli scrape --period monthly     # 月度排行
python -m src.cli scrape --no-analyze         # 只下载不分析
python -m src.cli scrape --no-headless        # 有头模式（调试/验证码）
```

### 分析

```bash
python -m src.cli analyze --dir output/guangdada/2026-03-23_weekly_top20/
```

### 飞书推送

```bash
python -m src.cli publish --report output/guangdada/.../report.md
```

### 诊断

```bash
python -m src.cli doctor
```

## 配置

复制 `config.yaml.template` 为 `config.yaml` 进行自定义：

```yaml
scraper:
  headless: true          # false = 显示浏览器窗口
  timeout_ms: 30000       # 页面加载超时
  cookie_reuse: true      # 复用已保存的登录状态

output:
  base_dir: "output/guangdada"
  image_format: "original"  # original / jpg / png

analysis:
  basic_enabled: true     # Pillow 基础分析
  llm_enabled: false      # LLM Vision 分析（需配置模型）
  llm_model: ""           # OpenClaw 模型通道名

feishu:
  enabled: false
  mode: "notify"          # notify / doc / both
```

所有配置项均可通过 `GDD_` 前缀的环境变量覆盖：

| 环境变量 | 说明 |
|---------|------|
| `GDD_CREDENTIAL_DIR` | 凭据存储目录（默认 `~/.openclaw/`）|
| `GDD_HEADLESS` | 无头模式：`true` / `false` |
| `GDD_OUTPUT_DIR` | 输出目录 |
| `GDD_LLM_ENABLED` | AI 分析：`true` / `false` |
| `GDD_FEISHU_ENABLED` | 飞书推送：`true` / `false` |

## 项目结构

```
guangdada-scraper/
├── README.md                    # 本文件
├── SKILL.md                     # OpenClaw Skill 文档
├── requirements.txt             # Python 依赖
├── config.yaml.template         # 配置模板
├── cursor-skill/
│   └── SKILL.md                 # Cursor IDE 自然语言技能映射
├── src/
│   ├── __init__.py
│   ├── __main__.py              # python -m src 入口
│   ├── cli.py                   # CLI 命令行
│   ├── config.py                # 配置加载器
│   ├── credential_store.py      # Fernet 加密凭据管理
│   ├── scraper.py               # Playwright 浏览器自动化
│   ├── image_downloader.py      # 图片下载
│   ├── analyzer.py              # 图片分析 + 报告生成
│   └── feishu_publisher.py      # 飞书接口
├── test/
│   ├── test_credential_store.py
│   ├── test_config.py
│   └── test_analyzer.py
└── examples/
    └── config.yaml.example
```

## 架构

```
┌─────────────────────────────────────────────┐
│                    CLI                       │
│  login | scrape | analyze | publish | doctor │
└──────────────────┬──────────────────────────┘
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Credential│ │ Scraper  │ │   Analyzer   │
│  Store   │ │(Playwright)│ │(Pillow+LLM) │
└──────────┘ └────┬─────┘ └──────┬───────┘
                  │              │
                  ▼              ▼
           ┌──────────┐  ┌──────────────┐
           │  Image   │  │   Markdown   │
           │Downloader│  │    Report    │
           └──────────┘  └──────┬───────┘
                                │
                                ▼
                        ┌──────────────┐
                        │    Feishu    │
                        │  Publisher   │
                        └──────────────┘
```

## 安全说明

- 登录凭据使用 **Fernet 对称加密**（AES-128-CBC + HMAC-SHA256）
- 密钥文件 (`guangdada.key`) 与加密凭据 (`guangdada.credentials.enc`) **分离存储**
- 密钥文件权限设为 600（仅当前用户可读，Linux/macOS）
- 浏览器 Cookie 状态存储在 `~/.openclaw/guangdada_state/`
- **所有敏感信息仅在运行时解密到内存，不会写入日志或版本控制**

## 运行测试

```bash
pip install pytest
python -m pytest test/ -v
```

## 依赖

| 包 | 用途 |
|---|------|
| playwright | 浏览器自动化（登录 + 抓取）|
| cryptography | Fernet 加密凭据存储 |
| Pillow | 图片分析（尺寸、色彩）|
| PyYAML | 配置文件解析 |
| requests | 图片下载 |

Python 3.9+（推荐 3.10+）

## 常见问题

**Q: 报 "Browser not found"**
A: 运行 `playwright install chromium`

**Q: 登录时出现验证码**
A: 使用 `python -m src.cli scrape --no-headless` 以有头模式运行，手动完成验证

**Q: 页面结构变化导致抓取失败**
A: 更新 `src/scraper.py` 中 `SELECTORS` 字典里的 CSS 选择器

**Q: 飞书文档发布报 NotImplementedError**
A: 这是预留接口，等待 openclaw-lark 插件集成。当前可使用 `send_notification` 发送文字摘要

## License

MIT
