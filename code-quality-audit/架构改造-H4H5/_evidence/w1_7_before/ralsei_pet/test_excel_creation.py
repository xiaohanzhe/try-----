#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试Excel创建功能的简单脚本
"""

import sys
import os
import time

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath('.'))

print("测试Excel创建功能...")

try:
    # 导入DesktopInteraction类
    from modules.desktop_interaction import DesktopInteraction
    
    # 创建DesktopInteraction实例
    desktop = DesktopInteraction(None)
    
    # 测试创建新Excel文件
    print("\n1. 测试创建新Excel文件...")
    file_name = f"测试人名表_{int(time.time())}"
    excel_path = desktop.create_new_excel(file_name)
    
    if excel_path:
        print(f"   ✓ 成功创建Excel文件: {excel_path}")
        
        # 测试写入表头
        print("\n2. 测试写入表头...")
        result = desktop.excel_control(
            action="write_data",
            excel_path=excel_path,
            cell_range="A1",
            data="姓名"
        )
        if result:
            print("   ✓ 成功写入表头")
        else:
            print("   ✗ 写入表头失败")
        
        # 测试写入人名数据
        print("\n3. 测试写入人名数据...")
        names = ["张三", "李四", "王五", "赵六", "钱七", "孙八"]
        all_success = True
        for i, name in enumerate(names, start=2):
            result = desktop.excel_control(
                action="write_data",
                excel_path=excel_path,
                cell_range=f"A{i}",
                data=name
            )
            if not result:
                all_success = False
        
        if all_success:
            print(f"   ✓ 成功写入所有人名: {', '.join(names)}")
        else:
            print("   ✗ 写入人名数据失败")
        
        # 测试自动调整列宽
        print("\n4. 测试自动调整列宽...")
        result = desktop.excel_control(
            action="auto_fit",
            excel_path=excel_path
        )
        if result:
            print("   ✓ 成功调整列宽")
        else:
            print("   ✗ 调整列宽失败")
        
        # 测试保存文件
        print("\n5. 测试保存文件...")
        result = desktop.excel_control(
            action="save",
            excel_path=excel_path
        )
        if result:
            print("   ✓ 成功保存文件")
        else:
            print("   ✗ 保存文件失败")
        
        print(f"\n✓ 所有测试完成！已在桌面上创建了名为'{file_name}.xlsx'的人名表")
    else:
        print("✗ 创建Excel文件失败")
        
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
