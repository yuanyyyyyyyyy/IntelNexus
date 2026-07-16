"""
AI简报分析生成器
===============
使用LLM分析搜索结果并生成简报内容
"""

from typing import Dict, List
from datetime import datetime

from ai_briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG
from ai_briefing.prompts import get_prompt
from ai_briefing.templates import (
    render_markdown_briefing,
    format_news_item
)
from src.logger import get_logger

logger = get_logger(__name__)


class AIBriefingAnalyzer:
    """AI简报分析生成器"""
    
    def __init__(self, llm=None):
        """
        初始化分析器
        
        Args:
            llm: LLM模型实例（可选，如果不提供则尝试自动加载）
        """
        self._llm = llm
    
    def _get_llm(self):
        """获取LLM实例"""
        if self._llm is not None:
            return self._llm
        
        try:
            from src.llm.core import get_llm
            # 尝试使用默认模型
            self._llm = get_llm("qwen2.5:7b")
            return self._llm
        except Exception as e:
            logger.warning(f"Could not load LLM: {e}")
            return None
    
    def generate_briefing(
        self,
        collected_data: Dict[str, List[Dict]],
        organization_name: str = None
    ) -> str:
        """
        生成完整的简报
        
        Args:
            collected_data: 采集的数据，格式为 {category_id: [results]}
            organization_name: 组织名称
        
        Returns:
            str: Markdown格式的完整简报
        """
        if organization_name is None:
            organization_name = BRIEFING_CONFIG["organization"]["name"]
        
        generated_date = datetime.now().strftime("%Y年%m月%d日")
        
        llm = self._get_llm()
        
        # 生成各部分内容
        top3_content = self._generate_top3(collected_data, llm)
        gov_usage_content = self._generate_section("ai_gov_usage", collected_data.get("ai_gov_usage", []), llm)
        china_narrative_content = self._generate_section("ai_china_narrative", collected_data.get("ai_china_narrative", []), llm)
        legislation_content = self._generate_section("ai_legislation", collected_data.get("ai_legislation", []), llm)
        data_leak_content = self._generate_section("ai_data_leak", collected_data.get("ai_data_leak", []), llm)
        insights_content = self._generate_insights(collected_data, llm)
        links_content = self._generate_links(collected_data)
        
        # 渲染完整简报
        briefing = render_markdown_briefing(
            generated_date=generated_date,
            organization_name=organization_name,
            top3_content=top3_content,
            ai_gov_usage_content=gov_usage_content,
            ai_china_narrative_content=china_narrative_content,
            ai_legislation_content=legislation_content,
            ai_data_leak_content=data_leak_content,
            insights_content=insights_content,
            links_content=links_content
        )
        
        return briefing
    
    def _generate_top3(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日要闻TOP3"""
        # 合并所有数据
        all_results = []
        for results in collected_data.values():
            all_results.extend(results)
        
        if not all_results:
            return "本日暂无重要新闻。"
        
        if llm is None:
            # 如果没有LLM，使用简单的前3条
            top_items = all_results[:3]
            result = []
            for i, item in enumerate(top_items, 1):
                result.append(format_news_item(
                    title=item.get("title", "未知标题"),
                    content=item.get("description", item.get("content", ""))[:200],
                    source=item.get("source", "未知来源"),
                    date=item.get("published_at", datetime.now().strftime("%Y-%m-%d"))
                ))
            return "\n".join(result)
        
        try:
            # 构建搜索结果摘要
            search_summary = self._format_results_for_prompt(all_results[:20])
            
            prompt = get_prompt("top3", search_results=search_summary)
            
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            system_prompt = "你是一位高级AI情报分析师。请根据搜索结果提取最重要的3条新闻。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()
            
            result = chain.invoke({"prompt": prompt})
            return result
        except Exception as e:
            logger.error(f"Error generating TOP3: {e}")
            return "简报生成过程中出现错误，请检查LLM配置。"
    
    def _generate_section(self, category: str, results: List[Dict], llm) -> str:
        """生成单个部分的简报内容"""
        if not results:
            return "本日暂无相关动态。"
        
        cat_config = WATCH_CATEGORIES.get(category, {})
        
        if llm is None:
            # 如果没有LLM，使用简单的格式化
            result = []
            for item in results[:5]:
                result.append(format_news_item(
                    title=item.get("title", "未知标题"),
                    content=item.get("description", item.get("content", ""))[:150],
                    source=item.get("source", "未知来源"),
                    date=item.get("published_at", datetime.now().strftime("%Y-%m-%d"))
                ))
            return "\n".join(result)
        
        try:
            # 根据类别选择不同的提示词
            prompt_name = {
                "ai_gov_usage": "gov_usage",
                "ai_china_narrative": "china_narrative",
                "ai_legislation": "legislation",
                "ai_data_leak": "data_leak"
            }.get(category, "gov_usage")
            
            search_summary = self._format_results_for_prompt(results[:10])
            prompt = get_prompt(prompt_name, search_results=search_summary)
            
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            system_prompt = f"你是一位AI情报分析师。请生成'{cat_config.get('name', category)}'部分的简报内容。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()
            
            result = chain.invoke({"prompt": prompt})
            return result
        except Exception as e:
            logger.error(f"Error generating section {category}: {e}")
            return "简报生成过程中出现错误。"
    
    def _generate_insights(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成趋势研判与防护建议"""
        # 构建今日动态概要
        highlights = []
        for category, results in collected_data.items():
            cat_name = WATCH_CATEGORIES.get(category, {}).get("name", category)
            if results:
                highlights.append(f"{cat_name}: {len(results)}条信息")
        
        if not highlights:
            return "本日暂无足够数据生成趋势分析。"
        
        today_highlights = "\n".join(highlights)
        
        if llm is None:
            # 如果没有LLM，返回默认建议
            return """1. **AI技术发展持续加速**
   各国在AI领域的投入持续增加，建议关注技术发展动态。
   
   **建议：** 保持对AI新技术的关注，及时评估潜在影响。

2. **AI安全风险日益突出**
   AI相关的安全事件和漏洞披露频繁，需加强安全防护。
   
   **建议：** 定期检查AI系统安全性，及时更新防护措施。

3. **AI监管政策逐步完善**
   各国AI相关法规陆续出台，企业需关注合规要求。
   
   **建议：** 跟踪AI政策动态，确保业务合规。"""
        
        try:
            prompt = get_prompt("insight", today_highlights=today_highlights)
            
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            system_prompt = "你是一位AI安全风险分析师。请根据今日动态生成3条趋势研判与防护建议。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()
            
            result = chain.invoke({"prompt": prompt})
            return result
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return "趋势分析生成过程中出现错误。"
    
    def _generate_links(self, collected_data: Dict[str, List[Dict]]) -> str:
        """生成重要链接部分"""
        links = []
        seen_urls = set()
        
        for results in collected_data.values():
            for item in results[:3]:  # 每个类别最多3个链接
                url = item.get("url", "")
                title = item.get("title", "")[:50]
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    links.append(f"• {title}: {url}")
        
        if not links:
            return "暂无重要链接。"
        
        return "\n".join(links[:10])  # 最多10个链接
    
    def _format_results_for_prompt(self, results: List[Dict]) -> str:
        """将搜索结果格式化为提示词可用的格式"""
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", "No URL")
            source = r.get("source", "Unknown")
            date = r.get("published_at", "Unknown date")
            desc = r.get("description", r.get("content", ""))[:200]
            
            formatted.append(f"{i}. {title}")
            formatted.append(f"   URL: {url}")
            formatted.append(f"   Source: {source}")
            formatted.append(f"   Date: {date}")
            formatted.append(f"   Description: {desc}")
            formatted.append("")
        
        return "\n".join(formatted)
