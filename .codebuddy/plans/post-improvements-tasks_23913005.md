---
name: post-improvements-tasks
overview: 处理上一轮遗留的三项改进：(1) 安装并运行 pytest 验证现有测试；(2) 加固邮件发送 TLS（starttls 加证书校验 + 明文告警）；(3) 统一 Tor 端口文档为 9150 并澄清 9050 含义。
todos:
  - id: install-and-run-pytest
    content: 安装 pytest 并运行 tests/，定位修复失败项
    status: completed
  - id: harden-email-tls
    content: 加固 notifier.py：starttls 加证书校验并加 use_tls=False 告警
    status: completed
  - id: fix-tor-port-docs
    content: 统一软件说明书 Tor 端口为 9150 并补 9050 说明
    status: completed
---

## 用户需求

处理上一轮总结中"未做的（建议后续）"三项收尾工作，提升项目可验证性与安全性。

## 核心内容

- **安装并运行测试**：当前环境未安装 pytest，需安装后运行 `tests/` 下全部已有测试（conftest.py、test_credibility.py、test_evidence_tracer.py、test_pipeline.py、test_project_split.py、test_refine_query.py、test_security.py），确保无回归；若有失败则定位并修复。
- **邮件 TLS 加固**：`AIBriefingNotifier` 当前 `starttls()` 未携带 SSL 上下文、不校验证书（存在中间人风险）；用户确认仅加固——为两处 `starttls()` 增加 `ssl.create_default_context()` 证书校验，并在 `use_tls=False` 时打印明文发送安全告警（保持可配置，不强制关闭）。
- **Tor 端口文档统一**：代码、`.env.example`、README 实际均已一致为 9150（Tor 浏览器默认 SOCKS 端口），仅 `data/docs/IntelNexus软件说明书.md` 示例中出现 9050（独立 Tor 守护进程端口）。需将说明书改为 9150，并注明 9050 的用途及如何用 `TOR_PROXY_PORT` 覆盖。

## 技术栈

- 语言：Python 3.10+
- 测试：pytest（新增开发依赖，标准库无关）
- 邮件安全：标准库 `smtplib` + `ssl.create_default_context()`
- 文档：Markdown 说明文档（仅文本修改，无逻辑变更）

## 实现方案

- **批 A（测试）**：通过 `pip install pytest` 安装测试运行器，执行 `python -m pytest tests/ -v`。测试为纯逻辑/单元层（可信度评分、证据链、流水线、项目拆分、查询精炼、安全），不依赖网络与外部服务；若个别用例因环境（如未配置 API key）失败，优先小范围修复用例或源码中明显缺陷，并清晰记录。
- **批 B（邮件 TLS）**：在 `intel-briefing/ai_briefing/notifier.py` 顶部确保 `import ssl`；将 `_send_email_once`（约 122 行）与批量发送（约 302 行）两处 `server.starttls()` 改为 `server.starttls(context=ssl.create_default_context())`，启用对服务端证书的校验，抵御中间人。当 `use_tls` 为 `False` 时，在发送前调用现有 `logger.warning(...)`，提示凭证将明文传输，保持可配置不阻断。
- **批 C（Tor 文档）**：将软件说明书中 `TOR_PROXY=http://127.0.0.1:9050` 改为 `9150`，并在端口说明处补充注释：9150 为 Tor 浏览器默认 SOCKS 端口；若使用独立 Tor 守护进程则为 9050，需用 `TOR_PROXY_PORT` 环境变量覆盖。可选在 `.env.example` 的 `TOR_PROXY_PORT=9150` 后追加同样注释。代码与 README 已一致，无需改动。

## 实现注意

- 复用现有 `logger`（notifier.py 顶部已定义），告警文案保持简洁、无敏感信息；避免日志刷屏。
- `ssl.create_default_context()` 在证书校验失败时会抛 `ssl.SSLError`/`smtplib.SMTPException`，属预期安全行为，不应静默吞掉；现有 `_retry` 机制已能处理异常重试。
- 邮件发送存在两处独立实现（单次与批量），必须同步修改，避免遗漏导致行为不一致。
- pytest 安装属于环境依赖变更，建议仅追加到开发环境（可新建 `requirements-dev.txt` 或在 `requirements.txt` 末尾追加 `pytest`），不污染运行时依赖语义。

## 架构与目录结构

本次为增量安全加固与文档修正，不引入新架构或新模块；仅修改以下文件：

```
IntelNexus/
├── requirements.txt            # [MODIFY] 末尾追加 pytest（或新建 requirements-dev.txt 写入 pytest）
├── intel-briefing/
│   └── ai_briefing/
│       └── notifier.py         # [MODIFY] 两处 starttls() 加 ssl context；use_tls=False 时 logger.warning 明文告警
├── .env.example                # [MODIFY] TOR_PROXY_PORT=9150 后补充 9150/9050 注释说明（可选）
└── data/docs/
    └── IntelNexus软件说明书.md  # [MODIFY] 9050 → 9150，并注明 9050 为独立 Tor 守护进程端口及 TOR_PROXY_PORT 覆盖方式
```

## 验收

- `python -m pytest tests/ -v` 全部通过，或失败项已定位并修复且有记录。
- `notifier.py` 发送路径使用 `starttls(context=ssl.create_default_context())`；`use_tls=False` 时日志出现明文告警。
- 软件说明书 Tor 端口与代码/配置一致为 9150，并明确 9050 用途。