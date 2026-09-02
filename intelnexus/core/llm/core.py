import re
import threading
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from intelnexus.core.llm.utils import _common_llm_params, resolve_model_config, get_model_choices

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 模块级 LLM 实例缓存（按 model_choice），避免每次搜索都重建模型连接
_llm_cache = {}
_llm_cache_lock = threading.Lock()

_ERROR_TEMPLATE_TIMEOUT = """## 一、执行摘要

报告生成请求超时，可能因网络延迟或模型响应过慢导致。

## 二、建议

1. 请检查网络连接状态
2. 尝试切换至其他可用的 AI 模型
3. 减少搜索范围后重试

## 三、错误详情

API 请求超时，模型未能在规定时间内返回结果。
"""

_ERROR_TEMPLATE_GENERIC = """## 一、执行摘要

报告生成过程中遇到错误。

## 二、错误信息

{error_msg}

## 三、建议

1. 请检查 API 密钥配置是否正确
2. 尝试切换至其他可用的 AI 模型
3. 检查 Ollama 服务是否正常运行（如使用本地模型）
"""


def get_llm(model_choice, use_cache=True):
    config = resolve_model_config(model_choice)

    if config is None:
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    if use_cache:
        with _llm_cache_lock:
            cached = _llm_cache.get(model_choice)
        if cached is not None:
            return cached

    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    all_params = {**_common_llm_params, **model_specific_params}

    llm_instance = llm_class(**all_params)

    if use_cache:
        with _llm_cache_lock:
            _llm_cache[model_choice] = llm_instance

    return llm_instance


def expand_query(user_input):
    """查询扩展 - 拼写修复 + 最多1个跨语言变体（避免请求爆炸）"""
    user_input = user_input.strip()

    common_typos = {
        "sarch": "search",
        "serach": "search",
        "seaech": "search",
        "reuslt": "result",
        "resutl": "result",
    }

    words = user_input.split()
    fixed_words = []
    for word in words:
        if word.lower() in common_typos:
            fixed_words.append(common_typos[word.lower()])
        else:
            fixed_words.append(word)

    original = " ".join(fixed_words)

    if len(original) < 3:
        return [original]

    queries = [original]

    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original)
    has_english = any('a' <= c.lower() <= 'z' for c in original)

    # Only add ONE cross-language variant to avoid search engine overload
    if has_chinese:
        queries.append(f"{original} English")
    elif has_english and len(original) >= 3:
        queries.append(f"{original} 中文")

    return queries


def expand_query_for_search(query_variants):
    """
    将查询变体扩展为搜索字符串。

    修正（方案B）：不再把多语言变体用 ``|`` 拼成 OR 查询一次性塞给搜索引擎。
    OR 拼接会稀释查询意图（如中文"九江" + "九江 English" 会拉回大量无关的英文全局新闻），
    "搜不准"的根因之一。

    改为：仅取第一个（最贴近原意的）变体作为搜索串，其余语言变体由管线层在
    聚合后再做语义排序/过滤处理。若传入单个字符串则原样返回。
    """
    if isinstance(query_variants, list):
        if not query_variants:
            return ""
        return query_variants[0]
    return query_variants


def _get_mode_description(search_mode):
    """Return a description string for the given search mode."""
    # 单一事实源：与 core.search.modes.MODE_DESCRIPTIONS 保持一致（此前本地副本漂移，
    # 缺 threat 条目导致威胁情报模式下 LLM 被告知"综合所有来源：网页、新闻、暗网"）
    try:
        from intelnexus.core.search.modes import MODE_DESCRIPTIONS
        return MODE_DESCRIPTIONS.get(search_mode, MODE_DESCRIPTIONS["all"])
    except ImportError:
        return "综合所有可用来源"


# ---------------------------------------------------------------------------
# 查询主题分类（方案 A：模板分层）
# 安全情报类查询沿用完整四维分析；非安全类（实体/城市/产品/人物等）
# 自动替换为自适应维度，避免"技术维度硬凑 VR 景区"式的模板错配。
_SECURITY_HINTS = (
    "漏洞", "攻击", "勒索", "恶意", "木马", "病毒", "钓鱼", "入侵", "渗透",
    "exploit", "ransomware", "malware", "apt", "cve", "0day", "zero-day",
    "数据泄露", "泄密", "暗网", "hacked", "breach", "botnet", "ddos",
    "网络攻击", "安全事件", "威胁情报", "后门", "挂马", "webshell",
)

# 否定词列表：用于过滤误判（如"没有漏洞"、"防范攻击"）
_NEGATION_WORDS = (
    "没有", "无", "非", "不", "未", "避免", "防范", "防止", "预防", "抵御",
    "no", "not", "without", "prevent", "avoid", "protect",
)

# 白名单：明确的非安全场景（即使包含安全关键词）
_GENERAL_WHITELIST = (
    "营销", "策略", "案例", "研究", "分析", "报告", "教程", "指南",
    "marketing", "strategy", "case study", "tutorial", "guide",
)


def classify_query_topic(query: str) -> str:
    """返回 'security' 或 'general'。规则匹配，零 LLM 开销。
    
    判断逻辑：
    1. 否定词过滤：如果包含否定词 + 安全关键词，判定为 general
       （如"没有漏洞"、"防范攻击"属于安全教育/讨论，不是安全事件）
    2. 白名单过滤：如果包含明确的非安全场景词，判定为 general
       （如"营销策略"、"案例研究"即使包含"攻击"也不是安全话题）
    3. 多关键词阈值：至少 2 个安全关键词才判定为 security
       （避免单关键词误判，如"攻击性营销"）
    4. 单关键词 + 极短查询：如果是极短查询（<=10字符），更可能是安全相关
    """
    if not query:
        return "general"
    
    q = query.lower()
    
    # 1. 否定词过滤
    has_negation = any(neg in q for neg in _NEGATION_WORDS)
    
    # 2. 白名单过滤
    has_whitelist = any(wl in q for wl in _GENERAL_WHITELIST)
    
    # 3. 统计安全关键词数量
    match_count = sum(1 for h in _SECURITY_HINTS if h in q)
    
    # 4. 综合判断
    if has_negation or has_whitelist:
        # 有否定词或白名单词，判定为 general
        return "general"
    elif match_count >= 2:
        # 至少 2 个安全关键词，判定为 security
        return "security"
    elif match_count == 1:
        # 单个关键词时，检查查询长度
        # 极短查询（<=10字符）更可能是安全相关，长查询更可能是综合讨论
        if len(q) <= 10:
            return "security"
        else:
            return "general"
    else:
        # 无安全关键词
        return "general"


_ADAPTIVE_DIMENSIONS = """
### 4.1 发展现状与格局
[该主体的当前状态、规模数据、行业地位、近期变化]

### 4.2 优势与挑战
[核心优势/竞争力；面临的问题、短板或争议]

### 4.3 相关方视角
[政府/监管态度、行业影响、公众关注点（仅当搜索结果有支撑时展开）]

### 4.5 发展趋势
[短期、中期、长期预测]
"""


def _build_system_prompt(query, search_mode):
    """统一的 LLM system prompt。

    不再区分 general/security 双模板，改为一个统一 prompt：
    - 4 个必选板块（所有查询都生成）
    - 3 个可选板块（LLM 根据话题自行判断是否生成）
    """
    mode_desc = _get_mode_description(search_mode)
    return f"""
你是一位高级信息分析师。基于以下搜索结果和分析数据，请生成一份分析报告的**核心分析板块**。

查询主题：{query}
数据来源：{mode_desc}

重要要求：
1. 使用 Markdown 格式
2. 内容必须基于提供的搜索结果和分析数据，不得编造
3. 如果某个板块没有足够信息支撑，简要说明原因而非编造
4. **语言降温原则**：结论强度不得超过证据支撑。禁止使用绝对化表达：
   - 禁止：「全球前沿水平」「颠覆性」「碾压式领先」
   - 替换为：「达到竞争水平」「在部分评测中表现突出」「可能产生影响」
   - 对未发生的事件，必须使用条件语气：「若...则可能...」「市场预期...」

---

**必选板块**（所有查询都必须生成以下 4 个板块）：

## TL;DR 情报速览

用 1 段话（不超过 100 字）概括本次分析的核心内容，面向忙碌的决策者，30 秒内可读完。
- 必须包含：主题、关键事实、核心结论
- 禁止使用列表，全部段落叙述


## 二、核心摘要

面向决策者的 2 分钟版摘要，**必须严格区分事实、分析判断和推测**，分三段输出（每段以粗体小标题开头）：

**【事实】**：围绕"{query}"的可验证核心事实（2-3 句，含时间/主体/事件，仅陈述已确认信息）。
**【分析判断】**：基于上述事实的推理结论（2-3 句，说明影响面与意义）。
**【推测】**：基于现有信息的合理推断（1-2 句，明确标注不确定性，如"若...则可能..."）。

硬性约束：
1. 【事实】段只能包含搜索结果中明确提及的信息，不得加入推理
2. 【分析判断】段必须标注推理依据（如"基于 X 来源的报道"）
3. 【推测】段必须使用"可能""若...则"等不确定性措辞
4. 禁止使用列表，全部段落叙述


## 八、舆情趋势

基于搜索结果，分析公众/行业对该主题的态度分布：

**舆情比例**：
- 正面：[XX]%
- 中性：[XX]%
- 负面：[XX]%
（三项之和必须为 100%）

**样本规模**：[基于搜索结果数量估算]

**方法论声明**：以上比例基于抓取样本人工/模型分类估算，不代表总体观点。

**正面观点**：
+ [具体正面观点1]
+ [具体正面观点2]

**负面观点**：
- [具体负面观点1]
- [具体负面观点2]

**总体舆情**：[正面偏积极 / 中性偏积极 / 中性 / 中性偏消极 / 负面]（一句话总结）

（必须基于搜索结果中的实际表述，不得编造不存在的观点；比例必须量化）


## 九、影响评估

从三个维度评估该事件/主题的影响：

**技术影响**：[★★★★☆] [1-2句分析]
**产业影响**：[★★★★☆] [1-2句分析]
**用户影响**：[★★★★☆] [1-2句分析]

**影响对象矩阵**：
| 对象 | 影响程度 | 说明 |
|------|---------|------|
| 开发者/技术社区 | [★★★★★] | [1句说明] |
| 企业用户/采购方 | [★★★☆☆] | [1句说明] |
| 普通消费者 | [★★★☆☆] | [1句说明] |

**关键判断**：[一句话概括最核心的影响判断]


---

**可选板块**（仅当查询主题涉及安全、风险、威胁时生成，否则跳过）：

判断标准：如果查询主题涉及网络安全、数据泄露、恶意攻击、技术风险等安全/风险话题，请额外生成以下板块；如果话题与安全风险无关（如商业、产品、市场、政策等），则**不要输出**以下板块。

## 六、证据链

从搜索结果中提炼 3-5 个关键结论，每个结论列出支撑证据节点：

**结论 1**：[一句话概括关键结论]
- E1：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
- E2：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
**综合置信度**：[高/中/低]

来源等级定义：A=官方声明/权威媒体；B=专业媒体；C=社区平台；D=匿名博客/个人网站


## 十、风险评估

**风险等级**：[高 / 中 / 低]

**风险矩阵**：
| 风险类型 | 发生概率 | 影响程度 | 综合评级 |
|---------|---------|---------|----------|
| [风险1] | [高/中/低] | [高/中/低] | [高/中/低] |
| [风险2] | [高/中/低] | [高/中/低] | [高/中/低] |

**关键发现**：[1-3条具体风险发现]

**建议**：[1-2条监控或应对建议]


## 十二、攻击面分析

从安全产品视角，分层分析该主题的攻击面/风险面：

**1. API/接口层**
- 风险点：[描述]
- 影响：[高/中/低]

**2. 分发/传播层**
- 风险点：[描述]
- 影响：[高/中/低]

**3. 模型/技术层**
- 风险点：[描述]
- 影响：[高/中/低]

**4. 企业/合规层**
- 风险点：[描述]
- 影响：[高/中/低]

**攻击面总结**：[一句话概括最核心的攻击面风险]


## 十三、情报判断与后续关注

**综合判断**：
[2-3句综合分析，说明当前态势、关键不确定性和最值得关注的方向]

**后续关注指标**：
1. [具体可监测的指标1]
2. [具体可监测的指标2]
3. [具体可监测的指标3]

**建议观察窗口**：[X天]


搜索结果内容将在用户消息中提供。请直接生成上述板块，不要有任何对话或提问。
"""


def _build_augmented_content(content, credibility_context="", kg_context="", conflicts_context="", kb_context=""):
    """Build the augmented content string with context from analysis modules."""
    augmented_content = ""
    if isinstance(content, dict):
        for url, text in content.items():
            n = min(len(text), 4000)
            text_clean = re.sub(r'!\[.*?\]\(.*?\)', '', text[:n])
            text_clean = re.sub(r'<img[^>]*>', '', text_clean)
            text_clean = re.sub(r'\b\S+\.(png|jpg|jpeg|gif|webp|svg)\b', '', text_clean)
            augmented_content += f"\n---\n来源: {url}\n{text_clean}\n"
    else:
        augmented_content = str(content)

    if credibility_context:
        augmented_content += f"\n\n=== 来源可信度评估 ===\n{credibility_context}\n"
    if kg_context:
        augmented_content += f"\n\n=== 关键实体 ===\n{kg_context}\n"
    if conflicts_context:
        augmented_content += f"\n\n=== 跨源冲突信息 ===\n{conflicts_context}\n"
    if kb_context:
        augmented_content += f"\n\n=== 历史知识库参考（用户既往收藏，供关联分析） ===\n{kb_context}\n"

    return augmented_content


def _is_small_model(model_name: str) -> bool:
    """检测是否为小参数模型（≤32B），需要简化输入和 prompt。

    只依据显式参数量标识（如 -7b、-27b）判断——本地部署的真小模型
    几乎都带参数后缀。不做系列前缀猜测：那会把 qwen3-max 等云端
    旗舰误判为小模型导致输入被截断。误判兜底由 generate_summary 的
    「输出格式校验 → 简化 prompt 重试」路径承担。
    """
    if not model_name:
        return False
    name = model_name.lower()
    # 参数量标识：27b, 14b, 7b, 3b 等
    small_params = ['3b', '7b', '8b', '14b', '27b', '1.5b', '0.5b']
    return any(p in name for p in small_params)


def _truncate_augmented_content(content: str, max_chars: int = 30000) -> str:
    """截断增强内容，防止小模型输入过长。"""
    if len(content) <= max_chars:
        return content
    # 保留前 max_chars 字符，但确保在完整来源边界截断
    truncated = content[:max_chars]
    last_source = truncated.rfind('\n---\n来源:')
    if last_source > max_chars // 2:
        truncated = truncated[:last_source]
    return truncated + '\n\n[... 其余来源已截断 ...]'


def _validate_llm_output(output: str) -> int:
    """验证 LLM 输出包含多少个必选板块标题。
    
    返回找到的必选板块数量（0-3）：
    核心摘要、舆情趋势、影响评估
    可选板块（证据链/风险评估/攻击面分析/情报判断）不计入验证。
    """
    if not output or len(output) < 100:
        return 0
    
    required_sections = ["核心摘要", "舆情趋势", "影响评估"]
    return sum(1 for s in required_sections if s in output)


def _build_simplified_prompt(query, search_mode):
    """构建简化版 prompt（用于重试）。
    
    当模型无法遵循复杂的多板块指令时，使用更简单的格式要求。
    只要求 4 个必选板块，不包含可选板块。
    """
    mode_desc = _get_mode_description(search_mode)
    return f"""
你是情报分析师。基于搜索结果，生成情报分析报告。

主题：{query}
来源：{mode_desc}

必须严格按以下格式输出（每个板块用 ## 开头，不能缺少）：

## TL;DR 情报速览
[1 段话，不超过 100 字，概括核心内容]

## 二、核心摘要
**【事实】**：[2-3 句核心事实]
**【分析判断】**：[推理结论]
**【推测】**：[合理推断]

## 八、舆情趋势
正面：XX% | 中性：XX% | 负面：XX%
[正面观点]
[负面观点]

## 九、影响评估
**技术影响**：[★★★★☆] [分析]
**产业影响**：[★★★★☆] [分析]
**用户影响**：[★★★★☆] [分析]

直接输出，不要提问。
"""


def generate_summary(llm, query, content, search_mode="all",
                     credibility_context="", kg_context="", conflicts_context="", kb_context=""):
    """生成情报报告，根据搜索模式调整分析重点"""

    logger.info(f"[generate_summary] 开始生成报告: query='{query[:50]}...', mode={search_mode}, llm={type(llm).__name__}")
    
    # 检查 LLM 实例是否有效
    if llm is None:
        logger.error("[generate_summary] LLM 实例为 None，无法生成报告")
        return ""
    
    logger.debug(f"Content type: {type(content)}")
    if isinstance(content, dict):
        logger.debug(f"Content keys count: {len(content)}")
        logger.debug(f"Content keys: {list(content.keys())[:5]}")
        if content:
            first_val = list(content.values())[0]
            logger.debug(f"First value length: {len(first_val)}")
            logger.debug(f"First value preview: {first_val[:300]}")
    elif isinstance(content, list):
        logger.debug(f"Content is list, length: {len(content)}")

    model_name = getattr(llm, 'model_name', '') or getattr(llm, 'model', '') or ''
    is_small = _is_small_model(model_name)
    
    if is_small:
        logger.info(f"检测到小模型 '{model_name}'，启用简化模式（截断输入）")

    system_prompt = _build_system_prompt(query, search_mode)
    # LangChain ChatPromptTemplate 默认使用 f-string 模板格式，
    # 会将 system_prompt 中的 { } 误认为模板变量。需要转义为 {{ }}。
    system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}")
    augmented_content = _build_augmented_content(content, credibility_context, kg_context, conflicts_context, kb_context)
    
    # 小模型截断输入
    if is_small:
        augmented_content = _truncate_augmented_content(augmented_content, max_chars=25000)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt_escaped), ("user", "搜索结果内容:\n{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    
    try:
        output = chain.invoke({"content": augmented_content})
        
        # 调试日志：输出 LLM 原始响应长度
        logger.info(f"LLM 原始输出长度: {len(output)} chars")
        logger.debug(f"LLM 完整输出:\n{output}")
        
        # 验证输出格式：至少包含 2 个必选板块
        section_count = _validate_llm_output(output)
        min_sections = 2
        logger.info(f"LLM 输出验证: {section_count} 个必选板块 (期望>={min_sections})")
        if section_count >= min_sections:
            return output
        
        # 输出格式不符，使用简化 prompt 重试
        logger.warning(f"LLM 输出仅包含 {section_count} 个板块（期望>={min_sections}），使用简化 prompt 重试")
        
        # 小模型重试时也截断输入
        retry_content = _truncate_augmented_content(augmented_content, 20000) if is_small else augmented_content
        simplified_prompt = _build_simplified_prompt(query, search_mode)
        simplified_prompt_escaped = simplified_prompt.replace("{", "{{").replace("}", "}}")
        retry_template = ChatPromptTemplate(
            [("system", simplified_prompt_escaped), ("user", "搜索结果内容:\n{content}")]
        )
        retry_chain = retry_template | llm | StrOutputParser()
        retry_output = retry_chain.invoke({"content": retry_content})
        
        retry_count = _validate_llm_output(retry_output)
        if retry_count >= min_sections:
            logger.info(f"简化 prompt 重试成功（{retry_count} 板块）")
            return retry_output
        
        # 重试仍失败，返回板块更多的那个
        logger.warning(f"重试仍仅 {retry_count} 个板块 (期望>={min_sections})，返回较长的输出 (output={len(output)} chars, retry={len(retry_output)} chars)")
        return output if len(output) >= len(retry_output) else retry_output
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM API error ({type(e).__name__}): {error_msg}")
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return _ERROR_TEMPLATE_TIMEOUT
        else:
            return _ERROR_TEMPLATE_GENERIC.format(error_msg=error_msg)
