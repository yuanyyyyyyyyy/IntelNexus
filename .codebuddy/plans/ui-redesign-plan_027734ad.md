---
name: ui-redesign-plan
overview: 针对 IntelNexus 的三大 UI 问题提供完整重设计方案：去除 AI 感 emoji、重构简报中心排版、优化侧边栏信息层级
design:
  styleKeywords:
    - Morandi Understated
    - Professional Tool Aesthetic
    - Information Density First
    - Typography Hierarchy
    - Clean Minimalism
    - No Decorative Elements
    - Vertical Card Layout
  fontSystem:
    fontFamily: "-apple-system, BlinkMacSystemFont, SF Pro Text, Helvetica Neue, Arial, sans-serif"
    heading:
      size: 40px
      weight: 600
    subheading:
      size: 22px
      weight: 600
    body:
      size: 15px
      weight: 400
  colorSystem:
    primary:
      - "#7B9CB5"
      - "#8FA890"
      - "#9CB5B0"
    background:
      - "#E8E4DF"
      - "#F5F2EE"
      - "#DCD8D3"
      - "#FFFFFF"
    text:
      - "#5C5C5C"
      - "#8A8A8A"
    functional:
      - "#C4A4A4"
      - "#C9C5C0"
todos:
  - id: clean-emoji-ui
    content: 清理 ui.py 中 Tab 标签和主界面的 emoji，改为纯文字
    status: completed
  - id: clean-emoji-sidebar
    content: 清理 sidebar.py 所有 section-header 和按钮中的 emoji，替换为文字或移除
    status: completed
  - id: clean-emoji-briefing
    content: 全面重写 briefing_viewer.py 的 render_briefing_welcome 布局，同时清理其余函数中的 emoji
    status: completed
  - id: update-css-styles
    content: 在 styles.py 中新增简报步骤卡片(.briefing-step-card)、状态圆点(.status-dot)、操作文字按钮等 CSS 类
    status: completed
  - id: restructure-sidebar
    content: 将 sidebar.py 中 4 个进阶模块包裹进 st.expander("高级配置")，实现侧边栏层级分离
    status: completed
    dependencies:
      - clean-emoji-sidebar
  - id: extend-i18n-keys
    content: 在 intel-search 和 intel-briefing 两个 i18n 文件的 LANG 字典中补充新增的文字 key（view/delete/advanced_config 等）
    status: completed
    dependencies:
      - code-explorer
---

## 产品概述

对 IntelNexus Streamlit 应用进行 UI 美化重构，解决三大视觉与体验问题：(1) 全界面 Emoji 泛滥导致 AI 模板感过重；(2) 简报中心欢迎页左右分栏比例失调、右侧空旷；(3) 侧边栏 6 个功能模块平铺堆叠、无信息层级区分。

## 核心功能

### 问题 1：Emoji 去除与文字化替换

**现状**：全项目约 30+ 处 emoji 使用，分布在 tab 标题、section header、按钮文本、状态指示、步骤列表等位置。

**目标**：

- 完全去除所有装饰性/标题性 emoji（📰📡👥🚀⚡💡🧅📬📧等）
- 功能按钮中的 emoji 操作符替换为中文/英文文字（👁️→"查看"、🗑️→"删除"）
- 状态指示 emoji 替换为 CSS 圆点 + 文字描述（🟢🔴 → 绿色/红色圆点）
- Tab 标签改为纯文字（"情报搜索"、"简报中心"）

### 问题 2：简报中心欢迎页重排

**现状**：`briefing_viewer.py:107-127` 使用 `st.columns([1, 2])` 左右分栏，左侧介绍卡片密集、右侧 `st.info` 提示区过于空旷，视觉失衡。

**目标**：改为单列垂直布局，包含：

- 顶部一行引导语（简洁说明简报中心用途）
- 中部三步流程卡片（水平排列的等宽小卡片，每步含序号+标题+一句话说明）
- 底部操作提示区域（替代原 st.info，使用样式化容器）

### 问题 3：侧边栏层级重组

**现状**：`sidebar.py:516-529` 的 `render_sidebar()` 按顺序平铺调用 6 个模块：搜索模式(128行)、模型设置(20行)、自定义模型(70行)、数据源(67行)、订阅管理(158行)、简报操作(55行)，全部展开时侧边栏极长且无主次之分。

**目标**：按使用频率分为两层：

- **核心层（始终可见）**：搜索模式选择 + 模型/线程/语言设置 -- 这是每次搜索都会用到的
- **进阶层（默认收起为 expander）**：暗网设置 | 自定义模型 | 数据源管理 | 订阅者管理 | 简报操作 -- 这些是低频配置项

## 技术栈

- **框架**：Streamlit（Python Web UI），版本兼容现有项目
- **样式**：自定义 CSS 注入（`shared/ui/styles.py`），基于 Morandi 色系 CSS 变量系统
- **国际化**：i18n 通过 `src/ui/i18n.py` 的 `get_text(key)` 函数，支持中英双语

## 技术架构

### 修改范围（4 个文件）

```
IntelNexus/
├── ui.py                              # [MODIFY] Tab 标签去 emoji
├── src/ui/
│   ├── sidebar.py                     # [MODIFY] 侧边栏层级重构：核心可见 + 进阶收起
│   ├── briefing_viewer.py             # [MODIFY] 简报欢迎页重排 + 全面去 emoji
│   └── i18n.py                        # [MODIFY] 新增去 emoji 后的文字 key（如 "view"/"delete"）
└── shared/ui/
    └── styles.py                      # [MODIFY] 新增简报卡片/侧边栏分组等 CSS 类
```

### 实现策略

**策略 1：Emoji 清理**

- 采用全局搜索替换方式，逐文件处理
- 按钮 emoji 用 `get_text("view")` / `get_text("delete")` 等新 i18n key 替代
- Section header 中的 emoji 直接删除，保留纯文字标题
- 不破坏任何业务逻辑，仅修改展示层字符串

**策略 2：简报中心垂直卡片布局**

- 移除 `st.columns([1, 2])` 左右分栏
- 改为单列流式布局：引导语 → 三步流程行（3 列等宽）→ 操作提示
- 使用自定义 CSS 类 `.briefing-step-card` 统一步骤卡片的圆角/背景/内边距
- 步骤序号用 CSS 伪元素或内联 `<span>` 渲染数字圆圈，不依赖 emoji

**策略 3：侧边栏 Expander 分组**

- 将 `_render_custom_models()` / `_render_data_sources()` / `_render_subscriptions()` / `_render_briefing_actions()` 四个函数包裹在 `st.expander("高级配置", expanded=False)` 中
- `_render_search_mode()` 和 `_render_model_settings()` 保持始终可见
- 暗网设置本身已是 expander，无需额外处理
- 各 render 函数内部逻辑不变，只改变调用时的外层容器

### 数据流

```
ui.py (入口)
  ├── st.tabs(["情报搜索", "简报中心"])        # 去 emoji
  ├── tab_search: (不变)
  └── tab_briefing:
      ├── render_briefing_preview()          # 内部 📄→纯文字标题
      ├── render_briefing_history()          # 内部 📋/👁️/🗑️→文字
      └── render_briefing_welcome()           # 重写布局

st.sidebar (侧边栏)
  ├── _render_search_mode()                  # 可见
  ├── _render_model_settings()               # 可见
  └── st.expander("高级配置"):               # 新增外层
       ├── _render_custom_models()
       ├── _render_data_sources()
       ├── _render_subscriptions()
       └── _render_briefing_actions()
```

## 实现注意事项

- **i18n 兼容**：新增的 text key（view/delete/status_online/status_offline 等）需同时添加到 intel-search 和 intel-briefing 两个子项目的 i18n LANG 字典中，否则 `get_text()` 会 fallback 到 key 本身
- **CSS 类命名**：遵循现有 `.section-header` / `.result-card` 的命名风格，使用 kebab-case
- **向后兼容**：session_state 中的 key 名（current_briefing, show_briefing_history 等）完全不变
- **暗网设置的嵌套**：`_render_search_mode()` 内部的暗网 expander 已有独立展开控制，不受外层高级配置 expander 影响

## 设计理念：克制专业 (Understated Professional)

IntelNexus 是面向分析师的情报工具，不是 AI demo。设计方向参考 Bloomberg Terminal / Datadog 这类专业工具的美学——**信息密度优先、装饰元素最小化、用排版层级而非图标来传达含义**。

整体风格关键词：**Morandi 克制风** —— 在现有低饱和度色系基础上，进一步削减视觉噪音，让内容本身成为焦点。

---

## 页面 1：主界面 — 搜索 Tab（调整后效果）

### Block 1：顶部标题区（微调）

- 保留 "IntelNexus" 大标题 + "多源网络情报分析平台" 副标题
- 字体大小/颜色不变，已足够克制
- 无 emoji，当前已符合要求

### Block 2：Tab 导航栏（改动）

- **改前**："🔍 情报搜索" | "📊 简报中心"
- **改后**："情报搜索" | "简报中心"
- 使用纯文字标签，Tab 下划线指示当前位置
- 文字颜色：未选中 `var(--morandi-text-light)`，选中 `var(--morandi-blue)`
- 字重：选中态 600，未选中 400

### Block 3：搜索输入区（不变）

- 搜索框 + 按钮保持现有样式（圆角14px、蓝色主按钮）
- 已是干净的交互设计

### Block 4：结果面板（微调）

- 结果卡片标题前的 emoji（如果有）去除
- 操作按钮统一为文字链接风格

---

## 页面 2：主界面 — 简报中心 Tab（重点改动）

### Block 1：简报预览区（当有简报时显示）

- 标题改前："📄 简报预览"
- 标题改为："简报预览"（h2，24px，font-weight 600）
- 下载按钮保持现有 MD/HTML 双格式

### Block 2：历史列表（当查看历史时显示）

- 标题改前："📋 历史记录"
- 标题改为："历史记录"
- 每行操作按钮：
- 改前："👁️" "🗑️"
- 改后："查看" "删除"（小尺寸文字按钮，secondary 样式）
- 行间距适当增加，提升可读性

### Block 3：欢迎引导页（完全重写，核心改动）

**布局结构**：单列垂直排列，三个区块依次向下流动

**区块 A — 顶部引导语**（1 行）

```
┌─────────────────────────────────────────────────────┐
│  配置数据源和订阅者后，AI 将自动采集并生成每日情报简报    │
└─────────────────────────────────────────────────────┘
```

- 背景色：`var(--morandi-card)`
- 圆角：12px
- 内边距：16px 24px
- 文字颜色：`var(--morandi-text-light)`
- 字号：14px

**区块 B — 三步流程卡片**（水平 3 列等宽）

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   ①          │  │   ②          │  │   ③          │
│  配置数据源   │  │  添加订阅者   │  │  生成简报     │
│              │  │              │  │              │
│ 添加 RSS 或  │  │ 设置推送渠道  │  │ 点击生成按钮  │
│ 网页数据源   │  │ 和关注类别   │  │ 开始自动汇总  │
└──────────────┘  └──────────────┘  └──────────────┘
```

每个步骤卡片样式：

- 背景：白色 (`#FFFFFF`)，带细边框 `1px solid var(--morandi-border)`
- 圆角：14px
- 内边距：20px 16px
- 序号圆圈：28px 直径，`var(--morandi-blue)` 背景，白色数字，居中
- 标题：15px，font-weight 600，`var(--morandi-text)`
- 说明：13px，`var(--morandi-text-light)`，line-height 1.6
- 卡片间 gap：16px
- 微妙阴影：`0 2px 8px rgba(0,0,0,0.04)`

**区块 C — 操作提示**（底部）

```
┌─────────────────────────────────────────────────────┐
│  提示：首次使用请先在左侧配置数据源和订阅者，            │
│  然后点击「生成简报」开始使用                          │
└─────────────────────────────────────────────────────┘
```

- 左侧竖条：3px 宽，`var(--morandi-blue)` 作为视觉锚点
- 背景：浅蓝 tint `rgba(123,156,181,0.08)`
- 圆角：10px
- 替代原来的 `st.info(icon="💡")`

---

## 页面 3：侧边栏（结构性改动）

### Block 1：品牌标识区（不变）

- "IntelNexus" 标题 + 副标题，保持现有 `.sidebar-title` / `.sidebar-subtitle` 样式

### Block 2：核心操作区（始终可见）

```
┌─ 搜索模式 ──────────────────────┐
│ ○ 全部来源  ● 网页搜索           │
│   新闻资讯    暗网搜索           │
└─────────────────────────────────┘

┌─ 设置 ──────────────────────────┐
│ AI 模型:  [qwen2.5:7b       ▼]  │
│ 并发数:   [===========5====]     │
│ 语言:     [中文            ▼]   │
└─────────────────────────────────┘
```

- section-header 去 emoji："搜索模式"（而非带 emoji 版本）
- 分隔线 `st.markdown("---")` 保留，用于视觉分隔

### Block 3：高级配置（默认收起的 Expander）

```
▸ 高级配置                           ← 默认折叠
```

展开后内部包含（保持原有顺序）：

| 子项 | 展开状态 | 说明 |
| --- | --- | --- |
| 暗网设置 | 默认展开（自身已有 expander 逻辑） | TOR 端口/状态检测 |
| 自定义模型 | 默认折叠 | 添加/管理自定义 LLM |
| 数据源管理 | 默认折叠 | RSS/Web 数据源 CRUD |
| 订阅管理 | 默认折叠 | 邮件设置/订阅者/推送渠道 |
| 简报操作 | N/A（直接渲染按钮） | 生成简报 + 查看历史 |


Expander 样式：

- 标签："高级配置"，不带任何 icon
- 展开后内部各子模块的分隔线保留
- 整体减少约 60% 的侧边栏默认高度

## Agent Extensions

### Skill

- **frontend-design**
- Purpose: 为 UI 重构提供专业的视觉设计指导，确保设计方案不是千篇一律的 AI 模板风格
- Expected outcome: 输出具有辨识度的莫兰迪克制风设计方案，涵盖色彩、字体、布局和签名元素

### SubAgent

- **code-explorer**
- Purpose: 确认 i18n 文件的确切路径和 LANG 字典结构，确保新增 text key 时能正确定位到修改目标
- Expected outcome: 定位 `intel-search/src/ui/i18n.py` 和 `intel-briefing/src/ui/i18n.py` 中的 LANG 字典，确认新增 key 的插入位置