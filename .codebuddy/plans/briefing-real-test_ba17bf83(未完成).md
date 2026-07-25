---
name: briefing-real-test
overview: 配置订阅者与 163 邮箱 SMTP，使用本地 Ollama 的 qwen3:8b 模型生成并真实发送一份 AI 情报简报到 m13237097902@163.com。
todos:
  - id: add-subscriber
    content: 使用 [mcp:filesystem] 编辑 data/subscriptions.json，增加 163 邮箱订阅者"墨"（启用 email 渠道与定时）
    status: completed
  - id: add-smtp-config
    content: 使用 [mcp:filesystem] 编辑 .env，追加 163 SMTP 配置（授权码、端口 25、启用 TLS）
    status: completed
  - id: run-briefing-test
    content: 在终端运行 python main.py briefing -m qwen3:8b，验证 Sent 1/1 且邮箱与 data/briefings 存档收到简报
    status: in_progress
    dependencies:
      - add-subscriber
      - add-smtp-config
---

## 用户需求

用户希望实际测试 IntelNexus 的「AI 简报」功能，并收到一份真实简报邮件，用于验证整条生成+推送链路是否跑通。

## 核心要点

- 收件邮箱：`m13237097902@163.com`
- 本地已启动 `ollama serve`，可用模型为 `qwen3:8b`（本机**没有**默认所需的 `qwen2.5:7b`，因此必须用 `qwen3:8b`）
- 已提供 163 邮箱 SMTP 授权码（用于登录 SMTP，非邮箱登录密码）
- 用户倾向 CLI 一键跑通 + 收邮件验证，自述"不太懂"，需把配置直接配好

## 预期效果

执行 `python main.py briefing -m qwen3:8b` 后，终端依次输出 `[1/4] Collecting → [2/4] Generating → [3/4] Sending → [4/4] Complete`，显示 `Sent 1/1 briefings`；同时简报以 Markdown/HTML/PDF 形式存档于 `data/briefings/`，并成功发送至用户 163 邮箱。

## 技术栈

- 运行时：Python 3.10+（conda base 环境，依赖已就绪）
- LLM：本地 Ollama，模型 `qwen3:8b`
- 推送：SMTP（STARTTLS 模式），163 邮箱 `smtp.163.com`
- 入口命令：`main.py` 的 `briefing` 子命令

## 实现方案

整体策略：**只改配置、不碰业务代码**，完全复用现有 `briefing` 命令与推送链。

1. 写入订阅者 `data/subscriptions.json`：满足 `get_active_subscribers()` 的筛选条件（`schedule.enabled=true`）与邮件渠道（`channels.email.enabled=true`）。
2. 写入 SMTP 配置 `.env`：`briefing` 命令从环境变量构造 `email_config`（SMTP_SERVER / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD / SMTP_USE_TLS）。
3. 运行 `python main.py briefing -m qwen3:8b`：因本机无默认 `qwen2.5:7b`，需显式用 `-m` 指定 `qwen3:8b`。

## 关键决策

- **模型用 `qwen3:8b`**：`ollama list` 仅有 `llava:7b`、`qwen3:8b`，命令默认值 `qwen2.5:7b` 在本机不存在，必须 `-m qwen3:8b`，否则 `get_llm` 报错退出。
- **SMTP_PORT=25 + STARTTLS**：`notifier.py` 使用 `smtplib.SMTP(...).starttls()`，仅兼容 STARTTLS 端口；163 的 465/994 为隐式 SSL，与当前代码不兼容，故使用 25（若 25 被运营商封锁，后续可改 `notifier.py` 支持 `SMTP_SSL`）。
- **密码用授权码**：163 邮箱 SMTP 登录必须使用授权码（用户提供 `QXjBBsamPbtRWPiV`），而非邮箱登录密码。

## 实现要点

- 订阅者 JSON 字段需与 `subscriptions.py` 的 `add_subscriber` 结构一致：`id / name / email / channels / schedule / categories / created_at / last_sent`。
- 推送判定：仅当 `channels.email.enabled=true` 才走邮件；`get_active_subscribers()` 仅返回 `schedule.enabled=true` 者，两者缺一不可。
- 数据采集依赖联网；`NEWS_API_KEY` 当前为占位符可能导致新闻源拉取失败，但网页源仍可用，不影响整体跑通。
- `.env` 中 `ENABLE_DARKWEB=true` 可能触发需 Tor 的暗网采集；若采集卡住，可临时置 `false`，不影响简报生成与推送。

## 目录结构（仅改动 2 个文件）

```
IntelNexus/
├── data/
│   └── subscriptions.json   # [MODIFY] 增加 163 邮箱测试订阅者（墨），启用 email 渠道与定时
└── .env                     # [MODIFY] 末尾追加 163 SMTP 配置（含授权码，端口 25，启用 TLS）
```

## 关键配置结构

`data/subscriptions.json`（整体替换为）：

```
{
  "subscribers": [
    {
      "id": "sub_test_001",
      "name": "墨",
      "email": "m13237097902@163.com",
      "channels": {
        "email": { "enabled": true, "address": "m13237097902@163.com" },
        "wecom": { "enabled": false },
        "dingtalk": { "enabled": false }
      },
      "schedule": { "enabled": true, "frequency": "daily", "time": "08:00" },
      "categories": ["ai_gov_usage","ai_china_narrative","ai_legislation","ai_data_leak","cyber_vuln","cyber_attack"],
      "created_at": "2026-07-25T19:40:00",
      "last_sent": null
    }
  ]
}
```

`.env` 末尾追加：

```
# 163 邮箱 SMTP 推送
SMTP_SERVER=smtp.163.com
SMTP_PORT=25
SMTP_USERNAME=m13237097902@163.com
SMTP_PASSWORD=QXjBBsamPbtRWPiV
SMTP_USE_TLS=true
```

## 执行命令（用户在终端运行）

```
cd d:\Improve\Project\Python\IntelNexus
# 确保在已装依赖的 conda base 环境（或用 run.bat 对应的环境）
python main.py briefing -m qwen3:8b
```

## Agent Extensions

### MCP

- **filesystem**
- Purpose: 编辑 `data/subscriptions.json` 与 `.env` 两个配置文件
- Expected outcome: 订阅者与 163 SMTP 配置被正确写入，使 `briefing` 命令能找到活跃订阅者并成功发送邮件