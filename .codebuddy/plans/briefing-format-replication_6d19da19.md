---
name: briefing-format-replication
overview: 将简报输出格式完全复刻为目标 PDF《AI 与网络安全每日情报简报》的结构与品牌化排版（封面+页眉页脚、双主板块各3子板块、CVE 表格、趋势研判、重要链接），并使 PDF / 邮件HTML / 独立HTML / Markdown 四种格式统一为目标风格，品牌落款全部取自配置（不写死彼德）。
todos:
  - id: config-and-categories
    content: 扩展 config.py：organization 增加 producer_unit/contact/footer_qr_text/disclaimer，WATCH_CATEGORIES 增加 cyber_vuln/cyber_attack 类目
    status: completed
  - id: rewrite-prompts
    content: 重写 prompts.py：新增 ai_dynamic/cyber_dynamic/cve_table 提示词并保留 top3/insight/links，更新 get_prompt 映射
    status: completed
    dependencies:
      - config-and-categories
  - id: rewrite-analyzer
    content: 重写 analyzer.generate_briefing 为新 Markdown schema（封面+中文星期+双主板块+⚠CVE表格+💡研判+📎链接+落款），保留降级与 format_news_item
    status: completed
    dependencies:
      - rewrite-prompts
  - id: unify-templates
    content: "统一 templates.py：MARKDOWN/EMAIL/STANDALONE 三模板改新结构+品牌落款，SECTION_MAP 更新，_md_to_html 支持 #### 与 Markdown 表格转 HTML"
    status: completed
    dependencies:
      - rewrite-analyzer
  - id: rewrite-pdf-export
    content: 重写 briefing_export.py：用 [skill:pdf] 实现品牌化 PDF（页眉页脚/封面/CVE 表格/落款块/可选二维码）
    status: completed
    dependencies:
      - unify-templates
  - id: wire-subject-and-tests
    content: 更新 main/scheduler/notifier 邮件主题为新标题，新增 tests/test_briefing_format.py 并运行 pytest 验证全绿
    status: completed
    dependencies:
      - rewrite-pdf-export
---

## 用户需求

用户发来目标样本 `data/AI网安每日情报简报_20260707_V3.0.pdf`，要求「把简报的格式变成这样」。

经澄清确认：

- **范围**：完全复刻目标 PDF 的板块结构 + 品牌化排版样式。
- **品牌**：落款信息（机构名/出品单位/联系人/扫码文案/免责声明）全部来自配置 `BRIEFING_CONFIG.organization`，保持可配置；**严禁硬编码「彼德」「AISOS」「上海彼德数智」等任何品牌字样**。
- **输出**：PDF、邮件 HTML、Markdown、独立 HTML 四种格式章节顺序与品牌落款必须统一一致。

## 核心功能（目标 PDF 结构）

1. 每页 running 页眉：`AI 与网络安全每日情报简报 | {organization}`；页脚：`{organization} · 每日情报简报  第 N 页`
2. 封面/标题块：`🔐 AI 与网络安全每日情报简报` + 中文星期日期（如「2026年7月7日（星期二）」）+ `{organization}` + 出品单位
3. 📌 近日要闻 TOP3：编号 1./2./3.，每条含描述与 `（来源：X / 日期）`
4. 🤖 AI 领域动态：子板块「模型与技术 / 应用与落地 / 产业与市场」，条目 `• [标签] 描述（来源：X / 日期）`
5. 🛡 网络安全动态：子板块「漏洞与威胁 / 攻击事件 / 政策与合规」
6. ⚠ 近日新增安全漏洞预警：结构化表格 `CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施`
7. 💡 趋势研判与防护建议：编号 1./2./3.，每条含分析 + 建议
8. 📎 重要链接：`• 标题: URL` 列表
9. 落款块：「— 简报结束 —」+ 免责声明 + 「扫码关注 · 获取更多安全情报」+ `{organization}` + 出品单位 + 联系人（配置留空则省略）

## 技术栈

- 语言：Python 3.10+
- 简报生成：LangChain（`ChatPromptTemplate` + `StrOutputParser`）已用于 analyzer
- 文档渲染：ReportLab（PDF）、纯字符串模板（Markdown/HTML）
- 现有链路：`collector`（搜索采集）→ `analyzer`（LLM 生成 Markdown）→ `markdown_to_html_sections` + `render_email_html`（邮件 HTML）→ `export_briefing_pdf`（PDF）；UI 查看器直接 `st.markdown` 渲染 Markdown，自动继承新结构

## 实现方案

保持 **Markdown 为唯一数据枢纽**，重构 Markdown 章节 schema 并增强 HTML/PDF 渲染器，使四种格式同源一致，避免大改 analyzer 对外接口。

- **配置层**：在 `BRIEFING_CONFIG["organization"]` 新增 `producer_unit`(出品单位)、`contact`(联系人/微信)、`footer_qr_text`(扫码关注文案，空则不渲染)、`disclaimer`(免责声明)，均给通用默认值、不写死品牌；在 `WATCH_CATEGORIES` 新增 2 个网络安全类目 `cyber_vuln`(CVE/漏洞)、`cyber_attack`(数据泄露/攻击事件/政策合规)，使 LLM 有真实数据可组织进新板块（collector 自动按类目并行采集）。
- **提示词层**：保留 top3 / insight / links 思路，重组为 `ai_dynamic`（产出 模型与技术/应用与落地/产业与市场）、`cyber_dynamic`（产出 漏洞与威胁/攻击事件/政策与合规）、`cve_table`（产出 Markdown 表格行 `| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |`）；子板块统一 `### 子标题` + `• [标签] 描述（来源：X / 日期）`。
- **生成层**：`analyzer.generate_briefing` 合并全部 collected_data，分别调用上述提示词，拼装新 Markdown schema（封面行 + 日期用 weekday 映射生成中文「（星期X）」+ 双主板块 + ⚠CVE 表格 + 💡研判 + 📎链接 + 落款块）；保留无 LLM 时的降级格式化与 `format_news_item` 工具。
- **模板层**：`MARKDOWN_TEMPLATE` 改新章节标题 + 封面行 + 落款块；`EMAIL_HTML_TEMPLATE` 与 `BRIEFING_STANDALONE_HTML` 改新结构 + 品牌化页眉(标题|org)/页脚(org+出品单位+联系人+扫码文案) + CVE 表格样式；`markdown_to_html_sections` 的 `SECTION_MAP` 更新到新标题，`_md_to_html` 增加 `#### ` 四级子标题与 Markdown 表格 `|` 行 → HTML `<table>` 转换。
- **PDF 层**：用 ReportLab 重写 `export_briefing_pdf`，`onPage` 回调渲染每页 running 页眉/页脚；首段 H1 作封面（标题+中文星期日期+org+出品单位）；章节图标标题与子标题；**CVE 用 `platypus.Table` 渲染**；结尾落款块（免责声明+扫码文案+org+出品单位+联系人，空则省略）；支持可选二维码图片（配置文件路径，缺省不渲染）。
- **接线层**：`main.py` / `scheduler.py` / `notifier.py` 邮件主题改为「AI 与网络安全每日情报简报」；其余（历史保存、PDF 附件、UI 预览）自动继承新 Markdown。

## 性能与可靠性

- LLM 调用由当前 6 段改为约 6 段（结构重组，量级相当），无显著开销增加；各段独立 try/except，单段失败不影响整体，沿用现有降级文案。
- PDF 中文字体沿用既有 `_register_chinese_font`（msyh/simhei/simsun），CVE 表格行数有界（取当日高危/在野项，上限约 10 行），无性能风险。
- 保持向后兼容：历史简报为旧 Markdown 仍能由 `st.markdown` 渲染；新渲染器仅影响新生成内容。

## 架构与数据流

```mermaid
flowchart TD
    A[collector.collect_all_categories] -->|Dict[cat_id:[results]]| B[analyzer.generate_briefing]
    B -->|新 Markdown schema| C[render_markdown_briefing]
    C --> D[main/scheduler: markdown_to_html_sections + render_email_html]
    C --> E[export_briefing_pdf 品牌化PDF]
    C --> F[UI: st.markdown 预览]
    D --> G[notifier 邮件/企微/钉钉]
    C --> H[briefing_history 存档]
```

## 目录结构与文件改动

```
intel-briefing/
├── ai_briefing/
│   ├── config.py              # [MODIFY] organization 增加 producer_unit/contact/footer_qr_text/disclaimer；WATCH_CATEGORIES 增加 cyber_vuln/cyber_attack（含 search_queries）
│   ├── prompts.py             # [MODIFY] 重写为 ai_dynamic/cyber_dynamic/cve_table + 保留 top3/insight/links；get_prompt 映射更新
│   ├── analyzer.py            # [MODIFY] generate_briefing 重写为新 Markdown schema；新增 _generate_ai_dynamic/_generate_cyber_dynamic/_generate_cve_table；中文星期日期；保留降级与 format_news_item
│   ├── templates.py           # [MODIFY] MARKDOWN_TEMPLATE/EMAIL_HTML_TEMPLATE/BRIEFING_STANDALONE_HTML 改新结构+品牌落款；SECTION_MAP 更新；_md_to_html 增加 #### 与 Markdown 表格→HTML 表格
│   └── notifier.py            # [MODIFY] 邮件主题字符串改为「AI 与网络安全每日情报简报」
├── src/export/
│   └── briefing_export.py     # [MODIFY] 用 ReportLab 重写：onPage 页眉页脚、封面、章节/子标题、CVE Table、落款块、可选二维码
└── main.py                    # [MODIFY] briefing 命令邮件主题改为新标题（scheduler.py 同改）
tests/
└── test_briefing_format.py    # [NEW] 冒烟测试：新 Markdown 含关键章节标题；markdown_to_html_sections 新 SECTION_MAP 映射正确；无 LLM 降级路径产出新结构
.env.example                   # [MODIFY] 增加 ORGANIZATION_* 品牌字段说明（producer_unit/contact/footer_qr_text/disclaimer）
README.md                      # [MODIFY] 简述简报新结构/品牌可配置
```

## 关键代码结构（节选）

```python
# ai_briefing/config.py 新增组织字段
BRIEFING_CONFIG = {
    "organization": {
        "name": "AI情报团队",          # 现有，作为 org 主名
        "team": "AI简报系统",
        "producer_unit": "",           # 出品单位（留空省略）
        "contact": "",                 # 联系人/微信（留空省略）
        "footer_qr_text": "",          # 扫码关注文案（留空省略）
        "disclaimer": "本简报基于公开信息整理，不构成投资或其他专业建议。"  # 可配置
    },
    ...
}

# analyzer 新 Markdown 骨架（伪代码）
def generate_briefing(self, collected_data, organization_name=None):
    org = BRIEFING_CONFIG["organization"]
    date_str = datetime.now().strftime("%Y年%m月%d日") + f"（{WEEKDAY_CN[datetime.now().weekday()]}）"
    top3 = self._generate_top3(collected_data, llm)
    ai_dyn = self._generate_ai_dynamic(collected_data, llm)      # 模型与技术/应用与落地/产业与市场
    cyber = self._generate_cyber_dynamic(collected_data, llm)     # 漏洞与威胁/攻击事件/政策与合规
    cve = self._generate_cve_table(collected_data, llm)          # Markdown 表格
    insights = self._generate_insights(collected_data, llm)
    links = self._generate_links(collected_data)
    return render_markdown_briefing(date_str, org, top3, ai_dyn, cyber, cve, insights, links)
```

## Agent Extensions

### Skill

- **pdf**
- Purpose: 指导用 ReportLab 生成品牌化 PDF（中文字体注册、platypus.Table 渲染 CVE 表格、onPage 回调实现每页页眉页脚与页码、可选二维码图片）。
- Expected outcome: 导出的 PDF 在章节顺序、封面、running 页眉页脚、CVE 表格与落款块上完全复刻目标样本版式，且中文字符正常显示。