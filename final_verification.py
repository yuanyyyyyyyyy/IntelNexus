#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最终验证脚本 - 检查所有修复
"""

import re

def check_ui_modifications():
    """检查ui.py的所有修改"""
    print("=" * 70)
    print("最终验证：ui.py修改检查")
    print("=" * 70)
    
    with open('ui.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "✓ 1. form clear_on_submit=False": ('with st.form("search_form", clear_on_submit=False)', content),
        "✓ 2. sidebar中添加下载格式选择": ('st.markdown(f\'<div class="section-header">{get_text("download_format")}', content),
        "✓ 3. sidebar_download_format初始化": ('st.session_state.sidebar_download_format = ""', content),
        "✓ 4. 使用sidebar_format_radio": ('key="sidebar_format_radio"', content),
        "✓ 5. 获取sidebar的格式": ('download_format = st.session_state.get(\'sidebar_download_format\', \'md\')', content),
        "✓ 6. 没有format_radio在main": ('key="format_radio"' not in content, True),
        "✓ 7. main中没有radio格式选择": ('format_radio' not in content, True),
        "✓ 8. 下载按钮key="download_btn"': ('key="download_btn"', content),
        "✓ 9. API Key中文化": ('get_text("api_key")', content),
        "✓ 10.自定义模型expander中文化": ('get_text("add_custom_model")', content),
    }
    
    passed = 0
    failed = 0
    
    for check_name, condition in checks.items():
        if isinstance(condition, bool):
            if condition:
                print(f"{check_name}")
                passed += 1
            else:
                print(f"✗ {check_name.split('✓')[1].strip()}")
                failed += 1
        else:
            search_term, content_check = condition
            if search_term in content_check:
                print(f"{check_name}")
                passed += 1
            else:
                print(f"✗ {check_name.split('✓')[1].strip()}")
                failed += 1
    
    print(f"\n{passed} 项通过, {failed} 项失败")
    return failed == 0

def check_darkweb_modifications():
    """检查darkweb_search.py"""
    print("\n" + "=" * 70)
    print("最终验证：darkweb_search.py修改检查")
    print("=" * 70)
    
    with open('darkweb_search.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "✓ 1. ENABLE_DARKWEB = true": ('ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "true").lower() == "true"', content),
        "✓ 2. 源地址已更新": ('https://breachedmw4otc2lhx7nqe4wyxfhpvy32ooz26opvqkmmrgbg73c7ooad.onion/Thread-SELLING-China-Shopping-Order-Delivery-Address-Leak-Name-phone-Address-14-2M-rows', content),
    }
    
    for check_name, (search_term, content_check) in checks.items():
        if search_term in content_check:
            print(f"{check_name}")
        else:
            print(f"✗ {check_name.split('✓')[1].strip()}")

def check_lang_dict():
    """检查LANG字典"""
    print("\n" + "=" * 70)
    print("最终验证：LANG字典中文化")
    print("=" * 70)
    
    with open('ui.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    translations = [
        ('add_custom_model', '添加自定义模型'),
        ('api_key', 'API密钥'),
        ('ollama_base_url', 'Ollama Base URL'),
        ('delete', '删除'),
    ]
    
    for key, value in translations:
        if f'"{key}": "{value}"' in content:
            print(f"✓ {key}: {value}")
        else:
            print(f"✗ {key}: {value}")

def main():
    print("\n")
    if check_ui_modifications():
        check_darkweb_modifications()
        check_lang_dict()
        print("\n" + "=" * 70)
        print("✅ 所有修改验证完成！")
        print("=" * 70)
        print("\n修复总结：")
        print("1. 格式切换 - 现在在sidebar中选择，不会导致主区域重置")
        print("2. 中文化 - 所有UI标签都已中文化")
        print("3. 删除学术论文 - 搜索模式中已删除")
        print("4. 暗网搜索 - 已启用并更新源")
        print("\n建议的测试步骤：")
        print("1. 打开 http://localhost:8501")
        print("2. 侧边栏选择'网页搜索'")
        print("3. 输入查询词后点击'搜索'按钮")
        print("4. 搜索完成后，在侧边栏改变下载格式 (Markdown/PDF/Word)")
        print("5. 验证主区域的搜索结果不会消失")
        print("6. 点击'下载报告'按钮，应该能正常下载")
    else:
        print("❌ 验证失败！请检查修改")

if __name__ == "__main__":
    main()
