---
name: fix-briefing-blank-and-ollama
overview: 修复两个问题：(1) 主界面简报中心tab显示空白 - 缺少 render_briefing_welcome() 调用；(2) Ollama模型未加载到下拉列表 - 需排查配置注入问题
design:
  architecture:
    framework: html
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 32px
      weight: 600
    subheading:
      size: 18px
      weight: 500
    body:
      size: 16px
      weight: 400
todos:
  - id: fix-config-injection
    content: 在 ui.py 中添加 settings.set() 配置注入，修复 Ollama 模型加载问题
    status: completed
  - id: fix-briefing-welcome
    content: 在 ui.py 中添加 render_briefing_welcome() 调用及对应 import，修复简报中心空白
    status: completed
---

## 产品概述

修复 IntelNexus Web UI 中存在的两个功能缺陷：(1) 简报中心 Tab 页点击后显示空白；(2) Ollama 模型列表无法加载到 AI 模型下拉选择框中。

## 核心功能

### 问题1：简报中心空白

- **现象**：用户在主界面（localhost:8501）点击"简报中心"Tab 后，右侧内容区域完全空白，无任何内容渲染
- **根因**：主入口 `ui.py` 第 87-91 行的 Briefing Tab 渲染逻辑**遗漏了 `render_briefing_welcome()` 调用**。当前逻辑为：

```python
with tab_briefing:
if st.session_state.get("show_briefing_history"):
render_briefing_history()
else:
render_briefing_preview()  # current_briefing 为空时直接返回，无任何输出
```

而 `render_briefing_preview()` 有守卫条件——当 `current_briefing` 不存在时直接 return。独立简报页面 `intel-briefing/ui.py` 正确调用了三个函数（preview + history + welcome），但主入口缺少 welcome。

- **预期效果**：点击"简报中心"Tab 后，应显示欢迎引导页（包含操作步骤说明和快捷操作提示）

### 问题2：Ollama 模型列表不加载

- **现象**：已启动 `ollama serve`，但刷新界面后 AI 模型下拉框仅显示云端预定义模型（gpt-4.1 等），不包含本地 Ollama 模型
- **根因**：**配置注入机制断裂**。调用链路如下：

1. `main.py` 第 16-23 行正确调用了 `settings.set({OLLAMA_BASE_URL: ...})`
2. 但 `main.py` 通过 `streamlit run ui.py` 以**子进程方式启动 UI**
3. `ui.py` 运行在新进程中，**从未调用 `settings.set()`**，导致 `_config` 字典为空
4. `fetch_ollama_models()` → `_get_ollama_base_url()` → `get_config("OLLAMA_BASE_URL", "")` 返回空字符串
5. 空字符串被判定为 falsy，直接返回 `[]`

- **预期效果**：AI 模型下拉框应同时展示云端模型和本地 Ollama 已安装模型（如 qwen2.5:7b、llama3 等）

## 技术栈

- Python 3 + Streamlit（Web UI 框架）
- 共享配置注入机制（`shared/settings` 模块）
- Ollama HTTP API（本地 LLM 服务）

## 实现方案

### 架构分析

```
main.py (进程A)
  ├── settings.set({OLLAMA_BASE_URL: "http://127.0.0.1:11434", ...}) ✓
  └── streamlit run ui.py  ← 子进程启动，配置不会传递
         │
         ▼
ui.py (进程B，全新进程)
  ├── ❌ 缺少 settings.set() 调用 → _config = {}
  ├── ❌ 缺少 render_briefing_welcome() 调用
  └── render_sidebar() → get_model_choices() → fetch_ollama_models()
        → get_config("OLLAMA_BASE_URL") → "" → 返回 []
```

### 修改策略

#### 修改1：`d:\Improve\Project\Python\IntelNexus\ui.py` — 双重修复

1. **添加配置注入**（在 Streamlit 导入之后、业务代码之前）：

```python
from shared.settings import set as set_config
from config import (
OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
GOOGLE_API_KEY, NEWS_API_KEY,
)
set_config({
"OLLAMA_BASE_URL": OLLAMA_BASE_URL,
"OPENROUTER_BASE_URL": OPENROUTER_BASE_URL,
"OPENROUTER_API_KEY": OPENROUTER_API_KEY,
"GOOGLE_API_KEY": GOOGLE_API_KEY,
"NEWS_API_KEY": NEWS_API_KEY,
})
```

注意使用 `config.py` 中定义的默认值（含 `.env` 覆盖），而非硬编码。

2. **添加 `render_briefing_welcome` 到 import 和调用链**：

- Import 行添加：`render_briefing_welcome`
- Briefing Tab 区域（第 91 行后）：添加 `render_briefing_welcome()` 调用

### 实现注意事项

- 配置注入必须放在 `st.set_page_config()` 之后但在 `render_sidebar()` 之前，确保所有依赖模块能正确读取配置
- `render_briefing_welcome()` 自身已有守卫条件（当 `current_briefing` 或 `show_briefing_history` 存在时会 return），所以可以安全地无条件调用

本次任务不涉及新建或大幅改造 UI，仅需修复现有渲染逻辑中的遗漏调用。无需设计新组件或新页面。