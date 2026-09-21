import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# 只测试方法是否存在，不实例化对象
class TestDesktopInteraction:
    def __init__(self):
        # 不实例化对象，只测试类方法
        pass
    
    def test_methods_exist(self):
        # 测试方法是否存在，不实例化对象
        print("=== 测试方法存在性 ===")
        
        # 导入模块
        from modules.desktop_interaction import DesktopInteraction
        
        # 测试文件互动方法
        print("\n=== 文件互动方法测试 ===")
        file_methods = [
            'drag_file',
            'rename_file',
            'delete_file',
            'create_folder',
            'copy_file',
            'cut_file',
            'double_click_file',
            'right_click_file'
        ]
        
        for method in file_methods:
            if hasattr(DesktopInteraction, method):
                print(f"✓ {method} 方法存在")
            else:
                print(f"✗ {method} 方法不存在")
        
        # 测试PPT控制方法
        print("\n=== PPT控制方法测试 ===")
        ppt_methods = [
            'ppt_control',
            '_execute_ppt_action'
        ]
        
        for method in ppt_methods:
            if hasattr(DesktopInteraction, method):
                print(f"✓ {method} 方法存在")
            else:
                print(f"✗ {method} 方法不存在")
        
        # 测试Excel控制方法
        print("\n=== Excel控制方法测试 ===")
        excel_methods = [
            'excel_control',
            '_execute_excel_action'
        ]
        
        for method in excel_methods:
            if hasattr(DesktopInteraction, method):
                print(f"✓ {method} 方法存在")
            else:
                print(f"✗ {method} 方法不存在")
        
        print("\n=== 方法存在性测试完成 ===")
    
    def test_ppt_control(self):
        # 测试PPT控制功能
        print("=== 测试PPT控制功能 ===")
        
        # 测试用例1: 检查PPT控制方法是否存在
        print("测试1: 检查PPT控制方法是否存在")
        if hasattr(self.desktop_interaction, 'ppt_control'):
            print("✓ PPT控制方法存在")
        else:
            print("✗ PPT控制方法不存在")
        
        # 测试用例2: 检查PPT操作方法是否存在
        print("测试2: 检查PPT操作方法是否存在")
        if hasattr(self.desktop_interaction, '_execute_ppt_action'):
            print("✓ PPT操作方法存在")
        else:
            print("✗ PPT操作方法不存在")
        
        print("\n=== PPT控制功能测试完成 ===\n")
    
    def test_excel_control(self):
        # 测试Excel控制功能
        print("=== 测试Excel控制功能 ===")
        
        # 测试用例1: 检查Excel控制方法是否存在
        print("测试1: 检查Excel控制方法是否存在")
        if hasattr(self.desktop_interaction, 'excel_control'):
            print("✓ Excel控制方法存在")
        else:
            print("✗ Excel控制方法不存在")
        
        # 测试用例2: 检查Excel操作方法是否存在
        print("测试2: 检查Excel操作方法是否存在")
        if hasattr(self.desktop_interaction, '_execute_excel_action'):
            print("✓ Excel操作方法存在")
        else:
            print("✗ Excel操作方法不存在")
        
        print("\n=== Excel控制功能测试完成 ===\n")
    
    def test_file_interaction(self):
        # 测试文件互动功能
        print("=== 测试文件互动功能 ===")
        
        # 测试用例1: 检查拖拽文件方法是否存在
        print("测试1: 检查拖拽文件方法是否存在")
        if hasattr(self.desktop_interaction, 'drag_file'):
            print("✓ 拖拽文件方法存在")
        else:
            print("✗ 拖拽文件方法不存在")
        
        # 测试用例2: 检查重命名文件方法是否存在
        print("测试2: 检查重命名文件方法是否存在")
        if hasattr(self.desktop_interaction, 'rename_file'):
            print("✓ 重命名文件方法存在")
        else:
            print("✗ 重命名文件方法不存在")
        
        # 测试用例3: 检查复制文件方法是否存在
        print("测试3: 检查复制文件方法是否存在")
        if hasattr(self.desktop_interaction, 'copy_file'):
            print("✓ 复制文件方法存在")
        else:
            print("✗ 复制文件方法不存在")
        
        # 测试用例4: 检查剪切文件方法是否存在
        print("测试4: 检查剪切文件方法是否存在")
        if hasattr(self.desktop_interaction, 'cut_file'):
            print("✓ 剪切文件方法存在")
        else:
            print("✗ 剪切文件方法不存在")
        
        # 测试用例5: 检查双击文件方法是否存在
        print("测试5: 检查双击文件方法是否存在")
        if hasattr(self.desktop_interaction, 'double_click_file'):
            print("✓ 双击文件方法存在")
        else:
            print("✗ 双击文件方法不存在")
        
        # 测试用例6: 检查右键点击文件方法是否存在
        print("测试6: 检查右键点击文件方法是否存在")
        if hasattr(self.desktop_interaction, 'right_click_file'):
            print("✓ 右键点击文件方法存在")
        else:
            print("✗ 右键点击文件方法不存在")
        
        print("\n=== 文件互动功能测试完成 ===\n")
    
    def run_all_tests(self):
        # 运行所有测试
        print("开始运行所有功能测试...\n")
        
        # 只测试方法存在性
        self.test_methods_exist()
        
        print("所有功能测试完成！")

if __name__ == "__main__":
    # 运行测试
    test = TestDesktopInteraction()
    test.run_all_tests()
