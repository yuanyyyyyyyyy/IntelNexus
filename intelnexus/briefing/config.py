"""
AI简报关注点配置
===============
定义6个关注点的关键词、查询模板和简报配置
"""

import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def _env_org(key: str, default: str) -> str:
    """读取机构品牌配置项（环境变量优先，空则回退默认值）。"""
    val = os.getenv(key)
    return val if val not in (None, "") else default


# 动态年份
YEAR = datetime.now().year


# 简报中可被「订阅者关注点」过滤的板块（与 analyzer.SECTION_LABELS 保持一致；
# 关注点通过 section 字段挂到这些板块上，推送时按订阅者 interests 裁剪）
BRIEFING_SECTIONS = [
    "分类情报详情",
    "网络安全威胁区",
    "热点趋势分析",
]

# ========== 6个关注点配置 ==========
WATCH_CATEGORIES = {
    "ai_gov_usage": {
        "name": "美欧机构AI应用",
        "name_en": "US/EU Government AI Adoption",
        "description": "美欧国家机构、敏感部门应用新AI技术的报道",
        "icon": "govt",
        "section": "AI 领域动态",
        "keywords_en": [
            "US government AI", "Pentagon artificial intelligence", "NATO AI strategy",
            "EU AI adoption", "White House AI", "DoD artificial intelligence",
            "CIA AI", "intelligence community AI", "federal AI strategy",
            "UK government AI", "France AI military", "Germany AI defense",
            "AI military application", "AI defense system"
        ],
        "keywords_zh": [
            "美国政府 人工智能", "五角大楼 人工智能", "北约 人工智能",
            "欧盟 AI应用", "白宫 人工智能", "军方 人工智能",
            "英国政府 AI", "法国 军事AI", "德国 国防AI",
            "军事 人工智能", "国防 AI系统"
        ],
        "search_queries": [
            f"Pentagon artificial intelligence {YEAR}",
            f"NATO AI strategy implementation {YEAR}",
            f"military AI applications news {YEAR}",
            f"federal AI procurement contract {YEAR}"
        ]
    },
    "ai_china_narrative": {
        "name": "涉我AI舆论",
        "name_en": "China-related AI Narrative",
        "description": "美欧涉我AI领域（算料算法算力等维度）的舆论报道",
        "icon": "china",
        "section": "AI 领域动态",
        "keywords_en": [
            "China artificial intelligence", "Chinese AI companies", "Baidu AI",
            "Alibaba AI", "TikTok AI", "DeepSeek AI", "AI chip ban China",
            "semiconductor restrictions China", "computing power China",
            "data China AI", "algorithm China", "Huawei AI", "Tencent AI",
            "SenseTime", "Megvii", "AI restriction China", "China AI regulation"
        ],
        "keywords_zh": [
            "中国 人工智能", "中国AI公司", "百度 阿里 腾讯 AI",
            "算力 芯片禁令", "算法 中国", "数据 中国AI",
            "华为 人工智能", "商汤 旷视", "DeepSeek",
            "AI限制 中国", "中国 AI监管"
        ],
        "search_queries": [
            f"China AI chip export controls {YEAR}",
            f"Chinese AI companies global expansion {YEAR}",
            f"China artificial intelligence news {YEAR}",
            f"Huawei AI chip Ascend {YEAR}"
        ]
    },
    "ai_legislation": {
        "name": "AI新法案",
        "name_en": "AI Legislation & Regulation",
        "description": "美欧涉AI领域且与我国有关的新法案出台情况",
        "icon": "legislation",
        "section": "政策法规动态",
        "keywords_en": [
            "AI regulation", "AI legislation", "AI Act", "AI bill",
            "artificial intelligence law", "AI policy", "AI governance",
            "EU AI Act", "US AI regulation", "AI compliance",
            "AI executive order", "AI risk management",
            "AI safety regulation", "AI transparency"
        ],
        "keywords_zh": [
            "人工智能 法案", "AI监管", "AI立法", "人工智能 治理",
            "AI合规", "AI政策", "AI行政命令", "AI风险管理",
            "AI安全监管", "AI透明度"
        ],
        "search_queries": [
            f"EU AI Act implementation {YEAR}",
            f"US AI regulation new bill {YEAR}",
            f"AI legislation affecting China {YEAR}",
            f"AI regulation news {YEAR}"
        ]
    },
    "ai_data_leak": {
        "name": "AI数据泄露",
        "name_en": "AI Data Breaches & Security",
        "description": "境外媒体报道的国外及国内因AI领域新技术引发的数据泄露风险事件",
        "icon": "leak",
        "section": "网络安全动态",
        "keywords_en": [
            "AI data breach", "AI security incident", "AI vulnerability",
            "machine learning data leak", "LLM security", "AI cyber attack",
            "AI privacy breach", "training data leak", "model poisoning",
            "ChatGPT data leak", "AI ransomware", "AI phishing",
            "AI supply chain attack", "prompt injection"
        ],
        "keywords_zh": [
            "AI 数据泄露", "人工智能 安全事件", "AI漏洞",
            "大模型安全", "AI网络攻击", "训练数据泄露", "模型投毒",
            "ChatGPT 数据泄露", "AI勒索软件", "AI钓鱼攻击",
            "AI供应链攻击", "提示注入"
        ],
        "search_queries": [
            f"AI data breach incident {YEAR}",
            f"large language model security vulnerability {YEAR}",
            f"AI powered cyber attack news {YEAR}",
            f"training data privacy breach AI {YEAR}"
        ]
    },
    "cyber_vuln": {
        "name": "漏洞与威胁",
        "name_en": "Vulnerabilities & Threats",
        "description": "近期披露的通用高危漏洞、CVE、0day 与在野利用情报",
        "icon": "vuln",
        "section": "网络安全动态",
        "keywords_en": [
            "critical vulnerability disclosed", "zero-day exploit", "RCE vulnerability",
            "CVE security advisory", "CISA KEV", "exploit published",
            "CVSS critical score", "patch Tuesday security", "vulnerability research",
            "security flaw discovered"
        ],
        "keywords_zh": [
            "漏洞 CVE", "高危漏洞", "0day 利用", "在野利用",
            "远程代码执行", "漏洞披露", "补丁 安全公告",
            "安全漏洞 发布"
        ],
        "search_queries": [
            f"critical vulnerability disclosed {YEAR}",
            f"zero-day exploit in the wild {YEAR}",
            f"CISA known exploited vulnerabilities update {YEAR}",
            f"RCE vulnerability patch released {YEAR}"
        ]
    },
    "cyber_attack": {
        "name": "攻击事件与合规",
        "name_en": "Attack Incidents & Compliance",
        "description": "数据泄露、勒索攻击、重大安全事件及网络安全政策合规动态",
        "icon": "attack",
        "section": "网络安全动态",
        "keywords_en": [
            "data breach", "ransomware attack", "dark web leak",
            "cyber attack incident", "breach disclosed", "security regulation",
            "cybersecurity compliance", "government cyber policy"
        ],
        "keywords_zh": [
            "数据泄露", "勒索软件", "暗网 售卖", "网络攻击事件",
            "网络安全 政策", "合规 监管", "网络安全法"
        ],
        "search_queries": [
            f"major data breach disclosed {YEAR}",
            f"ransomware attack incident news {YEAR}",
            f"dark web database for sale {YEAR}",
            f"cybersecurity regulation policy update {YEAR}"
        ]
    }
}


# ========== 简报配置 ==========
BRIEFING_CONFIG = {
    "organization": {
        # 以下品牌字段均可通过 .env 中的 ORGANIZATION_* 覆盖（保持可配置，不写死任何品牌）
        "name": _env_org("ORGANIZATION_NAME", "AI情报团队"),            # 机构主名（页眉/封面/落款）
        "team": "AI简报系统",
        "producer_unit": _env_org("ORGANIZATION_PRODUCER_UNIT", ""),    # 出品单位（留空则省略）
        "contact": _env_org("ORGANIZATION_CONTACT", ""),                # 联系人/微信（留空则省略）
        "footer_qr_text": _env_org("ORGANIZATION_FOOTER_QR_TEXT", ""),  # 页脚"扫码关注"文案（留空则不渲染）
        "disclaimer": _env_org(
            "ORGANIZATION_DISCLAIMER",
            "本简报基于公开信息整理，不构成投资或其他专业建议。"
        )
    },
    "search": {
        "time_window_days": 7,  # 搜索时间窗口（天数）
        "max_results_per_category": 30,  # 每个关注点最大结果数
        "max_results_for_top3": 20,  # TOP3板块输入条数上限
        "max_results_for_sections": 15,  # 其他板块输入条数上限
        "global_timeout_seconds": 90,  # 全局搜索超时（秒）- 从60增加到90
    },
    "format": {
        "max_top3_items": 3,
        "max_items_per_section": 10,
        "max_insights": 3,
        "date_format": "%Y年%m月%d日",  # 星期由代码单独处理，避免Windows兼容性问题
        "include_cve_table": True,
        "include_links": True
    },
    "diff": {
        "max_history_compare": 1,  # 对比最近N期历史
        "max_added_display": 8,  # 新增条目最多显示数
        "max_removed_display": 5,  # 消失条目最多显示数
    },
    "push": {
        "wecom_max_chars": 4000,  # 企业微信截断字符数
        "dingtalk_max_chars": 4500,  # 钉钉截断字符数
        "retry_count": 3,  # 推送重试次数
        "retry_delay_seconds": 2,  # 重试延迟基数（指数退避）
    },
    "tags": {
        "new_release": "[新发布]",
        "important": "[重要]",
        "trend": "[趋势]",
        "market": "[市场]",
        "policy": "[政策]",
        "compliance": "[合规]",
        "data_breach": "[数据泄露]",
        "high_risk": "[高危]",
        "exploited": "[在野利用]"
    },
    "output_formats": {
        "markdown": True,
        "html_email": True,
        "pdf": True
    }
}


def get_category_by_id(category_id: str) -> dict:
    """根据ID获取关注点配置（含用户覆盖）"""
    return get_all_categories().get(category_id, None)


def get_all_category_ids() -> list:
    """获取所有关注点ID（含用户覆盖）"""
    return list(get_all_categories().keys())


def get_all_categories() -> dict:
    """
    获取所有关注点配置。

    原 WATCH_CATEGORIES 为代码默认；现叠加 data/watch_categories.json 的用户覆盖
    （新增/修改/禁用），实现「关注点可配置化」。用户未覆盖时完全回退默认。
    """
    try:
        from intelnexus.config.watch_categories import get_all_categories as _merged
        return _merged()
    except Exception:
        # 回退：配置文件读取失败时，仍返回代码默认，保证不破坏现有逻辑
        return WATCH_CATEGORIES
