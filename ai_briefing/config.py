"""
AI简报关注点配置
===============
定义4个关注点的关键词、查询模板和简报配置
"""

from datetime import datetime


# 动态年份
YEAR = datetime.now().year


# ========== 4个关注点配置 ==========
WATCH_CATEGORIES = {
    "ai_gov_usage": {
        "name": "美欧机构AI应用",
        "name_en": "US/EU Government AI Adoption",
        "description": "美欧国家机构、敏感部门应用新AI技术的报道",
        "icon": "🏛️",
        "keywords_en": [
            "US government AI", "Pentagon AI", "NATO AI", "EU AI adoption",
            "White House AI", "DoD artificial intelligence", "CIA AI",
            "intelligence community AI", "federal AI strategy",
            "UK government AI", "France AI military", "Germany AI defense",
            "AI military application", "AI defense system"
        ],
        "keywords_zh": [
            "美国政府 人工智能", "五角大楼 AI", "北约 人工智能",
            "欧盟 AI应用", "白宫 人工智能", "军方 人工智能",
            "英国政府 AI", "法国 军事AI", "德国 国防AI",
            "军事 人工智能", "国防 AI系统"
        ],
        "search_queries": [
            f"Pentagon artificial intelligence {YEAR}",
            "NATO AI strategy implementation",
            "EU AI Act government agencies",
            "US intelligence community AI tools",
            "military AI applications news"
        ]
    },
    "ai_china_narrative": {
        "name": "涉我AI舆论",
        "name_en": "China-related AI Narrative",
        "description": "美欧涉我AI领域（算料算法算力等维度）的舆论报道",
        "icon": "🇨🇳",
        "keywords_en": [
            "China AI", "Chinese AI companies", "Baidu AI", "Alibaba AI",
            "TikTok AI", "DeepSeek", "AI chip ban China", "semiconductor restrictions",
            "computing power China", "data China AI", "algorithm China",
            "Huawei AI", "Tencent AI", "SenseTime", "Megvii",
            "AI restriction China", "China AI regulation"
        ],
        "keywords_zh": [
            "中国 人工智能", "中国AI公司", "百度 阿里 腾讯 AI",
            "算力 芯片禁令", "算法 中国", "数据 中国AI",
            "华为 人工智能", "商汤 旷视", "DeepSeek",
            "AI限制 中国", "中国 AI监管"
        ],
        "search_queries": [
            f"China AI chip export controls {YEAR}",
            "Chinese AI companies global expansion",
            "US restrictions China AI technology",
            "DeepSeek AI model capabilities",
            "China artificial intelligence news"
        ]
    },
    "ai_legislation": {
        "name": "AI新法案",
        "name_en": "AI Legislation & Regulation",
        "description": "美欧涉AI领域且与我国有关的新法案出台情况",
        "icon": "📜",
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
            "US AI regulation new bill",
            "AI legislation affecting China",
            "artificial intelligence governance policy",
            f"AI regulation news {YEAR}"
        ]
    },
    "ai_data_leak": {
        "name": "AI数据泄露",
        "name_en": "AI Data Breaches & Security",
        "description": "境外媒体报道的国外及国内因AI领域新技术引发的数据泄露风险事件",
        "icon": "🔒",
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
            "large language model security vulnerability",
            "AI powered cyber attack news",
            "training data privacy breach AI",
            "AI security incident news"
        ]
    }
}


# ========== 简报配置 ==========
BRIEFING_CONFIG = {
    "organization": {
        "name": "AI情报团队",
        "team": "AI简报系统",
        "contact": ""
    },
    "format": {
        "max_top3_items": 3,
        "max_items_per_section": 10,
        "max_insights": 3,
        "date_format": "%Y年%m月%d日（%A）",
        "include_cve_table": True,
        "include_links": True
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
    """根据ID获取关注点配置"""
    return WATCH_CATEGORIES.get(category_id, None)


def get_all_category_ids() -> list:
    """获取所有关注点ID"""
    return list(WATCH_CATEGORIES.keys())


def get_all_categories() -> dict:
    """获取所有关注点配置"""
    return WATCH_CATEGORIES
