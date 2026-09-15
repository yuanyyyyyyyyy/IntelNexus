# 论文 A 实验管线

把论文里 196 处 `not-yet-measured` 变成**可追溯的实测值**。
全流程脚本化，任何一步都能单独重跑；没有实测支撑的格子永远是占位，不会被"填平"。

## 一、准备

```powershell
# 1) 依赖（在仓库根目录的虚拟环境中）
.venv\Scripts\python.exe -m pip install -r requirements-extras.txt

# 2) 本地模型（另开一个终端保持运行）
ollama serve
ollama pull qwen2.5:7b
ollama pull mistral:7b
# qwen3:8b 本机已有，无需拉取

# 3) 云端密钥（只走环境变量，绝不写入配置文件或日志）
$env:DASHSCOPE_API_KEY = "sk-..."        # 阿里云百炼（qwen，首选）
$env:DEEPSEEK_API_KEY  = "sk-..."        # 可选：敏感性对照

# 4) 如 BERTScore 模型下载困难（国内）
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

## 二、标准流程

```powershell
.venv\Scripts\python.exe -m experiments.cli env          # G0 环境探测
.venv\Scripts\python.exe -m experiments.cli probe-chat   # 云端连通性探针（跑批前必做）
.venv\Scripts\python.exe -m experiments.cli collect      # G1 数据快照（只采一次）
.venv\Scripts\python.exe -m experiments.cli run smoke    # G2 冒烟
.venv\Scripts\python.exe -m experiments.cli run pilot --repeats 2   # G3 试点
.venv\Scripts\python.exe -m experiments.cli run full     # G4 全量（耗时最长）
.venv\Scripts\python.exe -m experiments.cli aggregate
.venv\Scripts\python.exe -m experiments.cli privacy --sample-n 20   # 表6 出域测量
.venv\Scripts\python.exe -m experiments.cli scan                    # 表6 明文残留
.venv\Scripts\python.exe -m experiments.cli figure                  # 图3
.venv\Scripts\python.exe -m experiments.cli scan-slots
.venv\Scripts\python.exe -m experiments.cli gen-mapping
.venv\Scripts\python.exe -m experiments.cli fill
.venv\Scripts\python.exe -m experiments.cli verify
```

回填产物在 `_build/content_filled/`，**原稿不动**；随后用
`build_docx.py build`（把 `CONTENT_DIR` 指向 `content_filled/`）重出 docx。

## 三、人工评分

```powershell
.venv\Scripts\python.exe -m experiments.cli human-sheet --out experiments/reports/human_eval_sheet.csv
# 评审人填写 factuality / completeness / usability（5 分制）后：
.venv\Scripts\python.exe -m experiments.cli aggregate --human-csv experiments/reports/human_eval_sheet.csv
```

配置名在表中被匿名化为 A/B/C，映射存于同目录的 `*.mapping.json`。

## 四、产物清单

| 路径 | 内容 |
|---|---|
| `reports/env_report.json` | 环境探测（GPU/Ollama/云端/抓包/信源） |
| `reports/probe_chat.json` | 云端连通性与耗时探针 |
| `data/snapshot/items.jsonl` | 数据快照 |
| `data/snapshot/dataset_stats.json` | 表1 与 R1 归档物 |
| `data/snapshot/manifest.sha256` | 哈希清单 |
| `runs/<run_id>/manifest.json` | 单次运行的可追溯要素（含 valid/failed 计数与参数覆盖） |
| `runs/<run_id>/records.jsonl` | 逐条时延、token、错误 |
| `reports/metrics_long.jsonl` | 逐条质量指标 |
| `reports/aggregate.json` | 表3/4/5/7 的唯一事实源 |
| `reports/privacy.json`、`privacy_scan.json` | 表6 |
| `reports/slots.json`、`mapping.yaml` | 占位槽位与指标绑定 |
| `reports/fill_report.json`、`verify_report.json` | 回填与反查结果 |
| `figures/fig3_pareto.png` | 图3 |

## 五、测试

```powershell
.venv\Scripts\python.exe -m pytest tests/test_exp_*.py -q
```

全部用例离线可跑（不依赖 Ollama、云端 API 与网络）。

## 六、已知必须先做的事

1. `configs/pricing.yaml` 的云端单价与本地折算参数为空 —— 填好前表5 全部占位。
2. 本机显存 6 GB，`num_ctx` 已收紧到 8192；若换机需重跑 `env` 并核对。
3. Ollama 服务未随系统启动，跑实验前确认 `ollama serve` 在运行。
4. 本地组当前配置为 `qwen3:8b`（本机已有）、`qwen2.5:7b`、`mistral:7b`（后两个需 `ollama pull`）；
   未拉取的模型会在 smoke 阶段被如实记为失败，不会静默通过。

## 七、排障

**云端全部超时**：先跑最小请求探针定位，再决定调超时、限输出长度还是换档位。

```powershell
.venv\Scripts\python.exe -m experiments.cli probe-chat                     # 非流式
.venv\Scripts\python.exe -m experiments.cli probe-chat --full-input         # 真实输入长度
.venv\Scripts\python.exe -m experiments.cli probe-chat --stream --full-input  # 流式：测 TTFT 与最大静默
```

判读：
- 短 prompt 也超时 → 网络或代理问题（检查 `HTTP_PROXY`/`HTTPS_PROXY`）；
- 流式的**最大静默间隔**接近 `request_timeout` → 推理型模型思考阶段不发分块，
  在 `experiment.yaml` 的 `cloud` 段设 `streaming: false`；
- 总耗时接近超时 → 设 `max_tokens` 限制输出，或上调 `request_timeout`。

以上覆盖都会写入 `run_manifest.param_overrides`，论文须说明。

**本地显存不足（单条过慢）**：先做驻留体检，再决定是拉小模型还是缩规模。

```powershell
.venv\Scripts\python.exe -m experiments.cli residency --ctx 4096,2048 --items 2
```

判读：`gpu_share ≥ 0.95` 且单条 ≤ 90 s 为 `full-ok`；否则为 `degrade-required`，
按输出建议处理（关闭占显存程序 / `ollama pull qwen3:4b` / 缩减 full 规模）。
判定阈值写死在 `local_residency.py`，不接受事后调整。

**日志显示"失败 0"但结果为空**：`generate_summary` 吞掉异常返回错误模板，
管线已用 `instrument.is_error_template` 识别并记为失败；若仍出现，检查
`ERROR_MARKERS` 是否覆盖了新模板文本。

**云端报 `Missing credentials` 或"全部超时"**：检查 `instrument._model_fields`
是否仍保留 pydantic 别名。`ChatOpenAI` 的字段真名是 `openai_api_key` /
`openai_api_base` / `request_timeout`，`api_key` / `base_url` / `timeout` 只是别名；
若按字段名过滤就会把凭据与 base_url 丢掉，请求会打到默认的 `api.openai.com`
（国内不可达）并挂到读超时。自检：

```powershell
.venv\Scripts\python.exe -c "from langchain_openai import ChatOpenAI; from experiments.harness.instrument import _filter_params; k,d=_filter_params(ChatOpenAI,{'api_key':'k','base_url':'u'});print(k,d)"
```

应输出 `{'api_key': 'k', 'base_url': 'u'} []`。
