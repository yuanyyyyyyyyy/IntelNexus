"""
偏好学习模块
============
基于用户反馈调整推送权重，实现个性化简报
"""
from typing import Dict, List
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


def compute_category_weights(subscriber_id: str) -> Dict[str, float]:
    """
    基于反馈历史计算分类权重
    
    权重公式：1.0 + (positive - negative) / total * 0.5
    范围：[0.5, 1.5]
    
    Args:
        subscriber_id: 订阅者ID
        
    Returns:
        Dict[str, float]: 分类权重字典 {category_id: weight}
    """
    try:
        from intelnexus.config.feedback import get_all_category_feedback
        from intelnexus.config.subscriptions import get_subscriber
        
        # 获取订阅者关注的分类
        subscriber = get_subscriber(subscriber_id)
        if not subscriber:
            return {}
        
        categories = subscriber.get("categories", [])
        
        # 获取所有分类反馈
        all_feedback = get_all_category_feedback()
        
        weights = {}
        for cat in categories:
            if cat in all_feedback:
                feedback = all_feedback[cat]
                up = feedback.get("up", 0)
                down = feedback.get("down", 0)
                total = up + down
                
                if total > 0:
                    # 基础权重1.0，根据反馈调整±0.5
                    weight = 1.0 + (up - down) / total * 0.5
                    # 限制在[0.5, 1.5]范围内
                    weight = max(0.5, min(1.5, weight))
                else:
                    weight = 1.0
                
                weights[cat] = weight
            else:
                weights[cat] = 1.0
        
        return weights
        
    except Exception as e:
        logger.warning(f"计算分类权重失败: {e}")
        return {}


def compute_source_weights(subscriber_id: str) -> Dict[str, float]:
    """
    基于反馈历史计算来源权重
    
    Args:
        subscriber_id: 订阅者ID
        
    Returns:
        Dict[str, float]: 来源权重字典 {source: weight}
    """
    try:
        from intelnexus.config.feedback import get_user_behavior
        
        behavior = get_user_behavior(subscriber_id)
        clicks = behavior.get("clicks", [])
        
        # 统计各来源点击次数
        source_counts = {}
        for click in clicks:
            source = click.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        
        if not source_counts:
            return {}
        
        # 归一化为权重
        max_count = max(source_counts.values())
        weights = {}
        for source, count in source_counts.items():
            weights[source] = 0.5 + (count / max_count) * 0.5  # 范围[0.5, 1.0]
        
        return weights
        
    except Exception as e:
        logger.warning(f"计算来源权重失败: {e}")
        return {}


def get_personalized_categories(subscriber_id: str) -> List[str]:
    """
    获取个性化分类列表（按权重排序）
    
    Args:
        subscriber_id: 订阅者ID
        
    Returns:
        List[str]: 排序后的分类列表
    """
    weights = compute_category_weights(subscriber_id)
    if not weights:
        # 无权重数据，返回原始顺序
        try:
            from intelnexus.config.subscriptions import get_subscriber
            subscriber = get_subscriber(subscriber_id)
            return subscriber.get("categories", []) if subscriber else []
        except Exception:
            return []
    
    # 按权重降序排序
    sorted_cats = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, _ in sorted_cats]


def filter_briefing_by_engagement(briefing_content: str, subscriber_id: str) -> str:
    """
    基于参与度过滤简报内容
    
    高权重分类的内容优先展示
    
    Args:
        briefing_content: 简报内容（Markdown格式）
        subscriber_id: 订阅者ID
        
    Returns:
        str: 过滤后的简报内容
    """
    try:
        weights = compute_category_weights(subscriber_id)
        if not weights:
            return briefing_content
        
        # 解析简报内容（按## sections分割）
        lines = briefing_content.split('\n')
        sections = []
        current_section = []
        current_category = None
        
        for line in lines:
            if line.startswith('## '):
                # 保存上一个section
                if current_section:
                    sections.append({
                        'category': current_category,
                        'content': '\n'.join(current_section)
                    })
                current_section = [line]
                # 尝试从标题提取分类
                title = line[3:].strip().lower()
                current_category = _extract_category_from_title(title)
            else:
                current_section.append(line)
        
        # 保存最后一个section
        if current_section:
            sections.append({
                'category': current_category,
                'content': '\n'.join(current_section)
            })
        
        # 按权重排序sections
        def get_section_weight(section):
            cat = section.get('category')
            if cat and cat in weights:
                return weights[cat]
            return 0.5  # 默认权重
        
        sorted_sections = sorted(sections, key=get_section_weight, reverse=True)
        
        # 重新组合内容
        return '\n\n'.join(s['content'] for s in sorted_sections)
        
    except Exception as e:
        logger.warning(f"基于参与度过滤简报失败: {e}")
        return briefing_content


def _extract_category_from_title(title: str) -> str:
    """从标题提取分类"""
    category_keywords = {
        "ai_gov_usage": ["政府", "机构", "gov", "government"],
        "ai_china_narrative": ["中国", "涉华", "china"],
        "ai_legislation": ["法规", "法案", "legislation", "law"],
        "ai_data_leak": ["泄露", "数据", "leak", "breach"],
        "cyber_vuln": ["漏洞", "vulnerability", "vuln"],
        "cyber_attack": ["攻击", "attack", "cyber"],
    }
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in title:
                return category
    
    return None


def get_engagement_score(subscriber_id: str) -> float:
    """
    计算订阅者综合参与度评分
    
    范围：[0.0, 1.0]
    
    Args:
        subscriber_id: 订阅者ID
        
    Returns:
        float: 参与度评分
    """
    try:
        from intelnexus.config.feedback import get_user_behavior
        
        behavior = get_user_behavior(subscriber_id)
        clicks = len(behavior.get("clicks", []))
        feedback = len(behavior.get("feedback", []))
        
        # 简单评分：点击+反馈的对数归一化
        import math
        raw_score = clicks * 0.3 + feedback * 0.7
        normalized = min(1.0, math.log1p(raw_score) / math.log1p(100))
        
        return normalized
        
    except Exception as e:
        logger.warning(f"计算参与度评分失败: {e}")
        return 0.0
