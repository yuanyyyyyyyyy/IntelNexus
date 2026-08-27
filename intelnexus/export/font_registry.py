"""
统一字体注册（Font Registry）
==============================
导出链路（PDF / Word / matplotlib / 知识图谱）的字体统一入口。

项目自带思源黑体（Noto Sans SC）静态字重，位于包内 ``assets/fonts/``：

- ``NotoSansSC-Regular.ttf``  常规字重（400）
- ``NotoSansSC-Bold.ttf``     粗体字重（700，真粗体，避免伪粗）

对外提供：

- :func:`register_pdf_fonts`：向 reportlab 注册 Regular + Bold（真字重），
  并通过 ``registerFontFamily`` 关联，使段落中 ``<b>`` 命中真粗体；
  自带字体缺失时按系统字体候选链兜底。
- :func:`get_cjk_font_paths`：返回自带字体文件路径，供 matplotlib 等
  非 reportlab 场景使用。
- :data:`DOCX_CJK_FONT_NAME`：docx 中 ``w:eastAsia`` 推荐字体名。

重要：随项目的两个 TTF 内部 PostScript 名完全相同（均为
``NotoSansSC-Thin``）。reportlab 按内部名对动态字体去重（见
``pdfmetrics._dynFaceNames``），后注册的 Bold 会被 Regular 顶替，
导致伪粗。因此注册前必须覆写 ``face.name`` 为互不相同的名称。
"""

import os
from pathlib import Path

try:
    from intelnexus.core.logger import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - 日志组件不可用时的保底
    import logging

    logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 自带字体资源（相对本文件定位，与工作目录无关）
# --------------------------------------------------------------------------
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

#: 自带 Noto Sans SC 常规字重（400）
NOTO_SANS_SC_REGULAR = _FONTS_DIR / "NotoSansSC-Regular.ttf"
#: 自带 Noto Sans SC 粗体字重（700）
NOTO_SANS_SC_BOLD = _FONTS_DIR / "NotoSansSC-Bold.ttf"

#: docx ``w:eastAsia`` 使用的中文字体名。
#: docx 只按名称引用字体、不内嵌字体文件，因此不涉及字体授权；
#: 接收方系统缺少该字体时，Word 会按主题自动替换为可用中文字体。
DOCX_CJK_FONT_NAME = "Source Han Sans SC"

#: matplotlib ``font.sans-serif`` 的系统字体兜底候选
MPL_SYSTEM_CJK_CANDIDATES = ["Microsoft YaHei", "SimHei", "DengXian"]

#: reportlab 系统字体兜底候选链（合并原 briefing_export / report 两处候选顺序）
_SYSTEM_FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    # Linux
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

# 已完成的注册缓存：(normal_name, bold_name) -> (normal_name, bold_name | None)
_REGISTERED = {}


def get_cjk_font_paths() -> dict:
    """返回项目自带中文字体文件路径（供 matplotlib 等场景使用）。

    Returns:
        dict: ``{"regular": Path | None, "bold": Path | None}``，
        文件不存在时对应值为 None。
    """
    return {
        "regular": NOTO_SANS_SC_REGULAR if NOTO_SANS_SC_REGULAR.exists() else None,
        "bold": NOTO_SANS_SC_BOLD if NOTO_SANS_SC_BOLD.exists() else None,
    }


def _register_family(normal_name: str, bold_name) -> None:
    """把 normal/bold 关联为同一字体族，使 ``<b>`` 能命中 Bold 字重。"""
    try:
        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        registerFontFamily(
            normal_name,
            normal=normal_name,
            bold=bold_name or normal_name,
            italic=normal_name,
            boldItalic=bold_name or normal_name,
        )
    except Exception as e:  # pragma: no cover
        logger.debug(f"registerFontFamily skipped: {e}")


def _make_ttfont(TTFont, reg_name: str, path, face_name: bytes):
    """构造 TTFont 并覆写内部 face 名。

    两个自带 TTF 的内部 PostScript 名相同（NotoSansSC-Thin），
    不覆写会被 reportlab 按内部名去重/顶替，导致伪粗。
    """
    font = TTFont(reg_name, str(path))
    try:
        from reportlab.pdfbase.ttfonts import TTFNameBytes

        font.face.name = TTFNameBytes(face_name)
    except Exception:  # pragma: no cover - 旧版 reportlab 保底
        font.face.name = face_name
    return font


def register_pdf_fonts(normal_name: str = "NotoSansSC", bold_name: str = None):
    """向 reportlab 注册中文字体（幂等，重复调用直接返回缓存结果）。

    优先注册项目自带的 Noto Sans SC Regular/Bold；自带字体缺失或注册
    失败时按系统字体候选链兜底（此时无真粗体，Bold 名为 None）。

    Args:
        normal_name: 正文字体注册名（调用方既有引用名，如 "Chinese" /
            "ChineseFont"，保持兼容）。
        bold_name: 粗体字体注册名，默认 ``normal_name + "-Bold"``。

    Returns:
        tuple: ``(normal_name, bold_name)``；bold 未注册时为
        ``(normal_name, None)``；完全无可用字体时为 ``(None, None)``。
    """
    # 先归一化 bold_name 默认值再计算缓存键，避免 ("X", None) 与
    # ("X", "X-Bold") 视为不同键导致重复注册。
    bold_name = bold_name or (normal_name + "-Bold")

    key = (normal_name, bold_name)
    if key in _REGISTERED:
        return _REGISTERED[key]
    result = (None, None)

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        _REGISTERED[key] = result
        return result

    # ---- 首选：项目自带的 Noto Sans SC（Regular + Bold 真字重）----
    if NOTO_SANS_SC_REGULAR.exists():
        try:
            pdfmetrics.registerFont(_make_ttfont(
                TTFont, normal_name, NOTO_SANS_SC_REGULAR, b"NotoSansSC-Regular"))
            result = (normal_name, None)
            if NOTO_SANS_SC_BOLD.exists():
                try:
                    pdfmetrics.registerFont(_make_ttfont(
                        TTFont, bold_name, NOTO_SANS_SC_BOLD, b"NotoSansSC-Bold"))
                    result = (normal_name, bold_name)
                except Exception as e:
                    logger.warning(f"Bundled bold font register failed: {e}")
            _register_family(normal_name, result[1])
            _REGISTERED[key] = result
            return result
        except Exception as e:
            logger.warning(f"Bundled CJK font register failed, fallback to system fonts: {e}")

    # ---- 兜底：系统字体候选链 ----
    for path in _SYSTEM_FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(normal_name, path))
            result = (normal_name, None)
            _register_family(normal_name, None)
            break
        except Exception:
            continue

    if result[0] is None:
        logger.warning("No CJK font available, PDF may not display Chinese correctly")

    _REGISTERED[key] = result
    return result
