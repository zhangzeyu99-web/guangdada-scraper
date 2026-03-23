---
name: guangdada-scraper
description: "爬取广大大买量素材排行榜。当用户提到 广大大/买量素材/素材排行/guangdada/创意排行/投放素材 等关键词时激活。"
version: 1.1.0
tags: [guangdada, scraper, ad-creative, 买量素材]
---

# 广大大买量素材爬虫 — AI 自动执行手册

**重要：用户不需要自己输入任何命令。当用户用自然语言表达意图时，你（AI）直接用 Shell 工具执行对应命令，然后用中文汇报结果。**

## Skill 安装位置

OpenClaw 安装路径: `C:\Users\Administrator\.openclaw\workspace\skills\guangdada-scraper`

所有命令的 **working_directory** 必须设为:
```
C:\Users\Administrator\.openclaw\workspace\skills\guangdada-scraper
```

## 默认输出路径

默认: `C:\Users\Administrator\Desktop\guangdada-output`

用户可以说"保存到 XXX"来覆盖。如果用户没有指定路径，一律使用上述桌面默认路径。

## 自然语言 → 执行动作

当用户说以下类型的话时，**立即执行**对应命令，不要让用户自己操作:

### 爬取素材

| 用户说的话（举例） | 你执行的命令 |
|---|---|
| "帮我看看这周买量素材排行" / "广大大TOP20" / "爬取广大大" | `python -m src.cli scrape --output-dir "C:\Users\Administrator\Desktop\guangdada-output"` |
| "抓广大大TOP10" / "只要前10个" | `python -m src.cli scrape --top 10 --output-dir "C:\Users\Administrator\Desktop\guangdada-output"` |
| "看看每日素材排行" | `python -m src.cli scrape --period daily --output-dir "C:\Users\Administrator\Desktop\guangdada-output"` |
| "月度排行" | `python -m src.cli scrape --period monthly --output-dir "C:\Users\Administrator\Desktop\guangdada-output"` |
| "保存到 D:\xxx" / "输出到 D:\project\xxx" | `python -m src.cli scrape --output-dir "用户指定的路径"` |
| "有验证码" / "登录不上" | `python -m src.cli scrape --no-headless --output-dir "..."` |

### 凭据管理

| 用户说的话 | 你执行的命令 |
|---|---|
| "存储/设置广大大账号" / "登录广大大" | 先问用户要账号密码，然后执行 `python -m src.cli login --username "邮箱" --password "密码"` |
| "清除广大大账号" / "删除登录信息" | `python -m src.cli logout` |
| "账号还能用吗" / "检查凭据" | `python -m src.cli check-auth` |

### 分析与推送

| 用户说的话 | 你执行的命令 |
|---|---|
| "重新分析之前的素材" | `python -m src.cli analyze --dir "上次输出的目录路径"` |
| "把报告发到飞书" | `python -m src.cli publish --report "report.md的完整路径"` |
| "检查环境" / "诊断一下" | `python -m src.cli doctor` |

## 执行流程规范

### 每次爬取时，你必须这样做:

1. **判断用户意图**: 从自然语言中提取 top_n、period、output_dir
2. **拼接命令**: 自动加上 `--output-dir`，用户没指定就用桌面默认路径
3. **用 Shell 工具执行**: 设置 working_directory 为 skill 安装路径，block_until_ms 设为 120000（爬虫耗时较长）
4. **汇报结果**: 用中文告诉用户：
   - 抓到了几个素材
   - 图片保存在哪里
   - 报告文件的完整路径（可以直接点击打开）
5. **如果报错**: 用中文解释原因并给出修复建议

### 首次使用检查清单:

如果用户第一次使用，先执行 `python -m src.cli doctor` 检查环境:
- 如果 Playwright 未安装 → 帮用户执行 `pip install -r requirements.txt` 和 `playwright install chromium`
- 如果凭据未存储 → 询问用户广大大的账号密码，然后执行 login
- 如果网络不通 → 提醒检查网络或代理

### 输出路径规则:

- 用户说"保存到桌面" → `C:\Users\Administrator\Desktop\guangdada-output`
- 用户说"保存到 D:\xxx" → 直接用该路径
- 用户没提路径 → 默认桌面
- 输出子目录自动按日期命名，如 `2026-03-23_weekly_top20/`
