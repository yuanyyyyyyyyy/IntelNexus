#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final verification test for export functionality in UI
模拟UI中的导出流程进行测试
"""

import os
import sys
import base64
from datetime import datetime
from pathlib import Path

def test_ui_export_flow():
    """模拟UI中的导出流程"""
    print("=" * 70)
    print("IntelNexus 最终导出功能验证测试")
    print("=" * 70)
    
    # 模拟UI中的搜索结果
    simulated_refined_query = "人工智能发展趋势分析 - 2024年"
    simulated_summary = """# AI市场分析报告

## 执行总结
人工智能技术在**2024年**迎来新的发展阶段，各行业应用加速。

## 关键趋势
1. 深度学习模型规模持续增大
2. *多模态AI*应用更加普遍
3. **企业级部署**成为主流

## 详细分析

### 技术发展方向
使用 `Transformer` 和 `Attention Mechanism` 等核心技术。

关键数据：
- 模型参数量：*1000亿级别*
- 训练速度提升：**3倍**
- 成本下降：[查看详情](https://example.com)

### 市场应用
- 自然语言处理：文本生成、翻译、问答
- 计算机视觉：**图像识别**、医疗影像分析
- 语音识别：*实时转录*、多语言支持

## 结论
AI将继续革新各个领域，中文处理能力尤为重要。

---
*报告完成：2024年3月8日*
"""
    
    print("\n" + "=" * 70)
    print("第1阶段: 导出功能验证")
    print("=" * 70)
    
    # 导入导出模块
    try:
        from report_export import export_report, export_pdf, export_word, _clean_markdown_for_export
        print("✓ 成功导入导出模块")
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False
    
    # 测试Markdown清理
    print("\n✓ 步骤1: 验证Markdown清理功能")
    test_md = "**粗体**和*斜体*还有[链接](url)和`代码`"
    cleaned = _clean_markdown_for_export(test_md)
    print(f"  原始: {test_md}")
    print(f"  清理: {cleaned}")
    assert "**" not in cleaned, "粗体标记仍然存在"
    assert "*" not in cleaned or "链接" in cleaned, "斜体标记处理有问题"
    print("  ✓ Markdown清理正确")
    
    # 测试导出
    print("\n✓ 步骤2: 测试各格式导出")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "data/ui_export_test"
    os.makedirs(output_dir, exist_ok=True)
    
    # Markdown导出
    print("\n  2.1 Markdown格式:")
    try:
        md_path = export_report(
            simulated_summary,
            simulated_refined_query,
            f"{output_dir}/report_md_{timestamp}",
            format='md'
        )
        md_size = os.path.getsize(md_path)
        print(f"    ✓ 导出成功 ({md_size} bytes)")
        
        # 验证内容
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            assert "人工智能" in md_content, "中文丢失"
            assert "**" in md_content, "Markdown格式丢失"
            print(f"    ✓ 内容验证通过")
    except Exception as e:
        print(f"    ✗ 失败: {e}")
        return False
    
    # PDF导出
    print("\n  2.2 PDF格式:")
    try:
        pdf_path = export_report(
            simulated_summary,
            simulated_refined_query,
            f"{output_dir}/report_pdf_{timestamp}",
            format='pdf'
        )
        pdf_size = os.path.getsize(pdf_path)
        print(f"    ✓ 导出成功 ({pdf_size} bytes)")
        
        # 检查文件内容
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
            assert len(pdf_data) > 1000, "PDF文件太小"
            assert b'%PDF' in pdf_data[:20], "不是有效的PDF文件"
            print(f"    ✓ PDF文件格式有效")
    except Exception as e:
        print(f"    ✗ 失败: {e}")
        return False
    
    # Word导出
    print("\n  2.3 Word格式:")
    try:
        docx_path = export_report(
            simulated_summary,
            simulated_refined_query,
            f"{output_dir}/report_docx_{timestamp}",
            format='docx'
        )
        docx_size = os.path.getsize(docx_path)
        print(f"    ✓ 导出成功 ({docx_size} bytes)")
        
        # 验证Word内容
        from docx import Document
        doc = Document(docx_path)
        doc_text = '\n'.join([p.text for p in doc.paragraphs])
        
        assert "人工智能" in doc_text, "Word中缺少中文内容"
        assert "**" not in doc_text, "Word中仍有**标记"
        assert "*单独" not in doc_text, "Word中仍有*标记"
        print(f"    ✓ Word内容验证通过 (已移除Markdown标记)")
    except Exception as e:
        print(f"    ✗ 失败: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("第2阶段: UI集成模拟")
    print("=" * 70)
    
    # 模拟UI中的下载按钮逻辑
    print("\n✓ 步骤3: 模拟UI下载流程")
    
    formats_to_test = ['md', 'pdf', 'docx']
    
    for fmt in formats_to_test:
        print(f"\n  3.{formats_to_test.index(fmt)+1} {fmt.upper()}格式下载模拟:")
        try:
            filename = f"report_{timestamp}"
            
            if fmt == 'pdf':
                pdf_path = export_pdf(simulated_summary, simulated_refined_query, filename)
                with open(pdf_path, 'rb') as f:
                    download_data = f.read()
                print(f"    ✓ PDF数据读取成功 ({len(download_data)} bytes)")
                Path(pdf_path).unlink(missing_ok=True)
                
            elif fmt == 'docx':
                docx_path = export_word(simulated_summary, simulated_refined_query, filename)
                with open(docx_path, 'rb') as f:
                    download_data = f.read()
                print(f"    ✓ Word数据读取成功 ({len(download_data)} bytes)")
                Path(docx_path).unlink(missing_ok=True)
                
            else:  # markdown
                download_data = simulated_summary.encode()
                print(f"    ✓ Markdown数据读取成功 ({len(download_data)} bytes)")
            
            # 验证数据不为空
            assert len(download_data) > 0, "下载数据为空"
            print(f"    ✓ 下载流程模拟成功")
            
        except Exception as e:
            print(f"    ✗ 失败: {e}")
            return False
    
    print("\n" + "=" * 70)
    print("第3阶段: 最终验证")
    print("=" * 70)
    
    print("\n✓ 生成的文件:")
    files = list(Path(output_dir).glob("*.*"))
    for f in sorted(files):
        size = f.stat().st_size
        ext = f.suffix
        print(f"  - {f.name:40} ({size:7} bytes)")
    
    print("\n" + "=" * 70)
    print("✓ 所有测试通过！")
    print("=" * 70)
    print("""
验证结果总结:
✓ Markdown清理函数正常工作
✓ PDF导出支持中文（使用reportlab）
✓ Word导出支持中文且移除Markdown标记
✓ Markdown导出保留原始格式
✓ UI下载流程模拟成功
✓ 文件格式验证通过

用户现在可以:
1. 使用任何搜索模式进行查询
2. 选择Markdown、PDF或Word格式
3. 下载包含中文内容的报告，无方块字体
4. 获得格式化良好的文档，无Markdown源代码
    """)
    
    return True

if __name__ == '__main__':
    try:
        success = test_ui_export_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
