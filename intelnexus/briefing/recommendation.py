"""
智能推荐模块
============
基于用户历史行为推荐相关主题/简报
"""
from typing import Dict, List
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


def get_related_topics(user_searches: List[str] = None, user_feedback: List[Dict] = None) -> List[Dict]:
    """
    基于搜索历史和反馈推荐相关主题
    
    Args:
        user_searches: 用户搜索历史
        user_feedback: 用户反馈历史
    
    Returns:
        List[Dict]: 推荐的主题列表
    """
    try:
        from intelnexus.topics.store import get_all_topics
        
        # 获取用户关注的关键词
        user_keywords = set()
        
        # 从搜索历史提取关键词
        if user_searches:
            for search in user_searches:
                if isinstance(search, str):
                    user_keywords.update(search.split())
                elif isinstance(search, dict):
                    query = search.get("query", "")
                    user_keywords.update(query.split())
        
        # 从反馈历史提取关键词
        if user_feedback:
            for feedback in user_feedback:
                if isinstance(feedback, dict):
                    url = feedback.get("url", "")
                    # 从URL提取关键词（简化版）
                    parts = url.split("/")[-1].split("-")
                    user_keywords.update(parts[:3])  # 取前3个部分
        
        if not user_keywords:
            return []
        
        # 计算每个主题的相关度
        topics = get_all_topics()
        scored_topics = []
        
        for topic in topics:
            topic_keywords = set(topic.keywords_zh + topic.keywords_en)
            # 移除空字符串
            topic_keywords = {kw for kw in topic_keywords if kw}
            
            if not topic_keywords:
                continue
            
            # 计算关键词重叠
            overlap = len(user_keywords & topic_keywords)
            if overlap > 0:
                score = overlap / len(user_keywords)
                scored_topics.append({
                    "topic": topic,
                    "score": score
                })
        
        # 按相关度排序
        scored_topics.sort(key=lambda x: x["score"], reverse=True)
        return scored_topics[:5]
        
    except Exception as e:
        logger.warning(f"获取相关主题失败: {e}")
        return []


def get_similar_briefings(current_briefing_id: str = None) -> List[Dict]:
    """
    推荐相似的历史简报
    
    Args:
        current_briefing_id: 当前简报ID
    
    Returns:
        List[Dict]: 推荐的简报列表
    """
    try:
        from intelnexus.config.briefing_history import get_briefing_history
        
        if not current_briefing_id:
            return []
        
        history = get_briefing_history()
        
        # 获取当前简报的分类
        current_briefing = None
        for item in history.get_briefings(limit=100):
            if item.get("id") == current_briefing_id:
                current_briefing = item
                break
        
        if not current_briefing:
            return []
        
        current_cats = set(current_briefing.get("categories", []))
        if not current_cats:
            return []
        
        # 计算与其他简报的相似度
        similarities = []
        for past_briefing in history.get_briefings(limit=50):
            if past_briefing.get("id") == current_briefing_id:
                continue  # 跳过自身
            
            past_cats = set(past_briefing.get("categories", []))
            if not past_cats:
                continue
            
            # Jaccard相似度
            intersection = len(current_cats & past_cats)
            union = len(current_cats | past_cats)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0.3:
                similarities.append({
                    "briefing": past_briefing,
                    "similarity": similarity
                })
        
        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:3]
        
    except Exception as e:
        logger.warning(f"获取相似简报失败: {e}")
        return []


def get_trending_topics() -> List[Dict]:
    """
    获取当前热门主题
    
    Returns:
        List[Dict]: 热门主题列表
    """
    try:
        from intelnexus.config.feedback import get_all_category_feedback
        
        # 获取所有分类反馈
        feedback = get_all_category_feedback()
        
        # 按反馈数排序
        sorted_cats = sorted(
            feedback.items(),
            key=lambda x: x[1].get("up", 0) + x[1].get("down", 0),
            reverse=True
        )
        
        # 转换为推荐格式
        trending = []
        for cat_id, cat_data in sorted_cats[:5]:
            total = cat_data.get("up", 0) + cat_data.get("down", 0)
            if total > 0:
                # 获取分类名称
                name = _get_category_name(cat_id)
                trending.append({
                    "id": cat_id,
                    "name": name,
                    "score": cat_data.get("up", 0) / total if total > 0 else 0.5,
                    "count": total
                })
        
        return trending
        
    except Exception as e:
        logger.warning(f"获取热门主题失败: {e}")
        return []


def _get_category_name(category_id: str) -> str:
    """获取分类的显示名称"""
    category_names = {
        "ai_gov_usage": "美欧机构AI应用",
        "ai_china_narrative": "涉我AI舆论",
        "ai_legislation": "AI新法案",
        "ai_data_leak": "AI数据泄露",
        "cyber_vuln": "网络安全漏洞",
        "cyber_attack": "网络攻击事件",
    }
    return category_names.get(category_id, category_id)
