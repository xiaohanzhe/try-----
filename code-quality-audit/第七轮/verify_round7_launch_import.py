# -*- coding: utf-8 -*-
"""第七轮回归：文档化启动方式不再崩溃（只读，不改动项目文件）。

背景（第七轮发现）：
  `modules/desktop_interaction.py` 顶层有一句**未加保护**的
  `from logger_utils import get_logger`；而 `logger_utils.py` 本身位于 `modules/`。
  `src/main.py` 此前只把 project_root（ralsei_pet/）放进 sys.path，**没有**放
  `modules/`，于是按 README 记载的 `cd src && python main.py` 启动时，
  会在 import 期直接：

      File "src/main.py", line 98, in <module>
        from modules.desktop_interaction import DesktopInteraction
      File "modules/desktop_interaction.py", line 19, in <module>
        from logger_utils import get_logger
      ModuleNotFoundError: No module named 'logger_utils'

**为什么之前的回归套件抓不到**：G2 的每一个套件都在 sys.path 里预置了
`src/` **和** `modules/`（见 `code-quality-audit/第六轮/verify_round6_fixes.py`
第 20-22 行），恰好掩盖了这个差异——真实启动路径里 `modules/` 并不在 sys.path 上。
本套件专门以"只放 src/"的方式起一个**真实子进程**去 import main，堵住这个盲区。

修复（第七轮）：
  1. `modules/desktop_interaction.py`：把该导入包进 try/except，降级到 logging
     （与其余 20 个 modules/*.py 的写法一致）；
  2. `src/main.py`：把 `ralsei_pet/modules` 追加进 sys.path，让"真实" logger_utils
     （带文件 handler）可被解析。用 append 而非 insert，保证标准库优先。
"""
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BASE = os.path.join(ROOT, 'ralsei_pet')
MAIN_SRC = os.path.join(BASE, 'src', 'main.py')
DI_SRC = os.path.join(BASE, 'modules', 'desktop_interaction.py')

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  [PASS] " if ok else "  [FAIL] ") + name + ((" :: " + detail) if detail else ""))


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


print("=== R1. 真实子进程：仅 src/ 在 sys.path 时 import main 必须成功 ===")
# 这是"文档化启动"的最小复现：只把 src/ 放进 sys.path（不预置 modules/），
# 让 main 自己去补 modules/。PYTHONPATH 显式清空，避免外部环境掩盖问题。
env = dict(os.environ)
env.pop('PYTHONPATH', None)
env['QT_QPA_PLATFORM'] = 'offscreen'
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
code = (
    "import sys, os\n"
    "sys.path.insert(0, os.path.join(r'%s', 'src'))\n"
    "import main\n"
    "print('IMPORT_OK')\n"
    "print('MODULES_ON_PATH=' + str(any("
    "p.replace(os.sep, '/').rstrip('/').endswith('/modules') for p in sys.path)))\n"
) % BASE
proc = subprocess.run([sys.executable, '-c', code], cwd=BASE, env=env,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
raw = proc.stdout.decode('utf-8', 'replace')
ok_import = 'IMPORT_OK' in raw and proc.returncode == 0
check('R1 仅 src/ 在 path 时 import main 成功（文档化启动不再崩）', ok_import,
      'exit=%s' % proc.returncode)
m = re.search(r'MODULES_ON_PATH=(True|False)', raw)
check('R2 main 自身把 modules/ 加进了 sys.path', bool(m) and m.group(1) == 'True',
      'MODULES_ON_PATH=%s' % (m.group(1) if m else '缺失'))
# 若失败，输出可读的尾部帮助排查（不含时间戳以外的不稳定内容）
if not ok_import:
    tail = '\n'.join(raw.strip().splitlines()[-6:])
    check('R1-detail 子进程尾部输出', False, tail.replace('\n', ' | '))

print("=== R3. 源码级：main.py 补了 modules 路径 ===")
main_src = read(MAIN_SRC)
found_path_fix = bool(re.search(r"sys\.path\.append\(\s*_modules_dir\s*\)", main_src)) or \
    bool(re.search(r"sys\.path\.(?:insert|append)\([^)]*['\"]modules['\"]", main_src))
check('R3 main.py 源码包含把 modules 目录加入 sys.path 的逻辑', found_path_fix,
      'found=%s' % found_path_fix)

print("=== R4. 源码级：desktop_interaction 的 logger 导入已被保护 ===")
di_src = read(DI_SRC)
guarded = bool(re.search(
    r"try:\s*\n\s+from logger_utils import get_logger\s*\n\s*except ImportError",
    di_src))
check('R4 desktop_interaction.py 的 logger_utils 导入已用 try/except 包裹', guarded,
      'guarded=%s' % guarded)

print("=== R5. 全量：modules/ 下不得再出现裸的 logger_utils 顶层导入 ===")
mods_dir = os.path.join(BASE, 'modules')
bad = []
for fn in sorted(os.listdir(mods_dir)):
    if not fn.endswith('.py'):
        continue
    path = os.path.join(mods_dir, fn)
    text = read(path)
    # 顶层（行首无缩进）的 from logger_utils import / import logger_utils
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r"^(from logger_utils import|import logger_utils)\b", line):
            bad.append('%s:%d' % (fn, i))
check('R5 modules/ 下无裸的 logger_utils 顶层导入', not bad, '异常=%s' % (bad or '无'))

total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print("")
print("第七轮回归：PASS=%d FAIL=%d" % (passed, failed))
sys.exit(1 if failed else 0)
