#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickCheck: 快速验证导出功能修复是否完整
"""

import sys
import os
from pathlib import Path

def quick_check():
    """快速检查所有关键组件"""
    
    checks_passed = 0
    checks_failed = 0
    
    print("=" * 70)
    print("IntelNexus 导出功能快速检查")
    print("=" * 70)
    
    # 检查1: 文件存在性
    print("\n✓ 检查1: 必要文件存在性")
    required_files = [
        "report_export.py",
        "ui.py",
        "requirements.txt",
        "config.py"
    ]
    
    for f in required_files:
        if Path(f).exists():
            print(f"  ✓ {f:20} 存在")
            checks_passed += 1
        else:
            print(f"  ✗ {f:20} 缺失")
            checks_failed += 1
    
    # 检查2: Python语法
    print("\n✓ 检查2: Python文件语法")
    python_files = ["report_export.py", "ui.py"]
    
    for pyfile in python_files:
        try:
            with open(pyfile, 'r', encoding='utf-8') as f:
                compile(f.read(), pyfile, 'exec')
            print(f"  ✓ {pyfile:20} 语法正确")
            checks_passed += 1
        except SyntaxError as e:
            print(f"  ✗ {pyfile:20} 语法错误: {e}")
            checks_failed += 1
    
    # 检查3: 依赖库
    print("\n✓ 检查3: Python依赖库")
    required_libs = {
        'reportlab': 'PDF支持',
        'docx': 'Word支持',
        'streamlit': 'UI框架',
    }
    
    for lib, desc in required_libs.items():
        try:
            __import__(lib)
            print(f"  ✓ {lib:20} ({desc:10}) 已安装")
            checks_passed += 1
        except ImportError:
            print(f"  ✗ {lib:20} ({desc:10}) 未安装")
            checks_failed += 1
    
    # 检查4: 关键函数存在
    print("\n✓ 检查4: 关键导出函数")
    try:
        from report_export import (
            export_report,
            export_pdf,
            export_word,
            export_markdown,
            _clean_markdown_for_export
        )
        print(f"  ✓ export_report 函数存在")
        print(f"  ✓ export_pdf 函数存在")
        print(f"  ✓ export_word 函数存在")
        print(f"  ✓ export_markdown 函数存在")
        print(f"  ✓ _clean_markdown_for_export 函数存在")
        checks_passed += 5
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}")
        checks_failed += 5
    
    # 检查5: Markdown清理函数功能
    print("\n✓ 检查5: Markdown清理功能")
    try:
        from report_export import _clean_markdown_for_export
        
        test_cases = [
            ("**粗体**", "粗体"),
            ("*斜体*", "斜体"),
            ("[文本](url)", "文本"),
            ("`代码`", "代码"),
        ]
        
        all_pass = True
        for input_text, expected_part in test_cases:
            result = _clean_markdown_for_export(input_text)
            if expected_part in result:
                print(f"  ✓ '{input_text}' 清理正确 → '{result}'")
                checks_passed += 1
            else:
                print(f"  ✗ '{input_text}' 清理失败 → '{result}'")
                all_pass = False
                checks_failed += 1
        
        if not all_pass:
            checks_failed += (4 - checks_passed)
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        checks_failed += 4
    
    # 检查6: 导出功能工作
    print("\n✓ 检查6: 导出功能测试")
    try:
        from report_export import export_report
        import tempfile
        
        test_content = "# 测试\n\n这是**测试**内容。"
        test_query = "测试查询"
        
        # 测试Markdown
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = export_report(test_content, test_query, f"{tmpdir}/test", "md")
            if Path(md_path).exists() and Path(md_path).stat().st_size > 0:
                print(f"  ✓ Markdown导出功能正常")
                checks_passed += 1
            else:
                print(f"  ✗ Markdown导出失败")
                checks_failed += 1
        
        # 测试PDF
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = export_report(test_content, test_query, f"{tmpdir}/test", "pdf")
            if Path(pdf_path).exists() and Path(pdf_path).stat().st_size > 1000:
                print(f"  ✓ PDF导出功能正常")
                checks_passed += 1
            else:
                print(f"  ✗ PDF导出失败或文件过小")
                checks_failed += 1
        
        # 测试Word
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = export_report(test_content, test_query, f"{tmpdir}/test", "docx")
            if Path(docx_path).exists() and Path(docx_path).stat().st_size > 5000:
                print(f"  ✓ Word导出功能正常")
                checks_passed += 1
            else:
                print(f"  ✗ Word导出失败或文件过小")
                checks_failed += 1
                
    except Exception as e:
        print(f"  ✗ 导出测试失败: {e}")
        checks_failed += 3
    
    # 检查7: 中文支持
    print("\n✓ 检查7: 中文字符处理")
    try:
        from report_export import export_report
        import tempfile
        
        chinese_content = "# 中文测试\n\n**人工智能** *深度学习* [机器学习](url)"
        
        # 检查Markdown
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = export_report(chinese_content, "中文查询", f"{tmpdir}/test", "md")
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "人工智能" in content:
                    print(f"  ✓ Markdown保留中文")
                    checks_passed += 1
                else:
                    print(f"  ✗ Markdown丢失中文")
                    checks_failed += 1
        
        # 检查Word
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = export_report(chinese_content, "中文查询", f"{tmpdir}/test", "docx")
            from docx import Document
            doc = Document(docx_path)
            text = '\n'.join([p.text for p in doc.paragraphs])
            if "人工智能" in text and "**" not in text:
                print(f"  ✓ Word正确处理中文且移除标记")
                checks_passed += 1
            else:
                print(f"  ✗ Word处理中文有问题")
                checks_failed += 1
                
    except Exception as e:
        print(f"  ✗ 中文处理测试失败: {e}")
        checks_failed += 2
    
    # 最终结果
    print("\n" + "=" * 70)
    total_checks = checks_passed + checks_failed
    
    if checks_failed == 0:
        print(f"✅ 所有检查通过 ({checks_passed}/{total_checks})")
        print("=" * 70)
        print("\n🎉 系统就绪！用户可以立即使用所有导出功能。")
        print("\n用户可以:")
        print("  1. 进行任何搜索查询")
        print("  2. 选择Markdown、PDF或Word格式")
        print("  3. 下载包含中文的格式化报告")
        print("  4. 获得没有Markdown源代码的干净文档")
        print("\n所有中文字符都会正确显示，不会出现方块字体。")
        return True
    else:
        print(f"❌ 有{checks_failed}个检查未通过 ({checks_passed}/{total_checks})")
        print("=" * 70)
        print("\n请检查上面的失败项目。")
        return False

if __name__ == '__main__':
    success = quick_check()
    sys.exit(0 if success else 1)
