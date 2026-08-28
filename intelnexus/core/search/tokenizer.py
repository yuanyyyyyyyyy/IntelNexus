"""统一中文分词接口（jieba 优先，bi-gram 兜底）。

设计目标：
- 开发环境走 jieba 精确分词（"送免费模型额度" → ["送", "免费", "模型", "额度"]）
- EXE 打包环境若未包含 jieba 词典，自动降级为 bi-gram（保持可用）
- 模块级单例初始化，避免 Streamlit rerun 重复加载
"""

import threading
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# ────────────────────────────────────────────────────────────────────────
# jieba 可选导入 + 模块级初始化
# ────────────────────────────────────────────────────────────────────────
_jieba_available = False
_jieba_lock = threading.Lock()
_jieba_initialized = False


def _try_import_jieba() -> bool:
    """尝试导入并初始化 jieba（双检锁，仅执行一次）。"""
    global _jieba_available, _jieba_initialized
    if _jieba_initialized:
        return _jieba_available
    with _jieba_lock:
        if _jieba_initialized:
            return _jieba_available
        try:
            import jieba
            jieba.initialize()
            _jieba_available = True
            logger.info("jieba 分词器初始化成功")
        except Exception as e:
            _jieba_available = False
            logger.info(f"jieba 不可用（{type(e).__name__}），降级为 bi-gram 分词")
        _jieba_initialized = True
        return _jieba_available


# 模块导入时即尝试初始化（Streamlit 进程级只执行一次）
_try_import_jieba()


# ────────────────────────────────────────────────────────────────────────
# bi-gram 兜底分词
# ────────────────────────────────────────────────────────────────────────
def _cjk_bigrams(text: str) -> list:
    """对中文文本生成 2 字滑动窗口 bi-gram 列表（jieba 不可用时的兜底方案）。

    例："送免费模型额度" → ["送免", "免费", "费模", "模型", "型额", "额度"]
    仅当文本长度 >= 3 时才生成（2 字及以下本身就是最小单元）。
    """
    if len(text) < 3:
        return []
    return [text[i:i + 2] for i in range(len(text) - 1)]


def _has_cjk(text: str) -> bool:
    """判断文本是否包含中日韩字符（CJK Unified Ideographs 范围）。"""
    return any('\u4e00' <= ch <= '\u9fff' for ch in text)


# ────────────────────────────────────────────────────────────────────────
# 统一分词接口
# ────────────────────────────────────────────────────────────────────────
def tokenize(text: str) -> list:
    """将文本切分为词列表。

    - jieba 可用时：精确分词（"送免费模型额度" → ["送", "免费", "模型", "额度"]）
    - jieba 不可用时：bi-gram 兜底（"送免费模型额度" → ["送免", "免费", "费模", ...]）
    - 纯英文/数字文本：按空白和标点切分

    Args:
        text: 待分词文本

    Returns:
        词列表（未去重、未过滤停用词，由调用方处理）
    """
    if not text:
        return []

    # 纯 ASCII 文本（英文/数字/符号）：按空白和标点切分
    if not _has_cjk(text):
        import re
        return [t for t in re.split(r"[\s,，。、;；]+", text) if t.strip()]

    # 含 CJK 字符：优先 jieba，降级 bi-gram
    if _jieba_available:
        import jieba
        return [w for w in jieba.cut(text) if w.strip()]
    else:
        # bi-gram 兜底：先按空白/标点切出片段，再对含中文的长片段生成 bi-gram
        import re
        tokens = []
        for segment in re.split(r"[\s,，。、;；]+", text):
            segment = segment.strip()
            if not segment:
                continue
            if _has_cjk(segment) and len(segment) >= 3:
                tokens.extend(_cjk_bigrams(segment))
            else:
                tokens.append(segment)
        return tokens
