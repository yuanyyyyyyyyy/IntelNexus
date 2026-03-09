#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test export functionality with Chinese content"""

import os
import sys
from report_export import export_report

# 测试内容 - 包含Markdown标记和中文
test_query = "AI趋势分析"
test_content = """# 智能AI发展趋势

## 概述
这是一份关于**人工智能**发展的分析报告。

## 关键发现
1. 深度学习技术持续进化
2. *自然语言处理*应用广泛
3. **计算机视觉**领域突破

## 详细分析

### 第一点：技术方向
采用了 `PyTorch` 和 `TensorFlow` 等框架，推动了[AI研究](https://example.com)向前发展。

关键指标：
- 模型准确率：**95.3%**
- 处理速度：*10倍提升*
- 成本节省：**40%**

### 第二点：应用场景
1. 医疗诊断系统
2. 自动驾驶技术
3. 企业智能决策

## 总结
未来AI将更加融入生产生活，中文处理能力至关重要。

---
*报告完成时间：2024*
"""

def test_exports():
    """测试所有导出格式"""
    output_dir = "data/test_exports"
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("开始导出测试 - 包含中文和Markdown格式")
    print("=" * 60)
    
    # 测试Markdown
    print("\n1. 测试Markdown导出...")
    try:
        md_path = export_report(test_content, test_query, f"{output_dir}/test_report.md", format='md')
        print(f"   ✓ Markdown导出成功: {md_path}")
        # 读取验证
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if '人工智能' in content and '**' in content:
                print("   ✓ 中文内容正确保存")
            else:
                print("   ✗ 内容有问题")
    except Exception as e:
        print(f"   ✗ Markdown导出失败: {e}")
    
    # 测试PDF
    print("\n2. 测试PDF导出...")
    try:
        pdf_path = export_report(test_content, test_query, f"{output_dir}/test_report.pdf", format='pdf')
        print(f"   ✓ PDF导出成功: {pdf_path}")
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"   ✓ PDF文件大小: {size} bytes")
            if size > 1000:
                print("   ✓ 文件包含内容")
            else:
                print("   ⚠ 文件较小，可能内容缺失")
    except Exception as e:
        print(f"   ✗ PDF导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试Word
    print("\n3. 测试Word导出...")
    try:
        docx_path = export_report(test_content, test_query, f"{output_dir}/test_report.docx", format='docx')
        print(f"   ✓ Word导出成功: {docx_path}")
        if os.path.exists(docx_path):
            size = os.path.getsize(docx_path)
            print(f"   ✓ Word文件大小: {size} bytes")
            if size > 5000:
                print("   ✓ 文件包含内容")
            else:
                print("   ⚠ 文件较小，可能内容缺失")
            
            # 检查Word内容中是否有Markdown标记
            from docx import Document
            doc = Document(docx_path)
            full_text = '\n'.join([p.text for p in doc.paragraphs])
            
            if '**' in full_text or '/*' in full_text or '__' in full_text:
                print("   ✗ Word中仍然包含Markdown标记")
            else:
                print("   ✓ Word中已移除Markdown标记")
            
            if '人工智能' in full_text or '智能' in full_text:
                print("   ✓ Word中中文内容正确")
            else:
                print("   ⚠ Word中可能缺少中文内容")
                
    except Exception as e:
        print(f"   ✗ Word导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("导出测试完成")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    print("=" * 60)

if __name__ == '__main__':
    test_exports()
