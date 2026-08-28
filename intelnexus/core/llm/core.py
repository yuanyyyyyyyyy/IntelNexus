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


def classify_query_topic(query: str) -> str:
    """返回 'security' 或 'general'。规则匹配，零 LLM 开销。"""
    if not query:
        return "general"
    q = query.lower()
    return "security" if any(h in q for h in _SECURITY_HINTS) else "general"


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
    """Build the system prompt for the LLM.

    新策略：LLM 只生成需要语义理解的 6 个分析板块，
    其余 7 个板块由程序化生成（零 LLM 成本、确定性高）。
    """
    mode_desc = _get_mode_description(search_mode)
    return f"""
你是一位高级网络情报分析师。基于以下搜索结果和分析数据，请生成一份情报分析报告的**分析板块**。

查询主题：{query}
数据来源：{mode_desc}

重要要求：
1. 直接输出以下 6 个板块，不要输出其他内容
2. 每个板块必须严格使用指定的标题格式（## 二、... 等）
3. 内容必须基于提供的搜索结果和分析数据，不得编造
4. 使用 Markdown 格式
5. 如果某个板块没有足够信息支撑，简要说明原因而非编造
6. **情报语言降温原则**：结论强度不得超过证据支撑。禁止使用以下绝对化表达：
   - 禁止：「全球前沿水平」「超越主流闭源竞品」「重塑产业格局」「碾压式领先」「颠覆性」
   - 替换为：「达到前沿竞争水平」「在部分评测中表现突出」「可能对市场格局产生影响」
   - 禁止：「确认」「证实」（除非有官方声明）
   - 替换为：「高度可能」「多方证据指向」「据报道确认」
   - 对未发生的事件（如预期发布），必须使用条件语气：「若...则可能...」「市场预期...」
   - 来源等级低的证据（社区博客、X帖子）不能支撑重结论，应标注「据第三方测试」「尚缺官方复现」

请严格按以下顺序和标题输出 6 个板块：

## 二、核心摘要

面向决策者的 2 分钟版摘要，**必须严格区分事实、分析判断和推测**，分三段输出（每段以粗体小标题开头）：

**【事实】**：围绕"{query}"的可验证核心事实（2-3 句，含时间/主体/事件，仅陈述已确认信息）。
**【分析判断】**：基于上述事实的推理结论（2-3 句，说明影响面与意义，关联行业/政策/风险格局）。
**【推测】**：基于现有信息的合理推断（1-2 句，明确标注不确定性，如"若...则可能..."）。

硬性约束：
1. 【事实】段只能包含搜索结果中明确提及的信息，不得加入推理
2. 【分析判断】段必须标注推理依据（如"基于 X 来源的报道"）
3. 【推测】段必须使用"可能""若...则"等不确定性措辞
4. 禁止使用列表，全部段落叙述
5. 必须提供增量信息（具体数据、因果链、对比基准或时间线）


## 六、证据链

从搜索结果中提炼 3-5 个关键结论，每个结论列出支撑证据节点：

**结论 1**：[一句话概括关键结论，**结论强度不得超过支撑证据的来源等级**]
- E1：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
- E2：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
- E3：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
**综合置信度**：[高/中/低]
**置信度依据**：[说明计算方式，如：A级来源直接证据 40% + B级独立确认 30% + 技术关联 20% + 社区佐证 10%]

来源等级定义：A=官方声明/权威媒体（Bloomberg、NVD）；B=专业媒体（TechCrunch、The Verge）；C=社区平台（HackerNews、知乎）；D=匿名博客/个人网站

**结论 2**：[一句话概括关键结论]
- E1：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
- E2：[证据描述]（来源：[来源名]，来源等级：[A/B/C/D]，支持度：[高/中/低]）
**综合置信度**：[高/中/低]
**置信度依据**：[说明计算方式]

（每个结论至少 2 个证据节点；支持度和置信度统一使用 高/中/低 三级，禁止使用精确数字如 0.82；
来源等级必须标注，低等级来源[D级]不能单独支撑关键结论）


## 八、舆情趋势

基于搜索结果，分析公众/行业对该主题的态度分布：

**舆情比例**：
- 正面：[XX]%
- 中性：[XX]%
- 负面：[XX]%
（三项之和必须为 100%）

**样本规模**：[基于搜索结果数量估算，如"约 XX 条讨论/报道"]

**方法论声明**：以上比例基于抓取样本人工/模型分类估算，样本来源包括搜索结果、社交媒体与新闻报道，不代表总体开发者群体观点。

**正面观点**：
+ [具体正面观点1]
+ [具体正面观点2]

**负面观点**：
- [具体负面观点1]
- [具体负面观点2]

**中性/争议观点**：
• [如有争议性讨论]

**总体舆情**：[正面偏积极 / 中性偏积极 / 中性 / 中性偏消极 / 负面]（一句话总结）

（必须基于搜索结果中的实际表述，不得编造不存在的观点；比例必须量化，不得只给定性描述）


## 九、影响评估

从四个维度评估该事件/主题的影响：

**技术影响**：[★★★★☆] [1-2句分析]
**产业影响**：[★★★★☆] [1-2句分析]
**安全影响**：[★★★★☆] [1-2句分析]
**生态影响**：[★★★★☆] [1-2句分析]

**影响对象矩阵**：
| 对象 | 影响程度 | 说明 |
|------|---------|------|
| 开发者/技术社区 | [★★★★★] | [1句说明] |
| 模型厂商/竞争对手 | [★★★★☆] | [1句说明] |
| 企业用户/采购方 | [★★★☆☆] | [1句说明] |
| 监管机构/政策制定者 | [★★★☆☆] | [1句说明] |

**关键判断**：[一句话概括最核心的影响判断]


## 十、风险评估

**风险等级**：[高 / 中 / 低]

**风险矩阵**：
| 风险类型 | 发生概率 | 影响程度 | 综合评级 |
|---------|---------|---------|----------|
| [风险1，如：数据泄露] | [高/中/低] | [高/中/低] | [高/中/低] |
| [风险2，如：供应链透明风险] | [高/中/低] | [高/中/低] | [高/中/低] |
| [风险3，如：合规风险] | [高/中/低] | [高/中/低] | [高/中/低] |

**风险类型**：
☑ [识别到的风险类型，如：数据泄露风险、舆论风险、技术风险、合规风险等]

**关键发现**：
[1-3条具体风险发现，含来源和可信度说明]

**建议**：
[1-2条监控或应对建议]

（概率×影响矩阵：综合评级 = 概率与影响的乘积，如“高概率×高影响=高风险”）


## 十一、情报判断与后续关注

**综合判断**：
[2-3句综合分析，说明当前态势、关键不确定性和最值得关注的方向]

**后续关注指标**：
1. [具体可监测的指标1]
2. [具体可监测的指标2]
3. [具体可监测的指标3]
4. [具体可监测的指标4]
5. [具体可监测的指标5]

**建议观察窗口**：[X天]


搜索结果内容将在用户消息中提供。请直接生成上述 6 个板块，不要有任何对话或提问。
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


def _validate_llm_output(output: str) -> bool:
    """验证 LLM 输出是否包含预期的板块标题。
    
    至少需要包含 3 个板块标题才认为输出有效。
    """
    if not output or len(output) < 100:
        return False
    
    expected_sections = [
        "核心摘要", "证据链", "舆情趋势", "影响评估", "风险评估", "情报判断"
    ]
    found = sum(1 for s in expected_sections if s in output)
    return found >= 3


def _build_simplified_prompt(query, search_mode):
    """构建简化版 prompt（用于重试）。
    
    当模型无法遵循复杂的多板块指令时，使用更简单的格式要求。
    """
    mode_desc = _get_mode_description(search_mode)
    return f"""
你是一位高级网络情报分析师。基于以下搜索结果，请生成一份简洁的情报分析报告。

查询主题：{query}
数据来源：{mode_desc}

请严格按以下 6 个标题输出（每个标题用 ## 开头）：

## 二、核心摘要
[2-3 句事实描述]

## 六、证据链
[3-5 个关键结论，每个结论列出证据来源]

## 八、舆情趋势
[正面/负面/中性观点分布]

## 九、影响评估
[技术/产业/安全/生态四维影响]

## 十、风险评估
[风险等级和关键风险点]

## 十一、情报判断与后续关注
[综合判断和后续监测指标]

搜索结果内容将在用户消息中提供。请直接生成上述 6 个板块，不要有任何对话或提问。
"""


def generate_summary(llm, query, content, search_mode="all",
                     credibility_context="", kg_context="", conflicts_context="", kb_context=""):
    """生成情报报告，根据搜索模式调整分析重点"""

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

    system_prompt = _build_system_prompt(query, search_mode)
    augmented_content = _build_augmented_content(content, credibility_context, kg_context, conflicts_context, kb_context)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "搜索结果内容:\n{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    
    try:
        output = chain.invoke({"content": augmented_content})
        
        # 验证输出格式
        if _validate_llm_output(output):
            return output
        
        # 输出格式不符，使用简化 prompt 重试一次
        logger.warning(f"LLM 输出格式不符预期（找到 {_validate_llm_output(output)} 个板块），使用简化 prompt 重试")
        simplified_prompt = _build_simplified_prompt(query, search_mode)
        retry_template = ChatPromptTemplate(
            [("system", simplified_prompt), ("user", "搜索结果内容:\n{content}")]
        )
        retry_chain = retry_template | llm | StrOutputParser()
        retry_output = retry_chain.invoke({"content": augmented_content})
        
        if _validate_llm_output(retry_output):
            logger.info("简化 prompt 重试成功")
            return retry_output
        
        # 重试仍失败，返回原始输出（让 report_builder 降级处理）
        logger.warning("简化 prompt 重试仍失败，返回原始输出")
        return output
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM API error ({type(e).__name__}): {error_msg}")
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return _ERROR_TEMPLATE_TIMEOUT
        else:
            return _ERROR_TEMPLATE_GENERIC.format(error_msg=error_msg)
