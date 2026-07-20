---
name: briefing-dual-entry
overview: 方案 B：将数据源管理、订阅管理、完整生成界面迁移至简报中心 Tab，侧边栏仅保留精简版「立即生成」快捷按钮，实现双入口架构
design:
  styleKeywords:
    - Morandi Theme
    - Card-based Layout
    - Clean Hierarchy
    - Progressive Disclosure
  fontSystem:
    fontFamily: SF Pro Text, -apple-system
    heading:
      size: 22px
      weight: 600
    subheading:
      size: 16px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#7B9CB5"
      - "#8FA890"
    background:
      - "#F5F2EE"
      - "#FFFFFF"
      - "#E8E4DF"
    text:
      - "#5C5C5C"
      - "#8A8A8A"
    functional:
      - "#4a9d5f"
      - "#c94a4a"
todos:
  - id: migrate-data-sources
    content: 将 _render_data_sources() 迁移到 briefing_viewer.py 并改名为 render_data_sources_panel()，重命名所有 widget key 加 bf_ 前缀避免冲突
    status: completed
  - id: migrate-subscriptions
    content: 将 _render_subscriptions() 迁移到 briefing_viewer.py 并改名为 render_subscriptions_panel()，重命名所有 widget key 加 bf_ 前缀避免冲突
    status: completed
  - id: migrate-generate
    content: 在 briefing_viewer.py 中新建 render_generate_panel() 承载完整生成逻辑，同时创建 render_briefing_config() 组合三个面板
    status: completed
  - id: slim-sidebar
    content: 精简 sidebar.py：移除 _render_data_sources/_render_subscriptions 调用；_render_briefing_actions 改为仅含快速生成+历史跳转两个按钮
    status: completed
    dependencies:
      - migrate-data-sources
      - migrate-subscriptions
      - migrate-generate
  - id: update-ui-entry
    content: 修改 ui.py 的 tab_briefing 区域，在 preview/history/welcome 之前插入 render_briefing_config() 调用
    status: completed
    dependencies:
      - migrate-generate
  - id: update-welcome-and-styles
    content: 更新 render_briefing_welcome() 引导文案指向页面内配置区；在 styles.py 中新增 .briefing-config-panel 卡片样式
    status: completed
    dependencies:
      - slim-sidebar
      - update-ui-entry
---

## Product Overview

将简报相关的配置功能（数据源管理、订阅管理、立即生成）从全局侧边栏迁移至简报中心 Tab 内，形成**双入口架构**：简报中心 Tab 内提供完整配置界面，侧边栏仅保留精简版快捷生成按钮。

## Core Features

- **简报中心 Tab 内嵌完整配置面板**：将 `_render_data_sources()`（数据源管理）、`_render_subscriptions()`（订阅者管理）、`_render_briefing_actions()` 的完整逻辑迁移到 `briefing_viewer.py` 中
- **侧边栏精简为快捷入口**：保留单个「立即生成」按钮 + 「查看历史」快捷跳转按钮
- **欢迎页引导更新**：三步流程卡片不再指向侧边栏，而是指向当前页面内的配置区域
- **样式一致性**：为简报中心内的配置区域新增与整体莫兰迪主题匹配的 CSS 样式

## 变更前后对比

**变更前**：

```
Sidebar (全局):
  Advanced:
    ├── 自定义模型 (通用)
    ├── 数据源管理  ← 简报相关，位置不当
    ├── 订阅管理    ← 简报相关，位置不当
  Action Bar:
    └── 立即生成 + 查看历史 ← 与简报 Tab 功能割裂

Briefing Tab (简报中心):
    ├── 预览区 (有内容时)
    ├── 历史列表 (触发时)
    └── 欢迎页 (默认) → 提示去侧边栏操作
```

**变更后**：

```
Sidebar (全局):
  Advanced:
    └── 自定义模型 (通用)
  Action Bar:
    ├── [⚡ 快速生成] 按钮 → 触发后结果展示在简报 Tab
    └── [📋 历史记录] 按钮 → 跳转简报 Tab 显示历史

Briefing Tab (简报中心):
    ├── 预览区 (有内容时)
    ├── 历史列表 (触发时)
    └── 配置面板 (默认/无预览时):
        ├── 📡 数据源管理 (完整 UI: 添加/启停/删除)
        ├── 📧 订阅管理 (完整 UI: SMTP/添加订阅者/列表)
        └── [🚀 生成简报] 按钮 (完整生成+推送+保存)
```

## Tech Stack

- **前端框架**: Streamlit (Python)，现有项目技术栈
- **样式系统**: 莫兰迪主题 CSS (`shared/ui/styles.py`)，内联 HTML/CSS
- **状态管理**: Streamlit `st.session_state`
- **语言**: Python 3.x

## Tech Architecture

### 架构模式：函数迁移 + 适配层重构

核心思路是将 `sidebar.py` 中的三个简报专用私有函数迁移到 `briefing_viewer.py` 成为公开渲染函数，同时在 sidebar 中保留一个精简的快捷调用版本。

### 数据流

```
Sidebar 快速生成按钮 click
  → 设置 session_state.current_briefing / show_briefing_history
  → 用户切换到 Briefing Tab 或自动提示
  → briefing_viewer 内的 render 函数读取 session_state 展示结果

Briefing Tab 内生成按钮 click  
  → 同样的 collector → analyzer → notifier 流程
  → 结果直接在当前 Tab 内展示 (session_state.current_briefing)
```

### 关键设计决策

1. **不抽取公共模块**: 生成逻辑约 40 行，复制两处比抽象共享模块更简洁（避免过度工程）
2. **Streamlit key 冲突规避**: 迁移后的函数需要重命名所有 st widget key（如 `source_type_selector` → `bf_source_type_selector`），避免与 sidebar 可能的残留 key 冲突
3. **Session state 共享**: 两套入口共用同一组 session_state key（`current_briefing`, `show_briefing_history`, `email_config`），确保状态同步

## Implementation Details

### Directory Structure

```
d:\Improve\Project\Python\IntelNexus\
├── src/ui/
│   ├── sidebar.py                    # [MODIFY] 移除 _render_data_sources, _render_subscriptions; 精简 _render_briefing_actions
│   └── briefing_viewer.py            # [MODIFY] 新增 render_data_sources_panel, render_subscriptions_panel, render_generate_panel; 更新 welcome 页
├── ui.py                             # [MODIFY] tab_briefing 内增加配置面板渲染调用
└── shared/ui/
    └── styles.py                     # [MODIFY] 新增简报中心内部配置面板样式 (.briefing-config-panel 等)
```

### Key Code Structures

```python
# briefing_viewer.py — 新增函数签名
def render_data_sources_panel() -> None:
    """在简报中心 Tab 内渲染数据源管理面板"""
    # 从 sidebar._render_data_sources() 迁移，key 加 bf_ 前缀

def render_subscriptions_panel() -> None:
    """在简报中心 Tab 内渲染订阅管理面板"""
    # 从 sidebar._render_subscriptions() 迁移，key 加 bf_ 前缀

def render_generate_panel() -> None:
    """在简报中心 Tab 内渲染完整生成按钮及结果反馈"""
    # 完整的 collector → analyzer → notifier 流程

def render_briefing_config() -> None:
    """组合以上三个面板为简报配置区域"""
    # 使用 st.columns 或垂直布局组织三个子面板
```

## 设计概述

简报中心 Tab 从纯展示页升级为「配置 + 展示」一体化工作台。采用**卡片式分区布局**，将数据源管理、订阅管理、生成操作分为三个独立的功能卡片，每个卡片使用 st.expander 折叠以节省空间。

### 页面布局设计

```
┌──────────────────────────────────────────────────────┐
│  Briefing Center                                     │
│                                                      │
│  ┌─ Preview Area ──────────────────────────────────┐ │
│  │  (有简报内容时显示 Markdown + 下载按钮)           │ │
│  └──────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ History List ──────────────────────────────────┐ │
│  │  (show_briefing_history=True 时显示历史列表)      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Config Workspace ──────────────────────────────┐ │
│  │                                                   │ │
│  │  ┌─ Data Sources Card ──────────────────────┐   │ │
│  │  │ 📡 数据源管理                        [展开] │   │ │
│  │  │  - 添加 RSS/Web 数据源                   │   │ │
│  │  │  - 启停/删除已有数据源                   │   │ │
│  │  └──────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ Subscriptions Card ─────────────────────┐   │ │
│  │  │ 📧 订阅管理                          [展开] │   │ │
│  │  │  - SMTP 邮件配置                         │   │ │
│  │  │  - 添加/管理订阅者                       │   │ │
│  │  └──────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ Generate Action Card ───────────────────┐   │ │
│  │  │         [ 🚀 生成简报 ]                  │   │ │
│  │  │  (一键采集→分析→推送→保存)                │   │
│  │  └──────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### Sidebar 精简设计

```
┌─ Sidebar ─────────────────────────┐
│  IntelNexus                       │
│  AI Intelligence Hub              │
│                                   │
│  CORE                             │
│  ○ 标准搜索                       │
│  ○ 暗网搜索  ...                   │
│  LLM Model: qwen2.5:7b            │
│  Threads: 5                       │
│  Language: 中文                   │
│                                   │
│  ADVANCED                         │
│  ▸ 自定义模型                     │
│                                   │
│  ┌─ Quick Actions ──────────────┐ │
│  │  [ ⚡ 快速生成简报 ]          │ │
│  │  [ 📋 历史记录 ]             │ │
│  └──────────────────────────────┘ │
└───────────────────────────────────┘
```

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 在实施过程中快速定位所有被迁移函数的依赖项和引用关系（如 import 链、session_state key 引用点）
- Expected outcome: 确保迁移过程中没有遗漏隐式依赖