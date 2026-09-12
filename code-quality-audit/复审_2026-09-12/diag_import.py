# -*- coding: utf-8 -*-
"""诊断 sprite_loader 导入失败原因"""
import sys
import os
import traceback

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

print("cwd:", os.getcwd())
print("modules in path:", os.path.join(ROOT, "ralsei_pet", "modules") in sys.path)
print("sys.modules has sprite_loader:", "sprite_loader" in sys.modules)

try:
    import sprite_loader
    print("import OK")
except Exception:
    traceback.print_exc()
