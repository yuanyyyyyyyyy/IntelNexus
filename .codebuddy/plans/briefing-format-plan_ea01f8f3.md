---
name: briefing-format-plan
overview: 将 IntelNexus 简报生成输出格式对齐到参考PDF（AI网安每日情报简报_20260707_V3.0.pdf）的专业6段式结构，去除emoji、优化排版层级
design:
  fontSystem:
    fontFamily: Source Han Sans SC, Noto Sans SC, Microsoft YaHei
    heading:
      size: 20px
      weight: 700
    subheading:
      size: 16px
      weight: 600
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#1F4E88"
    background:
      - "#FFFFFF"
      - "#F8F9FA"
    text:
      - "#212529"
      - "#6C757D"
    functional:
      - "#DEE2E6"
todos:
  - id: clean-md-template
    content: 清理 MARKDOWN_TEMPLATE 全部 7 处 emoji（标题+6个板块标题）
    status: completed
  - id: clean-html-templates
    content: 清理 EMAIL_HTML_TEMPLATE 和 BRIEFING_STANDALONE_HTML 中所有 h1/h2 的 emoji
    status: completed
  - id: update-section-map
    content: 更新 SECTION_MAP 的 6 个键值为无 emoji 版本
    status: completed
    dependencies:
      - clean-md-template
  - id: improve-top3-prompt
    content: 优化 TOP3_PROMPT 输出格式示例：改为多段落结构，对齐参考 PDF 的 TOP3 格式
    status: completed
  - id: clean-prompts-docstring
    content: 清理 prompts.py 文档注释和格式示例中的 emoji
    status: completed
---

## 产品概述

将 IntelNexus 系统生成的 AI 情报简报（Markdown / HTML）格式与参考 PDF `AI网安每日情报简报_20260707_V3.0.pdf` 对齐，去除模板中的装饰性 emoji、优化 TOP3 输出格式为多段落结构、确保三个输出模板（MD/邮件HTML/独立HTML）风格统一。

## 核心功能

### 参考PDF格式结构（6页）

1. **封面**: 标题 + 中文日期(含星期) + 团队名 + 出品单位行
2. **近日要闻TOP3**: 编号列表，每条 = 标题(粗体) + 多段详细描述 + 来源/日期行
3. **AI领域动态**: 三级子板块（模型与技术/应用与落地/产业与市场），每条格式 `[标签] 描述（来源：xxx / YYYY-MM-DD）`
4. **网络安全动态**: 三级子板块（漏洞与威胁/攻击事件/政策与合规），标签体系 [高危]/[数据泄露]/[政策] 等
5. **CVE漏洞表格**: 列 = CVE编号|影响产品|漏洞类型|CVSS|利用状态|建议措施
6. **趋势研判与防护建议**: 3条编号分析，每条含标题+3-5句深度分析+可执行建议
7. **重要链接**: 列表格式（标题: URL），最多10条
8. **页脚**: "— 简报结束 —" + 免责声明 + 二维码 + 组织信息

### 当前代码差距

| 差距项 | 参考PDF | 当前代码 | 需修改 |
| --- | --- | --- | --- |
| 标题emoji | 无 | # 🔐 AI... | templates.py x3 |
| 板块标题emoji | 无 ## 近日要闻 | ## 📌近日要闻 | templates.py x3 |
| TOP3格式 | 多段落/多行 | 单行压缩 | prompts.py TOP3_PROMPT |
| SECTION_MAP键 | 无emoji | 含emoji键 | templates.py |
| Prompt文档注释 | 无emoji | 含emoji | prompts.py docstring |


## 技术栈

- Python 3.x + Streamlit 框架
- Markdown 字符串模板渲染（`str.format()`）
- LLM 驱动内容生成（LangChain ChatPromptTemplate）

## 实现策略

### 策略：纯文本层修改，零架构变动

本次改动全部集中在**模板字符串**和**提示词文本**层面：

1. 从 3 个模板文件中删除 emoji 字符
2. 更新 SECTION_MAP 的匹配键
3. 调整 TOP3 prompt 的输出格式示例以引导 LLM 生成多段落内容

不涉及任何类结构、函数签名或调用链的变更。

## 修改范围

```
intel-briefing/ai_briefing/
├── templates.py      # [MODIFY] MARKDOWN_TEMPLATE + EMAIL_HTML_TEMPLATE + BRIEFING_STANDALONE_HTML + SECTION_MAP
└── prompts.py        # [MODIFY] 文档注释 + TOP3_PROMPT 输出格式示例
```

## 数据流（不变）

```
analyzer.py generate_briefing()
    → _generate_top3()          → get_prompt("top3")     → LLM
    → _generate_ai_dynamic()    → get_prompt("ai_dynamic")→ LLM
    → _generate_cyber_dynamic() → get_prompt("cyber_dynamic") → LLM
    → _generate_cve_table()     → get_prompt("cve_table")→ LLM
    → _generate_insights()      → get_prompt("insight")  → LLM
    → _generate_links()         → 直接组装
    → render_markdown_briefing(MARKDOWN_TEMPLATE) → 最终 MD
```

## 实现注意事项

- **SECTION_MAP 键值一致性**：markdown_to_html_sections() 用这些键做字符串匹配来拆分章节，必须与 MARKDOWN_TEMPLATE 中的 `## 标题` 文字完全一致
- **TOP3 prompt 格式调整**：当前 prompt 要求单行输出 `1. **标题**：描述`，需改为支持多段落的格式示例，引导 LLM 像参考 PDF 那样输出更丰富的内容
- **向后兼容**：已有的简报历史记录不受影响（它们是已渲染的静态内容）

本任务不涉及 UI 界面变更，仅修改简报生成器的文本模板和 LLM 提示词，无需前端框架设计。