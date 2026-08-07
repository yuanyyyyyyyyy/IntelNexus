---
name: intelnexus-tests-refresh
overview: 根据当前 IntelNexus 项目代码，重新校准测试基线并补齐缺失功能测试，分批次分功能进行，确保 pytest 在正确 Python 环境下全部可运行。
todos:
  - id: batch0-env-baseline
    content: 校准测试环境并用 conda base 复核现有 112 用例全部通过，标记运行命令
    status: completed
  - id: batch1-search
    content: 新增 test_web_search.py 与扩充 test_news_rss_retry.py，覆盖网页检索与新闻分支
    status: completed
    dependencies:
      - batch0-env-baseline
  - id: batch2-scraper
    content: 新增 test_scraper.py，覆盖缓存命中、PDF 跳过与超长截断逻辑
    status: completed
    dependencies:
      - batch0-env-baseline
  - id: batch3-analysis-graph
    content: 新增 test_intelligence_graph.py，覆盖实体抽取降级与知识图谱计算导出
    status: completed
    dependencies:
      - batch0-env-baseline
  - id: batch4-export
    content: 新增 test_export_report.py，覆盖 md/pdf/word/excel 导出与格式探测
    status: completed
    dependencies:
      - batch0-env-baseline
  - id: batch5-darkweb-config
    content: 新增 test_darkweb.py、test_subscriptions.py、test_briefing_history.py，覆盖暗网与配置层
    status: completed
    dependencies:
      - batch0-env-baseline
  - id: batch6-final-verify
    content: 分批次运行全部 pytest，确认无失败并完成统一验证报告
    status: completed
    dependencies:
      - batch1-search
      - batch2-scraper
      - batch3-analysis-graph
      - batch4-export
      - batch5-darkweb-config
---

## 用户需求

根据当前 IntelNexus 项目重新更新并全面测试，要求分批次、分功能地执行测试。

## 产品概述

IntelNexus 是一个 AI 驱动的多源网络情报分析平台（Python 项目，根目录 d:/Improve/Project/Python/IntelNexus）。包含多源搜索（网页/新闻/暗网）、LLM 分析与报告生成、可信度评估、知识图谱、证据链溯源、AI 简报系统等核心能力。

## 核心特性（测试覆盖目标）

- 搜索层：网页多引擎检索（query 拆分、去重、域名黑名单、相关性过滤）、新闻 RSS 重试、网页内容抓取（缓存/PDF/截断）
- 分析层：来源可信度评分、跨源一致性、冲突检测、证据链溯源、知识图谱（实体抽取+图计算+导出）
- 导出层：Markdown / PDF / Word / Excel 多格式报告导出
- 暗网层：可用性开关、结果聚合、URL 编码、自定义 .onion 站点
- 简报层：采集→分析→推送流水线、订阅者管理、简报历史、进度回调、推送隔离
- 安全与结构：XSS 转义、路径穿越防护、API Key 传递、子项目拆分结构

## 技术栈

- 语言：Python 3.12（conda base 环境 `D:\Tool\Develop\anaconda3\python.exe`，pytest 7.4.4）
- 测试框架：pytest + unittest.mock（patch / MagicMock）
- 现有开发依赖：requirements-dev.txt 仅含 pytest（需补充 pytest 说明，不引入新框架）
- 外部重依赖（sentence-transformers / spacy / requests / reportlab / python-docx / openpyxl）一律 mock，保证离线、快速、确定性

## 实现方法

采用「分批次、分功能」策略，在现有 9 个测试文件（112 用例已通过）基础上，按模块增量补充单元测试，不改动业务代码（除非发现真实 bug）。每批聚焦一个功能域，独立可运行验证。

关键技术决策：

1. **复用现有 conftest 与薄包装机制**：`src.analysis.credibility` 等是 thin wrapper（exec_module 加载 intel-search 真实实现），patch 目标用 `src.analysis.credibility.load_sentence_model` 路径已被验证有效，新测试沿用此模式。
2. **mock 外部依赖**，不触发真实网络 / LLM / 模型加载：search/web、news、scraper、darkweb 的 requests 调用一律 mock；report 的 reportlab/docx/openpyxl 真实可用（conda 环境已装），PDF/Word 用最小内容验证文件生成与关键文本。
3. **环境隔离**：所有新增测试在 conda base python 3.12 运行；通过临时目录（tmp_path）隔离文件写入，避免污染 data/。
4. **性能**：sentence-transformers/spacy 在 import 阶段由薄包装触发，单测用 mock model 规避真实加载；分批运行避免一次性长耗时。

## 实现要点（执行细节）

- **不破坏现有测试**：新增文件命名为 `test_<module>.py`，与现有命名规范一致；补强现有文件时只新增用例，不改已有断言。
- **mock 路径精确**：darkweb 真实实现在 `intel-search/src/search/darkweb.py`，经 `src.search.darkweb` 薄包装暴露；测试从 `src.search.darkweb` 导入并 patch `requests.get` 等。
- **订阅/简报历史**：`subscriptions.py` / `briefing_history.py` 写真实 data/ 文件，测试用 tmp_path / monkeypatch 重定向 SUBSCRIPTIONS_FILE、storage_dir，避免污染。
- **日志与告警**：复用 `shared.logger`；测试不校验日志内容，只校验行为（返回结构、文件存在、防穿越返回 None/False）。
- **爆破半径控制**：仅新增/扩充 tests/ 下文件；若发现业务 bug 先做最小修复并在计划中标注，先征得确认再改（本计划默认不改业务代码）。

## 架构设计

现有测试分层与代码模块一一对应：

- 搜索层 → shared/search/*（web / news / scraper）
- 分析层 → intel-search/src/analysis/*（credibility / evidence_tracer / intelligence_graph）
- 导出层 → intel-search/src/export/report.py
- 暗网层 → intel-search/src/search/darkweb.py
- 简报层 → intel-briefing/ai_briefing/ *+ intel-briefing/src/config/*
- 安全/结构 → 跨模块静态校验

新增测试沿用此映射，统一放根 tests/ 目录，由 conftest.py 提供 path 注入与公共 fixtures。

## 目录结构（仅测试侧变动）

```
tests/
├── conftest.py                 # [MODIFY] 补充 tmp_path 重定向 helper fixtures（可选），保持现有 fixtures 不变
├── test_credibility.py         # [EXISTING] 保持，112 基线一部分
├── test_evidence_tracer.py     # [EXISTING] 保持
├── test_refine_query.py        # [EXISTING] 保持
├── test_security.py            # [EXISTING] 保持（含 darkweb quote、history 防穿越）
├── test_project_split.py       # [EXISTING] 保持（结构校验）
├── test_news_rss_retry.py      # [EXISTING] 保持，并补充 search_newsapi / 代理跳过分支用例
├── test_pipeline.py            # [EXISTING] 保持
├── test_briefing_pipeline.py   # [EXISTING] 保持
├── test_web_search.py          # [NEW] web.py：query 拆分(|)、_dedup_results、is_blocked_domain、relevance_passes、get_web_results 各引擎 mock
├── test_scraper.py             # [NEW] scraper.py：缓存命中、PDF 跳过、超长截断、scrape_multiple 并发聚合
├── test_intelligence_graph.py  # [NEW] intelligence_graph.py：EntityExtractor 降级/extract、IntelligenceGraph build/centrality/communities/export_html/to_dict/空图
├── test_export_report.py       # [NEW] export/report.py：md/pdf/word/excel 各格式生成、get_export_formats、内容校验
├── test_darkweb.py             # [NEW] darkweb.py：is_available、ENABLE_DARKWEB=false→[]、get_darkweb_results 聚合、quote URL 编码、自定义站点
├── test_subscriptions.py       # [NEW] subscriptions.py：增删改查、get_active_subscribers 过滤、update_last_sent
└── test_briefing_history.py    # [NEW] briefing_history.py：save/load/delete、路径穿越防护、历史列表
```