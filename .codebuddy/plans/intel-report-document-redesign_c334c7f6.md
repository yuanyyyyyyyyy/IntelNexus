---
name: intel-report-document-redesign
overview: 将情报搜索结果区域从 morandi 圆角卡片重构为 Intel Briefing Document 文档风格：分类横幅页眉（CONFIDENTIAL）、流式摘要正文、内嵌指标条、可折叠分析面板、工具栏式导出区，统一冷灰工业风 token
design:
  architecture:
    framework: html
  styleKeywords:
    - Intelligence Document
    - Cold Industrial
    - Monospace Headers
    - Data-Dense
    - No-Emoji
    - Classification Banner
  fontSystem:
    fontFamily: "'SF Mono', 'Consolas', 'Liberation Mono', Menlo, monospace"
    heading:
      size: 18px
      weight: 700
    subheading:
      size: 13px
      weight: 600
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#0366D6"
      - "#0550AE"
      - "#1F2937"
    background:
      - "#FFFFFF"
      - "#F9FAFB"
      - "#1F2937"
    text:
      - "#111827"
      - "#6B7280"
      - "#F9FAFB"
    functional:
      - "#DC2626"
      - "#059669"
      - "#D97706"
      - "#E5E7EB"
todos:
  - id: ir-css
    content: 在 shared/ui/styles.py 的 render_morandi_theme_css() 末尾追加 .intel-report 完整 CSS token 系统（header/metrics/panel/toolbar/badge 约120行）+ 覆盖旧的 .result-card/.report-section/.stat-* morandi 样式
    status: completed
  - id: ir-pipeline
    content: 重构 intel-search/src/ui/search_pipeline.py 第77-110行 meta 卡片和第218-222行报告容器：改用 ir-meta-card 和 .intel-report 包裹 + 文档头横幅 HTML
    status: completed
    dependencies:
      - ir-css
  - id: ir-results
    content: 重写 intel-search/src/ui/results.py：清除全部emoji(10+处)，st.metric改为.ir-metric HTML卡，四个section用.ir-panel包裹，标题用等宽label
    status: completed
    dependencies:
      - ir-pipeline
  - id: ir-download
    content: 重构 intel-search/src/ui/download.js：selectbox+button 改为一行 .ir-toolbar 内联格式按钮组 [MD][PDF][DOCX][XLSX]
    status: completed
    dependencies:
      - ir-css
  - id: ir-detail
    content: 清理 intel-search/src/ui/results_detail.js 的 emoji残留（📋📌📝🔗），适配 .ir-panel 样式
    status: completed
    dependencies:
      - ir-css
  - id: ir-i18n
    content: 使用 [skill:humanizer] 清理 intel-search/src/ui/i18n.py 报告相关 emoji 文案（📋📌🔗💡）+ 新增 intel_report/confidential/executive_summary 等 key
    status: completed
  - id: ir-lint
    content: 运行 lint 检查确认全部文件无语法错误，验证 CSS 选择器作用域未污染其他 Tab
    status: completed
    dependencies:
      - ir-css
      - ir-pipeline
      - ir-results
      - ir-download
      - ir-detail
      - ir-i18n
---

## 产品概述

将情报搜索页面的"生成的报告"区域，从当前的 morandi 暖色圆角卡片风格，重构为 **Intel Briefing Document（情报简报文档风格）** — 具有正规情报产品视觉特征的专业报告界面。

## 核心功能

- **报告文档头横幅**: 深色底 `#1F2937` + 白字 + 红色 CONFIDENTIAL 标记 + 时间戳
- **Executive Summary 容器**: 流式摘要正文用白色底等宽标签容器包裹，与下方分析面板明确分离
- **Assessment Metrics 条**: 四个指标（平均可信度/高/低/一致性）用紧凑数字条展示（替代当前 st.metric）
- **四个分析折叠面板**: 可信度表格 / 冲突列表 / 知识图谱 / 证据链 — 统一用 `.ir-panel` 样式，清理所有 emoji
- **导出工具栏**: 替代当前 selectbox+button 为一行紧凑的格式按钮组 [MD] [PDF] [DOCX] [XLSX]
- **搜索元信息卡片**: 查询优化结果和搜索统计卡片也纳入新样式体系

## 视觉效果目标

- 顶部分类横幅 `INTEL REPORT · {timestamp} · CONFIDENTIAL` 作为签名元素
- 全局去除 emoji（`📊🟢🟡🔴⚠️🕸️🔗✅❌📝📋📌🔗💡`），用颜色编码 dot/badge 替代
- 与已完成的侧边栏（冷灰）和 Briefing Center（workbench）在色调上统一，但报告区有独立的正式感层次

## Tech Stack

- **前端框架**: Streamlit (已有项目)
- **样式方案**: 嵌入式 CSS (通过 `st.markdown("<style>...</style>", unsafe_allow_html=True)`)
- **语言**: Python 3.x (Streamlit 应用)

## 技术架构

### 架构设计

```
intel-search/ui.py (入口)
    |
    |-- render_light_theme_css()          # 保持不变
    |-- render_morandi_theme_css()        # [MODIFY] 新增 .intel-report token 系统
    |       |
    |       +-- .ir-header                # 文档头横幅 (深灰底+红标记)
    |       +-- .ir-surface               # 报告内容白底容器
    |       +-- .ir-metrics               # 指标条 (4列紧凑数字卡)
    |       +-- .ir-panel                 # 分析面板 (替代旧 expander 默认样式)
    |       +-- .ir-toolbar               # 导出工具栏
    |       +-- 覆盖: .result-card, .report-section, .stat-* 等 morandi 样式
    |
    |-- run_search_pipeline()             # [MODIFY] 报告容器改用 ir-* 类名
    |-- render_results_panels()           # [REWRITE] 清理 emoji + 新 CSS 类
    |-- render_download_section()         # [MODIFY] 工具栏化
    |-- render_results_detail()           # [MODIFY] 清理 emoji
```

### 关键技术决策

| 决策点 | 方案 | 原因 |
| --- | --- | --- |
| 报告容器作用域 | 用 `.intel-report` class 包裹全部内容，CSS 选择器限定在其内 | 避免污染 Briefing Tab 的 bf-workbench 样式 |
| Expander 自定义 | 通过 `[data-testid="stExpander"]` 选择器覆盖默认边框/背景 | Streamlit 不支持自定义 expander 外观，只能靠 CSS 强制覆盖 |
| 指标展示 | 从 `st.metric()` 改为 HTML `.ir-metric` 卡片 | st.metric 无法自定义样式到需要的精细程度；HTML 更可控 |
| Emoji 替换 | 可信度等级用 `.ir-badge` (绿/黄/红背景色)；冲突严重度同理 | 去除 AI 味的同时保留语义区分度 |
| 文档头时间 | 直接在 pipeline 中用 `datetime.now()` 注入 | 无需 session_state 额外存储 |


### 数据流不变

- `run_search_pipeline()` 返回值不变（无返回值，副作用写入 session_state）
- `search_mode`, `model`, `threads` 三值仍然由 sidebar 返回给 ui.py
- 所有 session_state key (`streamed_summary`, `credibility_data`, `conflicts`, `kg_entities` 等) 不变

## 目录结构

```
d:\Improve\Project\Python\IntelNexus\
├── shared/ui/styles.py                          # [MODIFY] 在 render_morandi_theme_css() 末尾追加 .intel-report CSS block (~120行)
├── intel-search/src/ui/search_pipeline.py         # [MODIFY] 第77-83行 result-card → ir-meta-card; 第218-222行 report-section → intel-report 容器
├── intel-search/src/ui/results.py                # [REWRITE] 全面重构：emoji 清除 + ir-metrics + ir-panel
├── intel-search/src/ui/download.py              # [MODIFY] UI 层改为工具栏风格
├── intel-search/src/ui/results_detail.py         # [MODIFY] 清理 emoji (📋📌📝🔗)
├── intel-search/src/ui/i18n.py                   # [MODIFY] 清理 emoji 残留文案 + 新增 report 相关 key
└── intel-search/ui.py                            # [MINOR] 可能需要注入 intel-report CSS 的调用
```

## Implementation Notes

- **CSS 作用域**: `.intel-report` 选择器必须足够具体，避免影响 bf-workbench 区域。使用 `.intel-report > *` 和 `.intel-report .class` 双层策略
- **Expander 覆盖**: Streamlit 的 expander 使用 `data-testid="stExpander"`，但全局选择可能影响到 sidebar。解决方案: 用 `.intel-report [data-testid="stExpander"]` 限制范围
- **流式输出兼容**: `summary_slot = st.empty()` + `summary_slot.markdown()` 的模式不能变，只需在外层包一个 `<div class="ir-summary">`
- **性能**: 新增纯 CSS，无额外 JS 运行时开销
- **Blast radius control**: 只修改 `intel-search/` 下的文件和 `shared/ui/styles.py` 中新增 CSS block，不动 briefing viewer / sidebar 已完成的代码

## Design Approach: Intel Briefing Document (Option A)

### 设计风格定位

模仿真实情报机构（CIA/FBI/DIA）的情报产品页面设计语言 -- 深色分类横幅页眉、等宽字体标题、紧凑数据指标、结构化分析面板。这不是"扮演间谍"，而是让用户感受到这是一份**经过专业处理的、可信赖的情报产品**。

### 页面规划 (3 个区块)

#### Block 1: Report Header (文档头横幅) - 固定顶部

深灰色 (`#1F2937`) 横幅横跨全宽，包含三段信息：

- 左侧: `INTEL REPORT` 大号等宽体白字
- 中间: 时间戳 `2026-07-21 00:51` 小号等宽灰字
- 右侧: `CONFIDENTIAL` 红色 (`#DC2626`) 白字 badge
底部有 1px 细线分割。

#### Block 2: Executive Summary + Metrics (摘要+指标)

上半部为纯白底大区域，包含：

- `EXECUTIVE SUMMARY` 等宽小标签 (11px uppercase gray)
- 流式生成的 Markdown 正文（最大阅读面积）
- 分割线后接四格紧凑指标条：每格为大号数字 + 小号标签 + 底部彩色进度条

#### Block 3: Analysis Panels + Export (分析面板+导出)

下半部为浅灰底 (`#F9FAFB`) 区域，包含：

- 四个可折叠分析面板，每个面板头部用左侧 3px 彩色竖线标识类型（蓝=可信度、橙=冲突、紫=知识图谱、绿=证据链）
- 最底部为导出工具栏：一行内联按钮 [MD] [PDF] [DOCX] [XLSX]

#### 交互细节

- Panel hover 时左侧竖线亮度微增
- 导出按钮 hover 反色（白底蓝字 -> 蓝底白字）
- 所有动画均为 0.15s ease 过渡（无弹性/无上浮）
- 指标数字使用 tabular-nums 字体特性确保对齐

## Agent Extensions

### Skill

- **frontend-design**
- Purpose: 提供设计方向指导（已在方案阶段使用，实施阶段继续参考其 design principles）
- Expected outcome: 确保实现忠实于 Option A 设计规格，避免回退到通用模板感

### Skill

- **humanizer**
- Purpose: 清理 i18n 文案中的 AI 味残留（如 "AI-generated"、"智能分析" 等表述）
- Expected outcome: 报告相关文案简洁专业，无冗余修饰词