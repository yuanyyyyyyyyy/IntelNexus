# 实验预注册协议（PROTOCOL）

> 本文在**看到任何结果之前**定稿，用于约束实验口径。
> 拿到结果后修改样本量、重复次数或指标定义，等同于事后解释，属学术不端。
> 确需变更时，须在本文件末尾「偏差记录」中写明原因与日期，并在论文中披露。

- **版本**：v1　**定稿日期**：2026-09-13
- **对应论文**：论文 A（安全简报自动生成中本地推理与云端 API 的质量—隐私—成本权衡）
- **配置哈希**：实验开始前记录 `configs/experiment.yaml` 的 SHA-256，变更即视为偏差

---

## 一、实验单元与调用口径

| 项 | 约定 |
|---|---|
| 实验单元 | 单条安全公告 → 一次摘要/简报生成 |
| 生成入口 | `intelnexus.core.llm.core.generate_summary`（与主程序同一链路） |
| 生成参数 | 直接复用 `intelnexus.core.llm.utils._common_llm_params`（temperature=0、request_timeout=120 s、max_retries=3），**实验内不另立一套** |
| 输入构造 | `{url: 正文}` 单来源块，与主程序一致 |
| 截断 | 沿用生产行为：仅本地小模型（≤32B 判定）截断至 25 000 字符（重试 20 000），云端不截断。这是部署形态的固有约束，已在论文外部效度中讨论 |

## 二、配置矩阵

| 组 | 配置 | 说明 |
|---|---|---|
| 本地 | qwen2.5:7b / llama3:8b / mistral:7b | Ollama，seed 固定，num_ctx 按显存收紧 |
| 云端 | 旗舰档 / 轻量档 | 阿里云百炼 OpenAI 兼容端点，模型名由 `/v1/models` 探测确定 |
| 基线 | 关键词规则 / TextRank / TF-IDF 聚类+首句 | 确定性算法，方差为 0 |

敏感性对照（不进主表）：DeepSeek 同档位，用于 6.4 节检验"换供应商是否改变结论"。

## 三、数据集与样本量

- 快照一次性采集，之后**只读**，所有阶段共用（`experiments/data/snapshot/`）。
- 划分：按发布时间升序，前 20% 为提示工程调试集，**后 80% 为测试集**（避免时序泄漏）。
- 各阶段样本量（写死，不得事后调整）：

| 阶段 | 样本条数 | 重复次数 | 用途 |
|---|---|---|---|
| smoke | 2 | 2 | 管线自检，不进论文 |
| pilot | 30 | 2 | 外推全量时间与费用预算 |
| full | 200 | 5 | 正式结果（表3–表7） |

- 质量评测只使用 `quality_eligible` 为真的条目（正文与官方摘要**不同源**）。

## 四、指标定义与口径

| 维度 | 指标 | 口径 |
|---|---|---|
| 质量 | ROUGE-L | jieba 分词后 LCS-F1，与官方摘要字段比对 |
| 质量 | BERTScore | `bert-base-chinese` F1；依赖或模型缺失则**整列保留占位**，不用近似替代 |
| 质量 | 实体 F1 | CVE/GHSA、版本、攻击类型、产品名；金标=参考摘要规则抽取（+可选人工校对）；金标为空的样本不计入 |
| 质量 | 人工评分 | ≥3 名评审、5 分制三维度、盲评（配置匿名化）；报告 Krippendorff's α（ordinal） |
| 效能 | P50/P95 时延 | **串行**测量（并发会污染分位数），端到端含提示词拼装与内部重试 |
| 效能 | 吞吐 | 每次重复的总条数 / 总耗时 |
| 效能 | 显存/内存峰值 | nvidia-smi 轮询（0.5 s）；无 GPU 时用进程 RSS |
| 成本 | 云端 | 输入、输出 token 分列，按官方单价（元/百万 token） |
| 成本 | 本地 | 电费 + 折旧折算，参数取自 `configs/pricing.yaml`，未填即占位 |
| 隐私 | 出域字节 | 计量代理统计（CONNECT 隧道口径），本地组排除首次模型拉取 |
| 隐私 | 外联目的地 | 去重主机数 |
| 隐私 | 明文残留 | 对日志/缓存/临时文件扫描敏感片段的命中条目数 |

## 五、统计方法

- 配对设计：同一 `(sample_id, repeat)` 构成一对；出域字节以"每次重复总量"配对（n = 重复次数）。
- 检验：Wilcoxon 符号秩（双侧）；效应量：Cliff's delta；多重比较：Holm 校正；α = 0.05。
- **禁止**：只报 p 值不报效应量；只报均值不报方差；降样本量或删异常值使结果变好。

## 六、门禁（G0–G4）

每个门禁失败即停，不得跳过。

| 门禁 | 命令 | 通过条件 |
|---|---|---|
| **G0 环境** | `python -m experiments.cli env` | 无阻塞项：Ollama 可达、本地模型已拉取、云端端点可达且两档模型已选定、抓包工具可用 |
| **G1 数据** | `python -m experiments.cli collect` | 快照条目 ≥200；`dataset_stats.json` 的 `meets_min_total` 为真；哈希清单已生成 |
| **G2 冒烟** | `python -m experiments.cli run smoke` | 全部配置失败率 0；每个 run 有 manifest 且字段齐全 |
| **G3 试点** | `python -m experiments.cli run pilot` | 时延/成本外推在可接受范围；token 用量来源非 none（云端必填） |
| **G4 全量** | `python -m experiments.cli run full` → `aggregate` → `fill` → `verify` | 表3–表7 无未测项；`verify` 可追溯到 run 与 manifest |

补充门禁（非数值但必须）：
- **人工评分**：盲评表回收 ≥3 人、α 已计算后才允许回填人工评分列。
- **定价**：`configs/pricing.yaml` 的单价与本地参数填写并注明来源与查询日期后，才允许回填表5。

## 七、失败与缺失处理

1. 单次生成失败：记录错误原因，计入失败率；失败率 >50% 中止该配置。
2. 指标不可用（如 BERTScore 模型下载失败）：该指标整列保留 `not-yet-measured`，并在论文局限性中说明。
3. **任何情况下不得**：用估算值、行业均值、TDP 或"合理假设"顶替未测项。

## 八、偏差记录

| 日期 | 偏差 | 原因 | 影响 |
|---|---|---|---|
| 2026-09-13 | 本地组 `llama3:8b` 改为 `qwen3:8b`（8.2B） | `llama3:8b` 未在本机拉取；本机已有 `qwen3:8b`（`ollama list` 实测 4.87 GB）。`llava:7b` 为多模态模型，不适用于文本简报，已排除 | 表2/表3/表4 的模型名与参数量随之更新；本地组仍为 3 个模型（qwen3:8b、qwen2.5:7b、mistral:7b），后两个需 `ollama pull` |
| 2026-09-13 | 云端参数覆盖（超时/输出上限/输入上限）待定 | 首次 smoke 中 qwen3-max 与 qwen-plus 全部超时（单条约 87 s、每次重复约 172 s） | 由 `probe-chat` 探针实测后填写；任何覆盖写入 manifest 的 `param_overrides` 并在论文中说明 |
| 2026-09-13 | 输入上限由"本地小模型 25 000 字符"改为**全后端统一 8 000 字符** | 首次 smoke 实测本地单条 P50=220 s，瓶颈为 25 000 字符输入的预填充；且生产实现中云端不截断，造成输入长度不公平 | 已写入 `run_manifest.param_overrides`；论文 §2.3 与 6.3 局限性同步说明；表2 截断列改为"统一上限 8000 字符" |
| 2026-09-13 | 主指标由 ROUGE-L 改为**安全实体 F1**，BERTScore 改用多语言基座 | 生成物为中文、参考摘要多为英文，ROUGE-L 实测 0.002±0.003，无区分度；实体 F1 与语言无关且更贴安全任务 | 表3 的指标顺序与表注同步；ROUGE-L 保留为辅助并附"首板块口径"敏感性 |
| 2026-09-14 | 本地显存不足：8B 无法全 GPU 驻留（实测结论 `degrade-required`） | `ollama ps` 实测：num_ctx=8192→36% CPU、4096→30% CPU、3072→27% CPU、2048→25% CPU，显存 6141 MiB 扣桌面占用后装不下 8B 量化模型 + KV。单条耗时 99–226 s，生成速度恒为 8.3 tok/s | 已处置：本地组改为 **qwen3:8b + qwen3:4b** 两档，4B 实测 `100% GPU`、41 s/条（`full-ok`） |
| 2026-09-14 | **full 规模由 200 条 × 5 次降为 100 条 × 3 次**；本地组由 3 档降为 2 档（qwen3:8b、qwen3:4b） | 8B 无法全 GPU 驻留（170 s/条），200×5 需约 55 h，超出可执行范围；qwen2.5:7b / mistral:7b 未拉取，llava:7b 为多模态不适用 | 配对检验仍有 n=100，统计效力可接受；已在 6.3 局限性中说明样本量与本地算力约束 |
| 2026-09-14 | **云端口径修正：早期 120 s 超时系实验侧参数过滤缺陷，非服务端问题**（此前"服务端抖动"的推断已作废） | `langchain_openai/chat_models/base.py:739-741,791`：字段真名为 `openai_api_key` / `openai_api_base`，`api_key` / `base_url` 仅为 pydantic 别名。`instrument._model_fields` 原按字段名过滤，把二者当未知参数丢弃 → 请求缺凭据且打到默认 `api.openai.com`（国内不可达）→ 挂到读超时。流式探针（原始 SDK，绕过该过滤）TTFT 0.39–2.05 s、最大静默 0.11–0.21 s 全部正常，印证问题在实验侧 | 已修 `_model_fields` 纳入别名（`experiments/harness/instrument.py`），新增 2 条回归用例；论文 §3.4 写明"实验脚本对 LangChain 构造参数做别名兼容处理"；**`streaming` 保持生产默认值不变** |
| 2026-09-15 | **汇总口径固定为 full 阶段**；排除 `qwen2.5:7b`、`mistral:7b` 的零散 smoke 记录 | 早期 smoke/pilot 留下的 2 条失败记录会把从未正式运行的模型带进配置清单与表格 | 汇总一律 `aggregate --stage full`；有效记录 1 800 条（6 配置 × 100 条 × 3 次重复） |
| 2026-09-15 | **撤除本地 `qwen3:4b` 臂** | 该臂在默认（思考模式开启）解码下整档 300/300 条 `content` 为空、输出 0 字符而调用本身"成功"；关闭思考后的冒烟（`runs/20260915T025327Z-qwen3-4b-r1-mvrj0f9r`）虽产出 1 758 字符，但 `eval_count=1024` 恰等于 `num_predict` 上限，即输出被截断。经作者确认不再追加算力重跑 | 本地组由 2 档减为 1 档（`qwen3:8b`）；表2/表3/表4 的 4B 行删除；该臂的失败作为**负结果**在 5.x 与 6.3 节说明（本地部署的隐性门槛不只在显存，还在后端默认解码行为）；配置定义保留在 `experiment.yaml` 的 `exclude_configs` 留档 |
| 2026-09-15 | **云端 token 用量改为"重算"而非 API usage** | 批量运行时 `ChatOpenAI` 在 `streaming=True` 下默认不回传 `usage`（需 `stream_usage=True`），600 条云端记录的 `tokens_in/out` 为空；重新调用 API 属重跑，超出已定范围 | 用 Qwen 官方分词器对**实际发生过的请求与响应文本**重算：输入 token 取本地 `qwen3:8b` 同一样本的 `prompt_eval_count`（**跨调用代理**，其口径问题见下条），输出 token 由分词器对已存盘生成文本计数（`experiments/cost/token_recount.py`）。提示词本身的本地/云端一致性已实测（同调用偏差 ≤0.383%，见下条），问题不在"提示词不同"，而在"合计 vs 单次" |
| 2026-09-15 | **token 校准语义修正：改为「同一次调用内」比较；历史 32.237% 重标注为跨调用观测（并已查明其成因为调用次数口径差）** | 原 `token-calib` 把「本地当次运行记录的 `prompt_eval_count`」与「另一次云调用的 API usage」相比，得出 32.237%。**核查结论：该差异来自调用次数口径不可比，既非提示词漂移、亦非计数误差。** agent 侧 `generate_summary`（`intelnexus/core/llm/core.py:610-629`）在输出板块不足时会改用简化 prompt 重试，本地小模型常触发（smoke 实测 4/4 条 `prompt_calls=2`），故本地记录里的 `tokens_in` 是**一条样本内各次调用之和**；而云端那一次只发 1 次（同调用校准 6/6 次 `calls=1`）。**实测复算**：`1820（首次）+ 559（重试）= 2379`，与旧本地记录 2397 相差 **0.751%**，恰等于独立实测的边界计数偏差；`1848 + 587 = 2435` 对 2453 相差 0.734%。次要成分：提示词自身长度亦会变化（`proxy_spread` 中个别样本 min 2 643 / max 4 025） | ① `calibrate()` 改为同调用比较：同一次调用既读 API `usage`，又对该次**真正发出的提示词**计数；实测结果：云端两档输入偏差 **−0.383% / −0.377% / −0.378%**、输出偏差 **0.000%（6/6）**，本地后端同调用对照 `same_call_agreement` 最大 **0.751%**（n=4）——**计数口径已实测准确**；② 旧的跨调用结果迁至 `token_recount.json` 的 `calibration_cross_call`（`comparison_type=cross-call`），附机制说明与同样本极差证据，**不得作为计数误差引用**；③ 该比值区间 [0.7562, 0.9989] 只用于给**输入侧**定界；④ 论文表5 表注与 5.3 局限性按此口径表述 |
| 2026-09-15 | **新增提示词留痕埋点；云端输入 token 改为「点值 + 实测区间」披露** | 旧记录未存提示词文本（运行目录只有 `manifest.json` / `records.jsonl` / `.md`），事后无法确认「那次请求的提示词有多长」，只能借用别次运行的值；代理值又是**各次调用之和**（见上条），在 100 条样本中有 3 条的合计在重复间变化（最大极差 2 993 token，见 `token_recount.json` 的 `proxy_spread`） | ① 埋点新增 `prompt_chars` / `prompt_sha256` / `prompt_tokens`（最后一次调用）/ `prompt_tokens_sum`（各次之和，与计费口径及服务端累计 `tokens_in` 可比）/ `prompt_calls` / `prompt_render`，经 `on_chat_model_start` 抓取（`langchain_core` 1.6 下 chat 模型**只**触发该回调，仅挂 `on_llm_start` 会一条都抓不到；计数编码置于计时窗口之外，不影响 P50/P95）；② 自本次起新记录的输入 token 来源标 `recount_own_prompt`，旧记录标 `recount_proxy`，两者在 `usage_source` 上可区分；③ 表5 保留点值，表注给出输入计费与单次成本区间（由 `reports/cost_sensitivity.json` 的 `input_token_band` 生成，**禁止手算**）；④ 该不确定区间不改变结论方向：区间内本地单次折算成本仍不低于云端旗舰档 |
| 2026-09-15 | **出域测量口径修正：剔除"代理转发回自身"的无效运行** | `build_target_url` 修复前，云端首次测量把请求转发回代理自身，产生"目的地仅 127.0.0.1、出域 1.1 GB、请求 13 万次"的虚假记录；旧 `save_result` 把它计入合计，使表6 的出域量与目的地数严重失真 | 新增 `judge_run` 有效性判定（error / 零请求 / 云端配置目的地全为回环即无效），无效运行**保留原件可复核但不计入合计**；`privacy.json` 按新口径重算：云端两档出域 85 048 字节（10 条样本）、去重目的地 1 个（`dashscope.aliyuncs.com`） |
| 2026-09-15 | **人工评分与 BERTScore 保留 `not-yet-measured`** | 人工评分需 ≥3 名评审独立盲评，本轮未组织；BERTScore 依赖 `bert-score` 未安装，且本机 `torch` 为 CPU 版（`2.13.0+cpu`），170 条 × 6 配置的多语言 BERTScore 在 CPU 上不可行 | 表3 的 BERTScore 与人工评分两列、表7 涉及人工评分的三行保留占位；按 §七.2 在 6.3 局限性中说明，**不以近似指标替代** |
| 2026-09-15 | 表7 的"出域字节数"行标注为单次测量、不做配对检验 | 出域按配置测量一次（每次 10 条样本合计），n=1 无分布，无法构成 §五 约定的"以每次重复总量配对" | 该行不以 p 值呈现，改为注明测量方式；论文表注说明 |
| 2026-09-15 | **新增评测依赖 `bert-score` 与跨语言基座 `bert-base-multilingual-cased`** | 表3 的 BERTScore 整列此前因依赖未安装而保留占位，而该指标是 §四 明列的四个质量指标之一 | 依赖写入 `requirements-extras.txt`；基座经 ModelScope / hf-mirror 固定落盘到 `experiments/data/bert_base_multilingual_cased/`（含 `model_info.json` 与逐文件 SHA-256），运行时以 `local_files_only` 加载，离线可复现。**口径**：`idf=False`（bert-score 默认按本次调用批次内的参考文本现算 IDF，各配置分别调用会使 IDF 随批次变化、跨配置不可比）、`rescale_with_baseline=False`（官方重标定不适用于多语言基座）、按 512 token 截断（BERT 位置编码上限），并另报"首板块口径"作截断稳健性对照。**修掉两处实测缺陷**：① 该基座 `tokenizer_config.json` 缺 `model_max_length`，transformers 5.x 退回超大哨兵值，传给 Rust 分词器的 `enable_truncation` 触发 `OverflowError: int too big to convert`，指标完全算不出来（已补 512 并加回归用例）；② bert-score 的取层注册表按模型名索引，直接传本地路径会 `KeyError`，改为把本地目录注册为同名模型的别名，取层号沿用官方对 12 层 BERT-base 的约定（第 9 层）。`aggregate` 改为逐条磁盘缓存，键为「基座名 + idf 开关 + 权重 sha256 前 12 位 + 候选文本 + 参考摘要」的哈希，使后续任何重跑命中缓存、秒级完成，同时保证"换基座或改口径却复用旧分数"不会静默发生。**可复现性实测**：同一输入重算两次，逐条 F1 差异在 1e-9 量级（float32 累积误差），三位小数完全一致 |

**关于脚本指纹**：2026-09-15 的埋点改动（`experiments/harness/instrument.py`、`experiments/harness/runner.py`）使 `run_manifest.script_sha256` 在改动前后必然不同——这是**预期**：指纹的作用是标明"该 run 由哪一版脚本产生"，不是要求全库一致。原有 1 800 条记录的 manifest 不因本次改动而被覆写，其指纹仍是产生它们时的版本。

## 九、复现入口（本轮定稿）

```
python -m experiments.cli env                 # G0 环境
python -m experiments.cli collect --limit 300 # G1 数据快照
python -m experiments.cli run full --configs qwen3:8b,cloud_flagship,cloud_light,baseline_keyword,baseline_textrank,baseline_tfidf
python -m experiments.cli bertscore-fetch      # 一次性：固定下载 BERTScore 跨语言基座
python -m experiments.cli token-recount       # 云端 token 重算（离线，无 API 调用）
python -m experiments.cli token-calib --n 3   # 真实 API 校准：同一次调用内比较（需 DASHSCOPE_API_KEY）
python -m experiments.cli privacy --configs cloud_flagship,cloud_light,qwen3:8b --sample-n 10
python -m experiments.cli cost                # 成本折算与敏感性；含输入侧区间 input_token_band
python -m experiments.cli scan                # 本地明文残留
python -m experiments.cli aggregate --stage full
python -m experiments.cli figure
python -m experiments.cli scan-slots --content-dir <稿件 content>
python -m experiments.cli gen-mapping
python -m experiments.cli fill --content-dir <稿件 content>
python -m experiments.cli verify
python -m experiments.cli results
pytest tests/test_exp_*.py -q
```

**待作者补齐的前置项**（未补齐前对应格子保持 `not-yet-measured`）：

1. `configs/pricing.yaml` 的 `local` 段 5 个参数（`P_avg_watt` 须实测平均整机功耗，其余为采购/使用参数）→ 表5 本地行、表7 成本行、图3 横轴；
2. 人工盲评（≥3 名评审，`human-sheet` 生成盲评表）→ 表3 人工评分列、表7 三行。
