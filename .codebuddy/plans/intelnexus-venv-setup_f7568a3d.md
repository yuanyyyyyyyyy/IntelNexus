---
name: intelnexus-venv-setup
overview: 为 IntelNexus 在项目内创建独立 venv（不再使用 conda base），锁死 numpy<2 防止 SciPy ABI 冲突复发，下载 spaCy 模型，并配好一键启动脚本免去手动激活。
todos:
  - id: pin-numpy
    content: 在两个 requirements 文件中将 numpy 约束收紧为 <2
    status: completed
  - id: create-venv
    content: 创建 .venv 并安装运行与开发依赖
    status: completed
    dependencies:
      - pin-numpy
  - id: download-spacy
    content: 在 venv 中下载 spaCy 中英文模型
    status: completed
    dependencies:
      - create-venv
  - id: launcher-scripts
    content: 创建一键启动脚本并更新 README 文档
    status: completed
    dependencies:
      - create-venv
  - id: verify-env
    content: 验证环境与启动冒烟测试
    status: completed
    dependencies:
      - download-spacy
      - launcher-scripts
---

## 用户需求

用户不想再用 conda base 环境启动 IntelNexus，希望为项目建立独立隔离环境，并提供一键启动方式，免去每次手动激活的麻烦。

## 产品概述

为 IntelNexus 项目在根目录创建独立的 Python 虚拟环境（`.venv`），从依赖层面锁定 `numpy<2` 以根除 SciPy/NumPy ABI 冲突的复发风险，安装全部运行与开发依赖并补全 spaCy 模型，最后提供双击即用的启动脚本，彻底摆脱手动激活。

## 核心功能

- 在项目根目录创建 `.venv` 隔离环境（复用系统现有 Python 3.12，无需额外下载）
- 锁定 numpy 版本上限 `<2`，从依赖声明层根除 SciPy 兼容崩溃
- 安装运行依赖与开发依赖，并下载 spaCy 中英文模型（`en_core_web_sm` / `zh_core_web_sm`）
- 提供一键启动脚本，直接调用 venv 的 `python.exe`，无需手动 activate
- 更新 README 文档，反映新的环境搭建与启动方式

## 技术栈选择

- 环境隔离：Python 标准库 `venv`（复用现有 3.12 解释器，零额外下载，最轻量）
- 依赖管理：`pip`（随 venv 自带）+ 现有 `requirements.txt` / `requirements-dev.txt`
- 启动脚本：Windows 批处理 `.bat`（双击即可运行，无需终端手动激活）
- 模型补全：spaCy CLI `python -m spacy download`

## 实现方案

**策略**：用 `python -m venv .venv` 在仓库根目录建立隔离环境；升级 pip 后安装运行与开发依赖；下载 spaCy 模型；编写 `run.bat` 直接以 `.venv\Scripts\python.exe` 启动 `main.py`，从而完全跳过 activate 步骤。

**关键决策与权衡**：

1. **为什么用 venv 而非 conda 环境**：用户已选择 venv，且它复用现有 3.12、不污染 base、无需额外下载 Python，最贴合“轻量+免激活”诉求。
2. **为什么在依赖层锁定 `numpy<2`**：根因是 SciPy（sentence-transformers 的传递依赖）按 NumPy 1.x ABI 编译，在 NumPy 2.x 下 `numpy.core.multiarray failed to import`。仅凭 base 手动降级是临时措施，新环境必须在 `requirements.txt` 与 `intel-search/requirements.txt` 两处都加 `<2` 上限，才能永久防止 pip 解析到 2.x 而复发。下界 `>=1.24.0` 保持不变，向后兼容。
3. **为什么 launcher 直接调 `python.exe` 而不 activate**：`%~dp0.venv\Scripts\python.exe main.py %*` 可直接定位 venv 解释器并透传命令行参数（如 `run ui` / `run search -q ...`），双击即跑，彻底解决“每次激活好烦”。

**性能与可靠性**：`sentence-transformers` 会拉取 `torch` 等大型包，pip 安装是一次性耗时瓶颈（数分钟），无法避免但只需执行一次；可在脚本中先 `pip install --upgrade pip` 提速。安装顺序：先锁 numpy 约束再安装，确保解析结果正确。spaCy 模型下载约数十 MB，仅首次需要。

**避免技术债**：复用现有 `requirements.txt` 结构，仅收紧版本上限；`.gitignore` 已含 `.venv/`，无需改动；README 仅增量更新，不重构。

## 实现注意事项

- **两处都要改**：`requirements.txt` 第 34 行与 `intel-search/requirements.txt` 第 19 行均为 `numpy>=1.24.0`，必须同时加 `<2` 上限，否则 intel-search 子项目仍可能解析到 2.x。
- **venv 创建命令**：`python -m venv .venv`（使用当前 3.12 解释器）；Windows 下 venv 默认行为即可，无需 `--copies`。
- **spaCy 模型必装**：`intel-search/src/analysis/intelligence_graph.py` 第 123/129 行会 `spacy.load('zh_core_web_sm'/'en_core_web_sm')`，缺模型会在首次使用知识图谱时崩溃，安装后务必执行 `python -m spacy download en_core_web_sm zh_core_web_sm`。
- **爆炸半径控制**：仅收紧 numpy 下界以上限，不改动其他依赖；新建 `.bat` 与 `.venv` 均为新增/被忽略项，不影响现有代码与 git 跟踪。

## 架构设计

本任务为环境/脚本层改造，不涉及应用架构变动。数据流简化为：
`run.bat → .venv\Scripts\python.exe main.py <子命令> → 现有 IntelNexus 代码（import numpy/scipy/spacy 均来自 venv）`。
环境层与原代码完全解耦，后续可随时重建 `.venv` 而不影响源码。

## 目录结构

```
IntelNexus/
├── requirements.txt              # [MODIFY] 第34行 numpy>=1.24.0 改为 numpy>=1.24.0,<2，锁定版本上限防复发
├── intel-search/requirements.txt # [MODIFY] 第19行 numpy>=1.24.0 改为 numpy>=1.24.0,<2，与根依赖保持一致
├── run.bat                       # [NEW] 一键启动脚本，直接调用 .venv 的 python.exe 并透传参数（run ui / run search -q "..." 等）
├── setup.bat                     # [NEW] 环境初始化脚本：建 .venv、升级 pip、装依赖、下载 spaCy 模型，可重复执行
└── README.md                     # [MODIFY] 在“安装/使用”章节补充 venv 方案与 run.bat 一键启动说明
```

## 关键代码结构（可选）

`run.bat` 的核心逻辑（直接调用 venv 解释器，无需激活）：

```
@echo off
setlocal
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
```

`%~dp0` 确保无论从哪个目录双击，都能定位到项目根下的 venv 与 `main.py`。