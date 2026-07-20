---
name: briefing-center-redesign
overview: 将简报中心从 AI 味重的莫兰迪暖色系设计，重构为情报工作台风格的冷灰工业风界面。主要改动：删除欢迎引导页和三列步骤卡布局，改为单栏功能流；移除所有 emoji 和解释性文案；引入功能性彩色标签条系统；重写 CSS design token 为 GitHub/Linear 风格。
design:
  styleKeywords:
    - 工具型界面
    - 冷灰工业风
    - 功能标签条
    - 克制设计
    - GitHub Issues 风格
  fontSystem:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif"
    heading:
      size: 28px
      weight: 700
    subheading:
      size: 12px
      weight: 600
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#0366D6"
      - "#0969DA"
      - "#1A7F37"
      - "#BF8700"
    background:
      - "#F4F5F7"
      - "#FFFFFF"
    text:
      - "#111827"
      - "#6B7280"
    functional:
      - "#D1D5DB"
      - "#CB2431"
      - "#EAEEF2"
todos:
  - id: rewrite-styles
    content: 重写 shared/ui/styles.py 新增 bf-workbench 主题 CSS（冷灰色系变量 + 功能标签条 + 卡片组件样式）
    status: completed
  - id: update-i18n
    content: 使用 [skill:humanizer] 重写 intel-briefing/src/ui/i18n.py 简报相关文案（去 emoji、去欢迎语、去解释性文本）
    status: completed
  - id: refactor-viewer
    content: 重构 src/ui/briefing_viewer.py（删除 welcome 函数、config 面板改用标签条结构、preview/history 精简化）
    status: completed
    dependencies:
      - rewrite-styles
      - update-i18n
  - id: update-entry
    content: 修改 ui.py 移除 render_briefing_welcome() 调用并调整 tab 内渲染顺序
    status: completed
    dependencies:
      - refactor-viewer
  - id: verify-lints
    content: 运行 lint 检查确认无语法错误，验证样式作用域未污染搜索 Tab
    status: completed
    dependencies:
      - update-entry
---

## 产品概述

对 IntelNexus 的「简报中心」Tab 进行视觉重构，去除当前设计中的 AI 模板化痕迹（莫兰迪暖色系、emoji 标题、编号步骤卡、欢迎引导页、解释性提示文案），打造类似 GitHub Issues / Linear / VS Code 的情报工作台（Intelligence Workbench）风格界面。

## 核心功能

- **配色系统替换**：从暖色莫兰迪（`#E8E4DF`）切换到冷灰工业风（`#F4F5F7`），单一强调色 `#0366D6` + 功能性彩色标签条（蓝 `#0969DA` / 绿 `#1A7F37` / 橙 `#BF8700`）
- **布局重构**：删除三列 1-2-3 步骤卡片和欢迎引导页，改为单栏垂直功能流，每个功能区左侧加 4px 彩色竖条标识
- **文案去 AI 味**：移除所有 emoji 前缀、欢迎语、解释性提示框；按钮/标题用动词优先的简练表达；空状态改为行动导向
- **交互精简**：删除 hover 上浮动画（`translateY`），改用微变色反馈；删除渐变背景面板

## 技术栈

- **前端框架**：Streamlit（Python Web UI 框架，项目已有依赖）
- **样式方案**：内联 CSS 注入（通过 `st.markdown(<style>)` 方式，项目已有模式）
- **语言**：Python 3.x + CSS3

## 实现策略

采用**渐进式样式替换 + 结构精简**策略：

1. 在 `shared/ui/styles.py` 中新增一套 workbench 主题 CSS 变量和组件类，与现有 morandi 共存但不冲突
2. 重构 `src/ui/briefing_viewer.py` 中的渲染函数：删除 welcome 页，改造 config 面板使用新的功能标签条结构
3. 更新 `intel-briefing/src/ui/i18n.py` 中所有简报相关文案
4. 调整 `ui.py` 入口处的调用顺序

### 关键架构决策

- **不破坏搜索 Tab**：新样式通过 `.bf-` 前缀限定作用域，仅影响简报中心区域
- **保留 morandi 作为全局基础**：侧边栏、搜索 Tab 等继续沿用 morandi 色系，仅在简报 Tab 内覆盖为 workbench 风格
- **CSS 优先级控制**：workbench 样式在 morandi 之后注入，利用层叠自然覆盖

## 目录结构

```
d:/Improve/Project/Python/IntelNexus/
├── shared/ui/styles.py              # [MODIFY] 新增 .bf-* workbench 主题样式块
├── src/ui/briefing_viewer.py        # [MODIFY] 删除 welcome 函数，改造 config 面板结构，更新 HTML 类名
├── intel-briefing/src/ui/i18n.py    # [MODIFY] 重写简报相关文案（去 emoji、去套话）
├── ui.py                            # [MODIFY] 移除 render_briefing_welcome() 调用
```

## 实现注意事项

- **作用域隔离**：所有新增 CSS 选择器以 `.bf-workbench` 为根容器限定，避免污染其他 Tab
- **兼容性**：Streamlit 组件（expander/button/selectbox）的内部 DOM 结构不可控，样式覆盖需用 `[data-testid]` 选择器并注意优先级
- **文案一致性**：中英文双语同步更新，保持语气一致（工具型、动词优先）
- **空状态处理**：数据源/订阅者为空时显示行动导向文案而非纯信息告知

## 设计风格：情报工作台（Intelligence Workbench）

参考 GitHub Issues 页面、Linear 编辑器、VS Code 侧边栏的工具型界面语言。核心特征是冷灰底色、清晰的功能分区、克制但有效的色彩编码。

## 页面规划（简报中心 Tab，共 1 页）

### Page 1: Briefing Center 主页面

#### Block 1 - 功能标签条式配置面板区（SOURCES）

页面顶部第一个功能区。白色卡片背景，左侧 4px 蓝色竖条标识。包含数据源管理的添加表单和列表展示。区块标题使用大写英文标签 "SOURCES" 加中文副标题的组合形式，无 emoji。

#### Block 2 - 功能标签条式配置面板区（SUBSCRIBERS）

紧接 SOURCES 下方，同样结构但左侧竖条为绿色（`#1A7F37`）。包含邮件设置、添加订阅者表单、订阅者列表管理。区块标签 "SUBSCRIBERS"。

#### Block 3 - 功能标签条式配置面板区（GENERATE）

操作触发区，左侧橙色竖条（`#BF8700`）。只包含一个全宽主操作按钮 "Generate Now"，视觉权重最高，作为整个配置流程的收口。

#### Block 4 - 结果输出区（OUTPUT）

无彩色竖条，纯白卡片。根据状态动态显示：预览模式展示 Markdown 内容 + MD/HTML 下载按钮；历史模式展示日期-组织名列表支持查看/删除；初始状态不显示或显示极简占位。

## Agent Extensions

### Skill

- **frontend-design**
- Purpose: 提供去 AI 味的设计指导原则，确保新设计方案避开模板化套路（暖奶油色、暗黑霓虹、报纸极简），打造有辨识度的情报工作台风格
- Expected outcome: 输出经过审美审视的设计决策，每个选择都有非默认的理由支撑

### Skill

- **humanizer**
- Purpose: 对更新后的 i18n 文案进行去 AI 味审查，检测并修正 inflated symbolism、promotional language、rule of three 等 AI 写作特征
- Expected output: 工具型的、动词优先的、无废话的中英文界面文案