# -*- coding: utf-8 -*-
"""
文件 / 表格操作控制器 —— H4/H5「上帝类拆分」Wave 1 第 5 项（W1-6）。

搬出来的是什么
--------------
`RalseiPet` 里「文件 / 表格操作」这条业务线的 **4 个方法**（A 块，物理连续）：

    handle_file_operation         (144 行含 def) —— 入口：新建表格 / 填人名 / 打开表格 / 通用打开
    _open_desktop_item_by_name     (40 行含 def) —— 通用「打开 XX」分发器 → 走 spell 打开流程
    fix_excel_format               (53 行含 def) —— Excel 格式修复（换行 / 居中 / 自动列宽行高）
    fill_names_in_excel            (70 行含 def) —— 按序填人名（含"已有数据拒绝覆盖"保护）

⚠️ 本项**不含** B 块（`check_file_content` / `check_text_content` / `check_image_content`）——
它们属「**文件情感反应**」群（同群 `react_to_file_emotionally` / `follow_file` /
`react_to_file_deletion` 均在宿主），与「文件 / 表格**操作**」是两种职责。
硬并入会让一个类混装两种职责，违背 H4 拆分初衷 → 已记入跨项待办，留给 H4「文件反应」专项。
详见 `code-quality-audit/架构改造-H4H5/W1-6_开工前侦察_2026-09-20.md` §五。

口径与排期方案的核对
--------------------
* 排期方案 §5.2 表把 W1-6 写成「存活：`handle_file_operation` 4114(143) / `fix_excel_format` 4298 /
  `fill_names_in_excel` 4351 / `check_{file,text,image}_content` 8076·8100·8142」，规模「~370 行」。
  **实测（删死代码后）**：A 块 L4222–4528 = **303 方法体行 / 307 物理行**；B 块另有 79 行。
  方案表内「~370 行」与它自己下方索引自算的「399 行」**互相矛盾** → 以实测为准。
* ❗ **`scan_method_index.py` 第 4 次偏差，形态是全新的「跨区散布」**：7 个方法**不成块**，
  横跨 L4222–4584 与 L8511–8591（相距约 4000 行）→「物理连续块」这个假设本身不成立。
  且**漏标了 `_open_desktop_item_by_name`（40 行）** —— 它是 A 块的自然成员（被
  `handle_file_operation` 显式调用），只因名字不含 `file`/`excel`/`sheet` 就被前缀启发式漏掉。
  历次偏差：W1-1 漏标 / W1-4 漏标 / W1-2 误纳 / **W1-6 跨区散布**。
  ⇒ **索引只能当线索集；范围必须逐方法人工确认，并与排期方案交叉核对（两边都要验）。**

死代码处置（本轮先做）
----------------------
`create_person_name_table`（原 L4222，57 行）G1 实测 **0 引用**，且与 `handle_file_operation`
的「新建表格」分支功能重复 → 按「要么接线、要么删」**删除**（未接线）。
`check_excel_table_needs` 排期方案列为待处置死代码，实则**第六轮已随 17 个办公检查删除**
（`main.py` 有留痕注释）→ **无需处置**。

为什么是这一块（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）
--------------------------------------------------------------
本项是 Wave 1 **最后一项**，也是块内闭合度最差的一项：4 个方法没有一个共享的私有状态属性，
全靠宿主成员（`desktop_interaction` / `dialogue_ui`）+ 两条跨控制器调用
（`open_file` / `open_folder`，**留在宿主**）。本项**不搬任何状态** →
`__getattr__` 读宿主、`__setattr__` 写宿主这条既有机制**天然成立**，无需新增状态。

与兄弟控制器的互调用（**不是**互写）
-----------------------------------
`_open_desktop_item_by_name` 调 `self.open_file(path)` / `self.open_folder(path)`。
这两个方法**留在宿主**（方案表列明），且它们是 `SpellFlowController._start_open_with_spell`
的**调用方**（不是反向）→ 走宿主 `__getattr__` 第 2 条白名单（宿主类型 MRO）即可命中，
**不依赖第 3 条兄弟白名单**。与 W1-2 调 `_cast_spell_then`（真需兄弟白名单）**不同构**。

本模块的模块级 import
---------------------
  * `os` —— ⚠️ **必须**。`_open_desktop_item_by_name` L4385/4391/4392/4393/4400 用了 `os.`
    但该方法体内**没有** `import os`（其他分支的局部 `import os` 不覆盖它）→ 在 `main.py` 里靠
    **模块级** `import os`（L3）解析。搬走后模块作用域变了 → `NameError`，
    **而逐字等价断言测不出来**。这是搬运铁律 7（"裸 Attribute 根"）的又一次实例。
  * `logging` —— 见 `_log_()`。
  * ⚠️ 本块**不含** `QTimer` / `QPoint` / `time.` / `random.` → 比 W1-2 干净。
    也**因此无铁律 1（`QTimer(self)`）**：全块没有任何 `QTimer(self)` 站点。

不搬的局部 import（**保持原位**）
--------------------------------
`win32com.client`（L4231 / L4413 / L4467）、`os`（L4230 / L4276 / L4316 / L4350）、
`re`（L4368）都是**方法体内局部 import** → 一个都不动。
若把 `win32com.client` 提到模块级，会把 pywin32 变成导入期硬依赖（CI / 无 Excel 环境会崩）。

为什么不 import 任何项目内模块
-----------------------------
同 `event_speech.py` / `games_controller.py` / `video_controller.py` / `spell_controller.py` /
`hide_controller.py` 的纪律：本模块位于「初始化环」下游（`main.py` import 期就要
`from modules.file_sheet_controller import FileSheetController`），回头 import
`logger_utils` / `dialogue_ui` 会把环重新接上。
"""

import logging
import os

_log = logging.getLogger(__name__)


class FileSheetController(object):
    """文件 / 表格操作。宿主（`RalseiPet`）持有，方法通过宿主 `__getattr__` 转发壳暴露。

    与 `GamesController` / `VideoController` / `SpellFlowController` / `HideAndSeekController`
    **完全同构**：本类需要 `__getattr__`（读宿主状态）+ `__setattr__`（写宿主状态），
    因为「只搬方法不搬状态」意味着方法体里 `self.desktop_interaction` / `self.dialogue_ui` /
    `self.open_folder` 这些宿主成员一个字都没改。

    转发判据与成环防护的完整论证见 `spell_controller.py` / `games_controller.py`
    的类 docstring 与 `main.py` 的 `_CONTROLLER_ATTRS` 注释 —— 真机踩过的
    `RecursionError`（构造期崩）也记在那里，**勿回退**。
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：本项**不搬任何状态属性**，本类只借用宿主成员，不复制、不缓存。
        # 普通赋值 → `p` 进实例字典 → `self.p` 走常规查找，不会递归回 __getattr__。
        self.p = ralsei_pet

    def __getattr__(self, name):
        # 只在常规查找失败时进入。两条**显式白名单**后才回落：
        #   · 宿主实例字典（desktop_interaction / dialogue_ui / game_state …）
        #   · 宿主**类型** MRO 上的东西（open_file / open_folder /
        #     _start_open_with_spell 所在的宿主链 / QMainWindow 的 move/width …）
        # 两条都不满足 → 抛，切断「宿主也没有 → 宿主 __getattr__ → 又转回本类」的成环路径。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        if name in pet.__dict__:
            return pet.__dict__[name]
        if any(name in klass.__dict__ for klass in type(pet).__mro__):
            return getattr(pet, name)
        # 第 3 条白名单：**兄弟控制器**（与 W1-2 同构，本项当前用不到，
        # 但保留以维持"所有控制器转发壳一致"的纪律，且防止未来新增互调时静默失败）。
        for _attr in getattr(type(pet), '_CONTROLLER_ATTRS', ()):
            _ctrl = pet.__dict__.get(_attr)
            if _ctrl is None or _ctrl is self:
                continue
            if getattr(type(_ctrl), name, None) is not None:
                return getattr(_ctrl, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # ⚠️ 「逐字等价测不出来」的第二个坑（W1-4 e2e 才炸出来）。
        # 普通过赋值走 object.__setattr__ → 直接写进**控制器自己的 __dict__** →
        # 状态被劈成两份（宿主读数与控制器读数不一致，行为静默错乱）。
        # 转发判据 = 宿主**已经拥有**的名字（实例字典或 MRO 上有）——
        # 判据的关键是**能自动覆盖新状态名**（本项目最贵的坑：
        # "函数写对了但产品用不上"）。控制器**故意不允许**给自己新增业务属性。
        #
        # 本项说明：W1-6 **不写任何宿主状态**（4 个方法全是"读宿主 + 调宿主 API + 用局部变量"），
        # 故本护栏在当前代码路径上**不会被触发**；保留它是为了：
        #   (a) 与其余 4 个控制器同构（纪律一致，降低后继维护的心智负担）；
        #   (b) 防御未来有人往本类里加 `self.xxx = ...` 而静默劈裂状态。
        # 鉴别力由单元探针用"人为赋值 + 断言写回宿主"单独覆盖（见 verify_w1_6_unit.py）。
        if name != 'p':
            pet = self.__dict__.get('p')
            if pet is not None:
                if name in pet.__dict__ or any(
                        name in klass.__dict__ for klass in type(pet).__mro__):
                    setattr(pet, name, value)
                    return
        object.__setattr__(self, name, value)

    def _log_(self):
        # 取宿主 main.py 的模块级 `_log`（同一个 logger 对象）—— 见模块 docstring。
        # `_log` 不在宿主实例字典里，所以走宿主**模块**的全局变量。
        import sys
        mod = sys.modules.get(type(self.p).__module__)
        if mod is not None:
            lg = getattr(mod, '_log', None)
            if lg is not None:
                return lg
        return _log

    # ------------------------------------------------------------------
    # 文件 / 表格操作（W1-6 搬运区，**以下方法体逐字来自 main.py L4222-4528**，
    # 唯一改动一类：`_log.` → `self._log_().`（12 处），逐方法计数见施工报告）
    # ------------------------------------------------------------------

    def handle_file_operation(self, user_input):
        # 处理文件操作指令
        try:
            user_input_lower = user_input.lower()
            
            # 检查是否是新建表格的指令
            if "新建" in user_input_lower and "表格" in user_input_lower:
                # 在桌面上新建Excel表格
                import os
                import win32com.client
                desktop_path = self.desktop_interaction.desktop_path
                
                # 创建新的Excel文件
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                
                workbook = excel.Workbooks.Add()
                sheet = workbook.ActiveSheet
                
                # 保存文件
                new_file_name = "新建表格.xlsx"
                new_file_path = os.path.join(desktop_path, new_file_name)
                
                # 检查文件是否已存在，如果存在则添加数字后缀
                counter = 1
                while os.path.exists(new_file_path):
                    new_file_name = f"新建表格_{counter}.xlsx"
                    new_file_path = os.path.join(desktop_path, new_file_name)
                    counter += 1
                
                # 修复（P2）：原实现直接 SaveAs/Close/Quit，没有 finally。SaveAs 失败
                # （目标文件被 Excel 占用、桌面无写权限、磁盘满、文件名为非法字符）时
                # 异常直接抛出，excel.Quit() 永不执行 → 留下一个隐藏的 EXCEL.EXE
                # 僵尸进程，且可能锁住刚写了一半的文件。同文件的 fix_excel_format /
                # fill_names_in_excel 已按 finally 修复，此处补齐以消除不一致。
                try:
                    workbook.SaveAs(new_file_path)
                finally:
                    try:
                        workbook.Close(SaveChanges=False)
                    except Exception as e:
                        self._log_().debug("main 防御性异常（已忽略）: %s", e)
                    try:
                        excel.Quit()
                    except Exception as e:
                        self._log_().debug("main 防御性异常（已忽略）: %s", e)
                
                self.dialogue_ui.add_dialogue("ralsei", f"我已经在桌面上创建了一个新的Excel表格: {new_file_name}", "happy")
                self.dialogue_ui.show_dialogue()
                return True
            
            # 检查是否是往表格里填人名的指令
            elif "填人名" in user_input_lower and "表格" in user_input_lower:
                # 获取桌面上的Excel文件
                import os
                desktop_path = self.desktop_interaction.desktop_path
                try:
                    excel_files = [f for f in os.listdir(desktop_path) if f.endswith('.xlsx')]
                except Exception:
                    excel_files = []
                
                if not excel_files:
                    self.dialogue_ui.add_dialogue("ralsei", "桌面上没有找到Excel表格文件！", "sad")
                    self.dialogue_ui.show_dialogue()
                    return True
                
                # 选择最新的Excel文件
                try:
                    excel_files.sort(key=lambda f: os.path.getmtime(os.path.join(desktop_path, f)), reverse=True)
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
                excel_file = excel_files[0]
                excel_path = os.path.join(desktop_path, excel_file)
                
                self.dialogue_ui.add_dialogue("ralsei", f"我将往表格: {excel_file} 里填写人名！", "happy")
                
                # 默认人名列表，可以根据需要扩展
                default_names = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
                
                # 打开并填写表格
                result = self.fill_names_in_excel(excel_path, default_names)
                
                if result:
                    self.dialogue_ui.add_dialogue("ralsei", f"我已经成功往表格: {excel_file} 里填写了人名！", "happy")
                    self.dialogue_ui.add_dialogue("ralsei", f"我填写的人名是: {', '.join(default_names)}", "helpful")
                else:
                    self.dialogue_ui.add_dialogue("ralsei", f"往表格: {excel_file} 里填写人名失败了...", "sad")
                
                self.dialogue_ui.show_dialogue()
                return True
            
            # 检查是否是打开并修改表格的指令
            elif "打开" in user_input_lower and "表格" in user_input_lower:
                # 获取桌面上的Excel文件
                import os
                desktop_path = self.desktop_interaction.desktop_path
                try:
                    excel_files = [f for f in os.listdir(desktop_path) if f.endswith('.xlsx')]
                except Exception:
                    excel_files = []
                
                if not excel_files:
                    self.dialogue_ui.add_dialogue("ralsei", "桌面上没有找到Excel表格文件！", "sad")
                    self.dialogue_ui.show_dialogue()
                    return True
                
                # 选择第一个Excel文件（可以根据需要扩展为选择特定文件）
                excel_file = excel_files[0]
                excel_path = os.path.join(desktop_path, excel_file)
                
                self.dialogue_ui.add_dialogue("ralsei", f"我找到了桌面上的Excel文件: {excel_file}", "happy")
                
                # 检查是否需要修改表格
                if "对齐" in user_input_lower or "格子" in user_input_lower or "超出去" in user_input_lower:
                    self.dialogue_ui.add_dialogue("ralsei", f"我将为你打开并修改表格: {excel_file}", "helpful")
                    
                    # 打开并修改表格
                    result = self.fix_excel_format(excel_path)
                    
                    if result:
                        self.dialogue_ui.add_dialogue("ralsei", f"我已经成功修改了表格: {excel_file}！", "happy")
                        self.dialogue_ui.add_dialogue("ralsei", "我已经将任务名称和喜好对齐，并确保所有内容都完全放在格子里，没有超出！", "helpful")
                    else:
                        self.dialogue_ui.add_dialogue("ralsei", f"修改表格: {excel_file} 失败了...", "sad")
                else:
                    self.dialogue_ui.add_dialogue("ralsei", f"我将为你打开表格: {excel_file}", "happy")
                    
                    # 仅打开表格
                    import os
                    os.startfile(excel_path)
            
            # 修复：通用"打开 XX 文件/文件夹"指令——原来只有 Excel 相关分支，
            # 输入"打开 某个文件/文件夹"时不会打开任何东西（被当作普通闲聊）。
            elif "打开" in user_input_lower and "表格" not in user_input_lower:
                return self._open_desktop_item_by_name(user_input)
            
            self.dialogue_ui.show_dialogue()
            return True
        except Exception as e:
            self._log_().warning(f"处理文件操作指令失败: {e}")
            self.dialogue_ui.add_dialogue("ralsei", "处理文件操作指令失败了...", "sad")
            self.dialogue_ui.show_dialogue()
            return True

    def _open_desktop_item_by_name(self, user_input):
        """按名称匹配桌面文件/文件夹并触发 spell 打开流程。返回 True/False。"""
        import re
        # 去掉"打开/帮我打开/请打开"及结尾语气词
        text = re.sub(r'^(请|帮我)?(打开|启动|开启)\s*', '', user_input.strip())
        text = re.sub(r'[呢？。！!~～\s]+$', '', text).strip()
        if not text:
            self.dialogue_ui.add_dialogue("ralsei", "你想让我打开什么呀？", "curious")
            self.dialogue_ui.show_dialogue()
            return True
        # 刷新桌面元素后按名称匹配（真实图标 + 忽略扩展名 + 模糊包含）
        try:
            self.desktop_interaction.update_desktop_elements()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        target_lower = text.lower()
        matched = None
        for el in self.desktop_interaction.desktop_elements:
            name = el.get('name', '') or ''
            base = os.path.splitext(name)[0].lower()
            if name.lower() == target_lower or base == target_lower or (len(target_lower) >= 2 and target_lower in name.lower()):
                matched = el
                break
        if matched is None:
            # 兜底：直接按路径尝试（文本可能是绝对/相对路径）
            p = os.path.join(self.desktop_interaction.desktop_path, text)
            if os.path.exists(p):
                matched = {'type': 'folder' if os.path.isdir(p) else 'file', 'path': p}
        if matched is None:
            self.dialogue_ui.add_dialogue("ralsei", f"我在桌面上没找到叫「{text}」的东西呢，换个名字试试？", "a little confusion and cute")
            self.dialogue_ui.show_dialogue()
            return True
        # 走 spell 流程（走过去 → 施法 → 打开）
        path = matched['path']
        if matched.get('type') == 'folder' or os.path.isdir(path):
            self.open_folder(path)
        else:
            self.open_file(path)
        return True
    
    def fix_excel_format(self, excel_path):
        # 修复Excel表格格式
        # 修复：异常路径也必须释放 COM 资源（否则累积僵尸 EXCEL.EXE 并锁文件）
        excel = None
        workbook = None
        try:
            # 启动Excel并打开文件
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            
            workbook = excel.Workbooks.Open(excel_path)
            sheet = workbook.ActiveSheet
            
            # 获取使用的范围
            used_range = sheet.UsedRange
            rows = used_range.Rows.Count
            cols = used_range.Columns.Count
            
            # 设置所有单元格自动换行
            used_range.WrapText = True
            
            # 设置所有单元格居中对齐
            used_range.HorizontalAlignment = -4108  # xlCenter
            used_range.VerticalAlignment = -4108  # xlCenter
            
            # 自动调整所有列宽
            for col in range(1, cols + 1):
                sheet.Columns(col).AutoFit()
            
            # 自动调整所有行高
            for row in range(1, rows + 1):
                sheet.Rows(row).AutoFit()
            
            # 保存并关闭
            workbook.Save()
            
            return True
        except Exception as e:
            self._log_().warning(f"修复Excel格式失败: {e}")
            return False
        finally:
            try:
                if workbook is not None:
                    workbook.Close(SaveChanges=False)
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
            try:
                if excel is not None:
                    excel.Quit()
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
    
    def fill_names_in_excel(self, excel_path, names_list):
        # 往Excel表格中按顺序填写人名
        # 修复：1) 异常路径释放 COM；2) 表格已有数据时拒绝静默覆盖
        #（原实现无条件重写 A/B 两列并 Save()，会覆盖用户已有表格内容，属数据丢失风险）。
        excel = None
        workbook = None
        try:
            # 启动Excel并打开文件
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            
            workbook = excel.Workbooks.Open(excel_path)
            sheet = workbook.ActiveSheet
            
            # 覆盖保护：若已有数据（A2/B2 起任何单元格非空），拒绝覆盖并提示
            existing = False
            try:
                used = sheet.UsedRange
                if used.Rows.Count > 1 or used.Columns.Count > 1:
                    existing = True
            except Exception:
                existing = False
            if existing:
                self._log_().debug(f"文件已有内容，为避免覆盖用户数据，未填写人名: {excel_path}")
                return False
            
            # 设置表头
            sheet.Cells(1, 1).Value = "序号"
            sheet.Cells(1, 2).Value = "姓名"
            
            # 设置表头样式
            header_range = sheet.Range("A1:B1")
            header_range.Font.Bold = True
            header_range.HorizontalAlignment = -4108  # xlCenter
            header_range.VerticalAlignment = -4108  # xlCenter
            header_range.Interior.Color = 15773696  # 浅灰色背景
            
            # 填写人名数据
            for i, name in enumerate(names_list, start=2):
                sheet.Cells(i, 1).Value = i - 1  # 序号
                sheet.Cells(i, 2).Value = name  # 姓名
            
            # 设置数据区域样式
            data_range = sheet.Range(f"A1:B{len(names_list) + 1}")
            data_range.Borders.LineStyle = 1  # 添加边框
            
            # 自动调整列宽
            for col in range(1, 3):
                sheet.Columns(col).AutoFit()
            
            # 保存并关闭
            workbook.Save()
            
            return True
        except Exception as e:
            self._log_().warning(f"往Excel表格中填写人名失败: {e}")
            return False
        finally:
            try:
                if workbook is not None:
                    workbook.Close(SaveChanges=False)
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
            try:
                if excel is not None:
                    excel.Quit()
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
