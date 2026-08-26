"""
IntelNexus SVG图标系统
=====================
基于Morandi配色的内联SVG图标库
"""
import streamlit as st


# =============================================================================
# CSS样式
# =============================================================================
ICON_CSS = """
<style>
/* IntelNexus Icon System */
.in-icon {
  display: inline-block;
  width: 24px;
  height: 24px;
  vertical-align: middle;
  stroke-width: 2;
  fill: none;
}

/* Morandi Color Variants */
.in-icon--gray { stroke: var(--icon-gray); }
.in-icon--blue { stroke: var(--icon-blue); }
.in-icon--warm { stroke: var(--icon-warm); }
.in-icon--rose { stroke: var(--icon-rose); }
.in-icon--sage { stroke: var(--icon-sage); }
.in-icon--lavender { stroke: var(--icon-lavender); }
.in-icon--terracotta { stroke: var(--icon-terracotta); }
.in-icon--dark { stroke: var(--icon-dark); }
.in-icon--light { stroke: var(--icon-light); }

/* Status Colors */
.in-icon--success { stroke: var(--icon-success); }
.in-icon--warning { stroke: var(--icon-warning); }
.in-icon--error { stroke: var(--icon-error); }

/* Size Variants */
.in-icon--sm { width: 16px; height: 16px; }
.in-icon--md { width: 24px; height: 24px; }
.in-icon--lg { width: 32px; height: 32px; }
.in-icon--xl { width: 48px; height: 48px; }
</style>
"""


# =============================================================================
# SVG路径数据
# =============================================================================
ICONS = {
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB导航
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'search': (
        '<circle cx="12" cy="12" r="9"/>'
        '<circle cx="12" cy="12" r="1"/>'
        '<line x1="12" y1="3" x2="12" y2="6"/>'
        '<line x1="12" y1="18" x2="12" y2="21"/>'
        '<line x1="3" y1="12" x2="6" y2="12"/>'
        '<line x1="18" y1="12" x2="21" y2="12"/>'
    ),
    'briefing': (
        '<rect x="5" y="3" width="14" height="18" rx="1"/>'
        '<line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="9" y1="12" x2="15" y2="12"/>'
        '<line x1="9" y1="16" x2="12" y2="16"/>'
    ),
    'knowledge': (
        '<ellipse cx="12" cy="6" rx="8" ry="3"/>'
        '<path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6"/>'
        '<path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 操作按钮
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'investigate': (
        '<circle cx="11" cy="11" r="7"/>'
        '<line x1="16.5" y1="16.5" x2="21" y2="21"/>'
        '<line x1="11" y1="8" x2="11" y2="14"/>'
        '<line x1="8" y1="11" x2="14" y2="11"/>'
    ),
    'save': (
        '<polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>'
    ),
    'delete': (
        '<polyline points="3,6 5,6 21,6"/>'
        '<path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    'link': (
        '<path d="M10,13a5,5,0,0,0,7.54.54l3-3a5,5,0,0,0-7.07-7.07l-1.72,1.71"/>'
        '<path d="M14,11a5,5,0,0,0-7.54-.54l-3,3a5,5,0,0,0,7.07,7.07l1.71-1.71"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 反馈
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'thumbsup': (
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="8,12 11,15 16,9"/>'
    ),
    'thumbsdown': (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 状态指示
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'success': (
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="8,12 11,15 16,9"/>'
    ),
    'warning': (
        '<path d="M12,2 L22,20 L2,20 Z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/>'
        '<circle cx="12" cy="16" r="0.5" fill="currentColor"/>'
    ),
    'error': (
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
    ),
    'high': (
        '<polygon points="12,4 20,20 4,20"/>'
        '<line x1="12" y1="10" x2="12" y2="14"/>'
        '<circle cx="12" cy="17" r="0.5" fill="currentColor"/>'
    ),
    'medium': (
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<line x1="8" y1="12" x2="16" y2="12"/>'
    ),
    'low': (
        '<circle cx="12" cy="12" r="10"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 内容类型
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'entry': (
        '<rect x="5" y="3" width="14" height="18" rx="1"/>'
        '<line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="9" y1="12" x2="15" y2="12"/>'
        '<line x1="9" y1="16" x2="12" y2="16"/>'
    ),
    'result': (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="2" y1="12" x2="22" y2="12"/>'
        '<ellipse cx="12" cy="12" rx="4" ry="10"/>'
    ),
    'note': (
        '<rect x="5" y="3" width="14" height="18" rx="1"/>'
        '<path d="M9,3 L9,8 L15,8"/>'
        '<line x1="9" y1="12" x2="15" y2="12"/>'
        '<line x1="9" y1="16" x2="12" y2="16"/>'
    ),
    # 行动项清单（补定义：results.py 此前引用了不存在的 'checklist'，
    # icon() 静默回退到放大镜导致面板标题挂错图标）
    'checklist': (
        '<line x1="9" y1="6" x2="20" y2="6"/>'
        '<line x1="9" y1="12" x2="20" y2="12"/>'
        '<line x1="9" y1="18" x2="20" y2="18"/>'
        '<polyline points="4,5.5 4.8,6.3 6.3,4.8"/>'
        '<polyline points="4,11.5 4.8,12.3 6.3,10.8"/>'
        '<polyline points="4,17.5 4.8,18.3 6.3,16.8"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 情报分类
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'govt': (
        '<path d="M3,21 L3,10 L12,3 L21,10 L21,21"/>'
        '<rect x="6" y="10" width="3" height="11"/>'
        '<rect x="10.5" y="10" width="3" height="11"/>'
        '<rect x="15" y="10" width="3" height="11"/>'
        '<line x1="1" y1="21" x2="23" y2="21"/>'
    ),
    'china': (
        '<polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>'
    ),
    'legislation': (
        '<line x1="12" y1="2" x2="12" y2="22"/>'
        '<circle cx="6" cy="8" r="3"/>'
        '<circle cx="18" cy="8" r="3"/>'
        '<path d="M6,11 L18,11"/>'
        '<path d="M4,17 L20,17"/>'
    ),
    'leak': (
        '<rect x="5" y="11" width="14" height="10" rx="2"/>'
        '<path d="M8,11 V8 a4,4,0,0,1,8,0 v3"/>'
        '<circle cx="12" cy="16" r="1.5"/>'
    ),
    'vuln': (
        '<path d="M12,2 L22,20 L2,20 Z"/>'
        '<circle cx="12" cy="13" r="2"/>'
        '<line x1="12" y1="8" x2="12" y2="10"/>'
    ),
    'attack': (
        '<polygon points="13,2 3,14 12,14 11,22 21,10 12,10"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 分析/数据
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'chart': (
        '<rect x="3" y="12" width="4" height="9"/>'
        '<rect x="10" y="7" width="4" height="14"/>'
        '<rect x="17" y="3" width="4" height="18"/>'
    ),
    'trend': (
        '<polyline points="22,7 13.5,15.5 8.5,10.5 2,17"/>'
        '<polyline points="16,7 22,7 22,13"/>'
    ),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 导航/工具
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'expand': (
        '<polyline points="6,9 12,15 18,9"/>'
    ),
    'collapse': (
        '<polyline points="6,15 12,9 18,15"/>'
    ),
    'settings': (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>'
    ),
    'info': (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="16" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12.01" y2="8"/>'
    ),
}


# =============================================================================
# 辅助函数
# =============================================================================
def icon(name: str, size: str = "md", color: str = "gray", css_class: str = "") -> str:
    """
    渲染SVG图标
    
    Args:
        name: 图标名称 (如 'search', 'briefing')
        size: 尺寸 'sm'(16px), 'md'(24px), 'lg'(32px), 'xl'(48px)
        color: Morandi颜色 ('gray', 'blue', 'warm', 'rose', 'sage', 'lavender', 'terracotta', 'dark', 'light')
        css_class: 额外CSS类
    
    Returns:
        HTML字符串包含内联SVG
    """
    svg = ICONS.get(name, ICONS['search'])
    classes = f"in-icon in-icon--{size} in-icon--{color} {css_class}".strip()
    return f'<svg class="{classes}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">{svg}</svg>'


def render_icon_css():
    """注入图标CSS到页面"""
    st.markdown(ICON_CSS, unsafe_allow_html=True)


def status_icon(status: str, size: str = "md") -> str:
    """
    渲染状态图标
    
    Args:
        status: 状态 ('success', 'warning', 'error', 'high', 'medium', 'low')
        size: 尺寸
    """
    color_map = {
        'success': 'sage',
        'warning': 'warning',
        'error': 'error',
        'high': 'terracotta',
        'medium': 'warm',
        'low': 'light',
    }
    color = color_map.get(status, 'gray')
    return icon(status, size=size, color=color)


def category_icon(category_id: str, size: str = "md") -> str:
    """
    渲染分类图标
    
    Args:
        category_id: 分类ID
        size: 尺寸
    """
    category_map = {
        'ai_gov_usage': ('govt', 'blue'),
        'ai_china_narrative': ('china', 'terracotta'),
        'ai_legislation': ('legislation', 'warm'),
        'ai_data_leak': ('leak', 'sage'),
        'cyber_vuln': ('vuln', 'warning'),
        'cyber_attack': ('attack', 'error'),
    }
    icon_name, color = category_map.get(category_id, ('info', 'gray'))
    return icon(icon_name, size=size, color=color)
