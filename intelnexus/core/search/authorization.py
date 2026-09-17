"""针对性侦察的授权闸门
========================

对「具名实体 + 漏洞/渗透/攻击面」类查询做合规把关。

背景：系统曾对「某酒店 + 设施 + 漏洞」这类请求直接产出攻击面分析，
通篇没有授权状态、测试边界或用途声明。对真实在营实体（尤其是关键基础设施
或政府资产）开展未授权探测，在多数法域下存在明确法律风险。

闸门语义：
- 识别出「具体目标 + 进攻性意图」→ ``requires_authorization=True``；
- 未声明授权 → ``authorized=False``，调用方须降级为**纯 OSINT**：
  不生成攻击面、利用路径、探测步骤等可直接用于主动测试的内容；
- 仅面向公开 CVE / 通用安全原理的研究不属于针对性侦察，不拦截。

默认开启，可通过 ``enabled=False`` 或环境变量
``INTELNEXUS_REQUIRE_AUTH=0`` 关闭（自建自用场景）。
"""

import os
import re
from typing import Dict, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# ── 进攻性意图关键词 ────────────────────────────────────────────────────────
OFFENSIVE_INTENT_KEYWORDS = [
    "漏洞", "渗透", "攻击面", "利用", "入侵", "提权", "后门", "webshell",
    "内网", "打点", "拿下", "爆破", "社工", "0day",
    "vulnerability", "exploit", "pentest", "penetration", "attack surface",
    "scan", "recon",
]

# ── 具体目标指示（具名实体 / 资产）────────────────────────────────────────
TARGET_KEYWORDS = [
    "酒店", "宾馆", "公司", "集团", "企业", "工厂", "园区", "银行", "分行",
    "医院", "学校", "学院", "大学", "政府", "机关", "部门", "单位", "机构",
    "门店", "商场", "机场", "车站", "景区", "平台", "系统", "网站", "门户",
    "后台", "内网", "办公网", "生产线", "工控",
]

_TARGET_SUFFIX_RE = re.compile(
    r'(?:酒店|宾馆|公司|集团|企业|工厂|园区|银行|医院|学校|学院|大学|'
    r'政府|机关|部门|单位|机构|门店|商场|机场|车站|平台|系统|网站)'
)

# 英文资产词（B2：目标可能不带中文后缀，如 "scan the hotel network"）
_EN_TARGET_RE = re.compile(
    r'\b(?:hotel|hospital|school|university|college|bank|airport|company|'
    r'agency|government|facility|campus|resort|casino|datacenter|'
    r'data center|server|network)\b', re.IGNORECASE
)

# 「对 X 做/开展/进行 …」句式：X 往往是不带后缀词的具名目标
# （「对华尔道夫做渗透测试」），但捕获结果里若就是意图词本身
# （「对漏洞进行修复」）则不算目标。
_ACTION_ON_TARGET_RE = re.compile(
    r'对([\u4e00-\u9fffA-Za-z0-9· ]{2,24}?)(?:做|开展|进行)'
)

# 主机/IP/域名类资产指示
_HOST_RE = re.compile(
    r'(?:\b(?:\d{1,3}\.){3}\d{1,3}\b)'
    r'|(?:\b[a-zA-Z0-9-]+\.(?:com|cn|net|org|io|gov|edu|ru|top|xyz|info|biz)\b)'
)

# ── 通用主体豁免（B3：防守型研究不是针对性侦察）──────────────────────────
_CVE_ID_RE = re.compile(r'\b(?:CVE|CNVD|CNNVD)-\d{4}-\d{3,7}\b', re.IGNORECASE)

_GENERIC_PLATFORMS = (
    "windows", "linux", "log4j", "log4shell", "spring", "java", "python",
    "nginx", "apache", "mysql", "docker", "kubernetes", "wordpress", "php",
    "openssl", "struts", "shiro", "weblogic", "tomcat", "exchange",
    "gitlab", "jenkins", "oracle", "microsoft", "android", "ios", "redis",
    "elasticsearch", "vmware", "cisco", "fortinet", "sap", "thinkphp",
)

# 目标后缀词前面若只有这些字，说明是「网站/系统」这类泛指而非具体资产
_GENERIC_PREFIX_CHARS = set('该此本所有的与和及或个一些常主流的、，。；：！？（）() \t')

# ── 授权声明标记 ────────────────────────────────────────────────────────────
# 只收「声明类」短语。红队/蓝队/靶场是场景词不是授权声明，命中它们
# 不能自证授权（B4）。
AUTHORIZED_MARKERS = [
    "已授权", "已获授权", "书面授权", "授权测试", "授权范围内", "经授权",
    "授权书", "自有资产", "自己搭建",
    "authorized", "with permission", "permission granted",
    "scope approved", "lab environment", "owned asset",
]

_ENV_FLAG = "INTELNEXUS_REQUIRE_AUTH"


def _env_enabled() -> bool:
    """环境变量开关（默认开启）。"""
    val = os.environ.get(_ENV_FLAG, "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def _match_any(text: str, keywords) -> Optional[str]:
    lowered = (text or "").lower()
    for kw in keywords:
        if kw.lower() in lowered:
            return kw
    return None


def _mentions_generic_subject(query: str) -> bool:
    """查询是否在讨论通用平台或已公开编号的漏洞（防守型研究的强信号）。"""
    if _CVE_ID_RE.search(query or ""):
        return True
    low = (query or "").lower()
    return any(p in low for p in _GENERIC_PLATFORMS)


def _is_bare_generic(query: str, start: int) -> bool:
    """通用后缀词前面是否没有专名（如句首的「网站」vs「华尔道夫酒店」）。"""
    prefix = query[max(0, start - 6):start]
    for ch in prefix:
        if ch in _GENERIC_PREFIX_CHARS or ch.isspace():
            continue
        if ch.isalnum():
            return False
    return True


def _has_target_indicator(query: str) -> Optional[str]:
    """查询是否指向某个具体资产/具名实体。

    优先级：主机/IP > 品牌名（含「对 X 做…」句式）> 中文后缀词。
    中文后缀词只有在「不是泛指」时才算资产：
    - 前面有专名（「华尔道夫酒店」✓ / 句首的「网站漏洞」✗）；
    - 且查询没有在讨论通用平台或公开 CVE（「Windows 系统漏洞修复建议」✗）。
    """
    if not query:
        return None

    host = _HOST_RE.search(query)
    if host:
        return host.group(0)

    action = _ACTION_ON_TARGET_RE.search(query)
    if action and not any(kw in action.group(1) for kw in OFFENSIVE_INTENT_KEYWORDS):
        return action.group(1)

    en_target = _EN_TARGET_RE.search(query)
    if en_target:
        return en_target.group(0)

    suffix = _TARGET_SUFFIX_RE.search(query)
    if suffix and not _mentions_generic_subject(query) \
            and not _is_bare_generic(query, suffix.start()):
        return suffix.group(0)

    return None


def assess_authorization(query: str,
                         topic: str = "",
                         authorization_declared: bool = False,
                         authorization_scope: str = "",
                         llm_target_hint: Optional[bool] = None,
                         enabled: Optional[bool] = None) -> Dict:
    """评估查询是否属于需要授权声明的针对性侦察。

    Args:
        query: 用户原始查询
        topic: 查询分类（可选，仅用于日志与提示）
        authorization_declared: 调用方是否已显式取得授权声明（UI 勾选 / CLI 选项）
        authorization_scope: 用户填写的授权范围描述（目标、网段、时间窗口）。
            仅在已声明授权时采用，避免未授权场景下出现自相矛盾的文案。
        llm_target_hint: LLM 兜底判定结果（``llm_target_check`` 的返回值）。
            **只允许收紧**：仅在规则层识别到意图但未命中目标时，把 True
            视为命中；规则层已判定命中时，LLM 说「否」也不会放行。
        enabled: 闸门开关；``None`` 时取环境变量 ``INTELNEXUS_REQUIRE_AUTH``

    Returns:
        ``{"requires_authorization": bool, "authorized": bool,
        "scope_note": str, "matched_intent": str}``
    """
    if enabled is None:
        enabled = _env_enabled()

    text = f"{query or ''} {topic or ''}"
    intent = _match_any(text, OFFENSIVE_INTENT_KEYWORDS)
    target = _has_target_indicator(query or "")
    llm_confirmed = bool(intent and not target and llm_target_hint is True)
    if llm_confirmed:
        target = f"LLM 判定的具名目标（{intent}）"

    requires = bool(enabled and intent and target)
    authorized = (not requires) or authorization_declared or bool(
        _match_any(text, AUTHORIZED_MARKERS))

    if not requires:
        scope_note = "非针对性侦察请求，按常规公开信息分析处理。"
    elif authorized:
        scope_note = (
            "已识别针对性侦察意图并声明授权：分析限定在授权范围与授权窗口内，"
            "输出不得超出授权标的。"
        )
        scope = (authorization_scope or "").strip()
        if scope:
            scope_note = f"授权范围：{scope}。{scope_note}"
    else:
        scope_note = (
            "未声明授权：本次分析降级为纯公开信息（OSINT）收集，"
            "不生成攻击面、利用路径或探测步骤；对目标开展任何主动测试"
            "均需事先取得资产所有者的书面授权。"
        )

    return {
        "requires_authorization": requires,
        "authorized": authorized,
        "scope_note": scope_note,
        "matched_intent": intent or "",
        "target_indicator": target or "",
        "topic": topic or "",
    }


def llm_target_check(llm, query: str) -> Optional[bool]:
    """用 LLM 二级判定「该查询是否针对某个具名在营实体」。

    仅在规则层识别到进攻性意图、但未能命中具名目标的窄路径下调用
    （纯规则靠后缀词/主机名/句式匹配，对「对华尔道夫做渗透测试」这类
    不带通用后缀的品牌名会漏报）。

    Returns:
        ``True``  = LLM 认为是针对性侦察；``False`` / ``None`` = 无法判定。
        任何异常都返回 ``None``，调用方保持规则结果（fail-closed）。
    """
    if llm is None or not (query or "").strip():
        return None

    system = (
        "你是合规审查助手。判断用户查询是否针对某个具体的、在营的真实主体"
        "（具名酒店/公司/机构/系统/网站/资产，含品牌名、地名+机构名、主机名、IP）。\n"
        "只输出一个词：TARGETED 或 NOT_TARGETED。\n"
        "判定为 TARGETED 的例子：对华尔道夫做渗透测试；扫描 example.com 的漏洞；"
        "调研某某银行的所有设施漏洞。\n"
        "判定为 NOT_TARGETED 的例子：log4shell 漏洞原理；Windows 系统漏洞修复建议；"
        "漏洞扫描工具对比。\n"
        "拿不准时输出 NOT_TARGETED。"
    )
    template = None
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        template = ChatPromptTemplate([("system", system), ("user", "{q}")])
        out = (template | llm | StrOutputParser()).invoke({"q": query.strip()})
    except Exception as e:
        logger.warning(f"LLM 兜底判定失败，保持规则结果: {e}")
        return None

    answer = (out or "").strip().upper()
    # 契约：True = 判定为针对性侦察；False = 明确 NOT_TARGETED；
    # None = 无法判定（含解析失败），调用方保持规则结果。
    if "NOT_TARGETED" in answer:
        return False
    if "TARGETED" in answer:
        return True
    logger.warning(f"LLM 兜底判定输出无法解析，按无法判定处理: {out[:60]!r}")
    return None


#: 未授权时替代「攻击面分析」章节的合规说明
UNAUTHORIZED_NOTICE = (
    "> ⚠️ 本次查询未声明授权，已降级为**纯公开信息（OSINT）**分析。\n"
    ">\n"
    "> 未生成攻击面、利用路径或探测步骤。对真实在营资产开展任何主动探测、"
    "扫描或利用验证，均需事先取得资产所有者的书面授权，并遵守当地法律"
    "（如美国 CFAA、中国《网络安全法》等）。\n"
    ">\n"
    "> 如需开展授权评估，请在查询中声明授权范围与授权窗口后重新检索。"
)


def osint_only_system_addendum() -> str:
    """未授权时追加到 LLM system prompt 的边界约束。"""
    return (
        "**合规边界（强制）**：本次查询未声明对目标资产的测试授权。\n"
        "- 仅允许基于公开信息（OSINT）进行归纳，禁止输出可被直接用于主动测试的内容；\n"
        "- 禁止生成攻击面分层、利用路径、扫描/探测步骤、Payload、"
        "或任何面向该目标的入侵建议；\n"
        "- 如必须涉及风险，只能描述公开披露的信息并注明来源，"
        "同时提示需经授权方可验证。\n"
    )
