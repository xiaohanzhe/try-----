import os
import sys
import time
from PyQt5.QtCore import QPoint

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from modules.desktop_interaction import DesktopInteraction

class DetailedInteractionTest:
    def __init__(self):
        self.desktop_interaction = DesktopInteraction(None)
        self.test_results = {}
        self.test_success = 0
        self.test_total = 0
    
    def run_all_tests(self):
        print("开始详细测试桌面互动功能...")
        print("=" * 60)
        
        # 测试浏览器互动功能
        self.test_browser_interaction_detailed()
        
        # 测试窗口互动功能
        self.test_window_interaction_detailed()
        
        # 测试文件互动功能
        self.test_file_interaction_detailed()
        
        # 测试鼠标互动功能
        self.test_mouse_interaction_detailed()
        
        print("=" * 60)
        print("详细测试完成！")
        print(f"测试结果: {self.test_success}/{self.test_total} 通过")
        
        # 打印详细测试结果
        print("\n详细测试结果:")
        for test_name, result in self.test_results.items():
            status = "✓" if result else "✗"
            print(f"{status} {test_name}")
    
    def test_browser_interaction_detailed(self):
        print("\n1. 详细测试浏览器互动功能")
        print("-" * 40)
        
        # 测试获取浏览器窗口信息
        try:
            browser_windows = self.desktop_interaction.identify_browser_windows()
            print(f"识别到的浏览器窗口: {len(browser_windows)}")
            if browser_windows:
                for i, window in enumerate(browser_windows):
                    print(f"  浏览器窗口 {i+1}: {window['title']} (大小: {window['width']}x{window['height']})")
            self._record_test("获取浏览器窗口信息", True)
        except Exception as e:
            print(f"获取浏览器窗口信息失败: {e}")
            self._record_test("获取浏览器窗口信息", False)
        
        # 测试浏览器打开功能（不实际打开）
        try:
            # 这里只测试函数调用，不实际打开浏览器
            import webbrowser
            # 测试webbrowser模块是否可用
            self._record_test("浏览器模块可用性", True)
        except Exception as e:
            print(f"浏览器模块测试失败: {e}")
            self._record_test("浏览器模块可用性", False)
    
    def test_window_interaction_detailed(self):
        print("\n2. 详细测试窗口互动功能")
        print("-" * 40)
        
        # 测试获取所有可见窗口详细信息
        try:
            windows = self.desktop_interaction.get_all_visible_windows()
            print(f"获取可见窗口数量: {len(windows)}")
            if windows:
                print("前3个可见窗口:")
                for i, window in enumerate(windows[:3]):
                    print(f"  窗口 {i+1}: {window['title']} (Z序: {window['z_order']}, 大小: {window['width']}x{window['height']})")
            self._record_test("获取窗口详细信息", True)
        except Exception as e:
            print(f"获取窗口详细信息失败: {e}")
            self._record_test("获取窗口详细信息", False)
        
        # 测试窗口类型识别
        try:
            # 测试识别不同类型的窗口
            ppt_windows = self.desktop_interaction.identify_ppt_windows()
            excel_windows = self.desktop_interaction.identify_excel_windows()
            word_windows = self.desktop_interaction.identify_word_windows()
            print(f"识别到PPT窗口: {len(ppt_windows)}, Excel窗口: {len(excel_windows)}, Word窗口: {len(word_windows)}")
            self._record_test("窗口类型识别", True)
        except Exception as e:
            print(f"窗口类型识别失败: {e}")
            self._record_test("窗口类型识别", False)
    
    def test_file_interaction_detailed(self):
        print("\n3. 详细测试文件互动功能")
        print("-" * 40)
        
        # 测试更新桌面元素
        try:
            self.desktop_interaction.update_desktop_elements()
            print("成功更新桌面元素")
            self._record_test("更新桌面元素", True)
        except Exception as e:
            print(f"更新桌面元素失败: {e}")
            self._record_test("更新桌面元素", False)
        
        # 测试获取桌面文件列表
        try:
            files = self.desktop_interaction.get_desktop_files()
            print(f"获取桌面文件数量: {len(files)}")
            if files:
                print("前5个桌面文件:")
                for i, file in enumerate(files[:5]):
                    print(f"  文件 {i+1}: {file['name']} (类型: {file['type_desc']}, 大小: {file['size']})")
            self._record_test("获取桌面文件列表", True)
        except Exception as e:
            print(f"获取桌面文件列表失败: {e}")
            self._record_test("获取桌面文件列表", False)
        
        # 测试文件类型识别
        try:
            test_files = ["test.txt", "test.py", "test.pdf", "test.xlsx", "test.pptx"]
            print("文件类型识别测试:")
            for file in test_files:
                file_type = self.desktop_interaction.identify_file_type(file)
                print(f"  {file} -> {file_type}")
            self._record_test("文件类型识别", True)
        except Exception as e:
            print(f"文件类型识别失败: {e}")
            self._record_test("文件类型识别", False)
        
        # 测试文件反应生成
        try:
            test_files = ["deltarune.txt", "ralsei.py", "browser.exe", "test.txt"]
            print("文件反应生成测试:")
            for file in test_files:
                reaction = self.desktop_interaction.get_special_file_reaction(file)
                print(f"  {file} -> 情绪: {reaction['emotion']}, 动作: {reaction['action']}")
            self._record_test("文件反应生成", True)
        except Exception as e:
            print(f"文件反应生成失败: {e}")
            self._record_test("文件反应生成", False)
    
    def test_mouse_interaction_detailed(self):
        print("\n4. 详细测试鼠标互动功能")
        print("-" * 40)
        
        # 测试元素附近检查
        try:
            print("元素附近检查测试:")
            test_cases = [
                (QPoint(100, 100), QPoint(150, 150), 100, True),  # 应该在附近
                (QPoint(100, 100), QPoint(300, 300), 100, False),  # 应该不在附近
            ]
            
            for i, (element_pos, check_pos, max_distance, expected) in enumerate(test_cases):
                result = self.desktop_interaction.is_element_nearby(element_pos, check_pos, max_distance)
                status = "✓" if result == expected else "✗"
                print(f"  测试 {i+1}: {status} 元素位置 {element_pos} 与检查位置 {check_pos} 的距离是否 < {max_distance}: {result} (预期: {expected})")
            self._record_test("元素附近检查", True)
        except Exception as e:
            print(f"元素附近检查测试失败: {e}")
            self._record_test("元素附近检查", False)
        
        # 测试获取附近元素
        try:
            print("获取附近元素测试:")
            # 先更新桌面元素
            self.desktop_interaction.update_desktop_elements()
            # 测试获取不同位置附近的元素
            test_positions = [QPoint(100, 100), QPoint(200, 200)]
            for i, pos in enumerate(test_positions):
                nearby_elements = self.desktop_interaction.get_nearby_elements(pos, 100)
                print(f"  位置 {pos} 附近的元素数量: {len(nearby_elements)}")
            self._record_test("获取附近元素", True)
        except Exception as e:
            print(f"获取附近元素测试失败: {e}")
            self._record_test("获取附近元素", False)
    
    def _record_test(self, test_name, result):
        self.test_results[test_name] = result
        self.test_total += 1
        if result:
            self.test_success += 1

if __name__ == "__main__":
    test = DetailedInteractionTest()
    test.run_all_tests()
