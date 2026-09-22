# -*- coding: utf-8 -*-
"""第三十四轮回归锁：移动/行为基础代码的「不许回退」项。

本套件锁三件事，都是第三十四轮严查中**实测确认**的：

  A. 假 Qt 事件钩子不许回来
     `mouseEnterEvent` / `mouseLeaveEvent` 不是 Qt 的钩子名（正确名是
     `enterEvent` / `leaveEvent`），Qt 从不派发它们，写了也永远不执行。
     第三十四轮已删除。本套件用 AST + 运行时双重判据钉死：
       ① 源码里不得再出现这两个方法定义（AST FunctionDef 名检查）；
       ② 反向控制：确认同文件其余的 Qt 钩子名**确实存在**（否则本判据无鉴别力，
          比如"我把所有事件钩子都删了"也会 PASS）。
       ③ 真机判据：QWidget 自身没有 mouseEnterEvent 属性、有 enterEvent 属性。

  B. 死字段 `fall_start_time` 不许回来
     它曾有 6 处写点、0 处读点（AST 双向扫描确认），且 init 里三种类型
     （None / 0 / float）并存。第三十四轮已整体删除。本套件锁：
       ① AST 全文件扫描：`self.fall_start_time` 的 Attribute 节点数 = 0；
       ② getattr(self, 'fall_start_time') 的调用数 = 0；
       ③ modules/*.py 里不得出现该字符串。

  C. init_movement 内同一字段不得重复赋值
     第三十四轮合并了 5 组（is_falling ×3 / is_recovering ×2 / fall_duration ×2 /
     max_fall_duration ×2 / fall_start_time ×2）。本套件锁：
       ① 上述 5 个字段在 init_movement 内的**赋值语句数各 ≤ 1**；
       ② 反向控制：确认这 5 个字段**确实在 init_movement 内被赋值过**
          （否则"我把 init_movement 删空了"也会 PASS）。

  D. start_fall 内 is_moving 的赋值语句数 = 1（四分支提取后的形态）
       ① 赋值语句数 == 1；
       ② 反向控制：该赋值**出现在 4 个 reason 分支之前**
          （若被人挪回分支内，本套件必须报红）。

  E. 日志 handler 的 rollover 失败必须被兜住
     `_SafeTimedRotatingFileHandler` 必须存在、且是 TimedRotatingFileHandler 子类；
     行为级正负控制：让 os.rename 抛 OSError，原生 handler 会往 stderr 吐
     `--- Logging error ---`，本类**不得**吐（且要继续写盘）。

**不联网、不实例化 App、不需要显示器**（纯 AST + 轻量运行时常量 + 一次 logging 往返）。
"""
import ast
import io
import logging
import logging.handlers
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# 脚本位于 <repo>/code-quality-audit/第34轮-.../verify_xxx.py
#   HERE        = <repo>/code-quality-audit/第34轮-...
#   ..          = <repo>/code-quality-audit
#   .., ..      = <repo>            ← 仓库根
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
MODULES_DIR = os.path.join(ROOT, 'ralsei_pet', 'modules')
LOGGER_PY = os.path.join(MODULES_DIR, 'logger_utils.py')

PASS = 0
FAIL = 0
_NOTES = []


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        # 输出格式必须是 `[PASS]` / `[FAIL]` 字面量：
        # run_all.py 用 `re.findall(r'\[PASS\]|\[\s*OK\s*\]', text)` 统计 PASS 数，
        # 写成 "  PASS  msg" 会让计数恒为 0（套件仍能通过，但汇总结算数字失真）。
        print('[PASS] %s' % msg)
    else:
        FAIL += 1
        print('[FAIL] %s' % msg)


def note(msg):
    _NOTES.append(msg)
    print('  NOTE  %s' % msg)


def _read(path):
    return io.open(path, encoding='utf-8').read()


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _attr_assign_count(node, attr):
    """统计 node（某函数）内 `self.<attr> = ...` 的**赋值语句**条数。

    注意：一条语句 `self.a = self.b = 1` 算 targets 里两个 Attribute；
    本函数按"赋值语句"计数（`is_movement` 的四个分支各是一条独立语句）。
    """
    cnt = 0
    for st in ast.walk(node):
        if isinstance(st, ast.Assign):
            for t in st.targets:
                if (isinstance(t, ast.Attribute)
                        and isinstance(t.value, ast.Name)
                        and t.value.id == 'self'
                        and t.attr == attr):
                    cnt += 1
    return cnt


def main():
    print('=' * 72)
    print('第三十四轮：移动/行为基础代码「不许回退」回归锁')
    print('=' * 72)

    src = _read(MAIN_PY)
    tree = ast.parse(src)

    # ---------------- A. 假 Qt 钩子 ----------------
    print('\n[A] 假 Qt 事件钩子（mouseEnterEvent / mouseLeaveEvent）不许回来')
    for fake in ('mouseEnterEvent', 'mouseLeaveEvent'):
        check(_func(tree, fake) is None,
              'main.py 里不得再定义 %s（AST FunctionDef）' % fake)
    # 反向控制：真钩子必须在，证明判据有鉴别力
    for real in ('mousePressEvent', 'mouseMoveEvent', 'mouseReleaseEvent',
                 'mouseDoubleClickEvent'):
        check(_func(tree, real) is not None,
              '反向控制：真 Qt 钩子 %s 仍在（判据有鉴别力）' % real)
    # 运行时判据：QWidget 自身没有 mouseEnterEvent
    try:
        from PyQt5.QtWidgets import QWidget
        check(not hasattr(QWidget, 'mouseEnterEvent'),
              '逆向实证：QWidget 类本身没有 mouseEnterEvent 属性')
        check(hasattr(QWidget, 'enterEvent'),
              '逆向实证：QWidget 类有 enterEvent 属性（这才是 Qt 的钩子）')
    except Exception as e:  # pragma: no cover
        check(False, 'PyQt5 不可用，无法做运行时判据: %s' % e)

    # ---------------- B. 死字段 fall_start_time ----------------
    print('\n[B] 死字段 fall_start_time 不许回来')
    attr_nodes = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Attribute) and n.attr == 'fall_start_time']
    check(len(attr_nodes) == 0,
          'main.py 内 self.fall_start_time 的 Attribute 节点数 = 0（实测 %d）'
          % len(attr_nodes))
    getattr_hits = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'getattr' and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)
                and n.args[1].value == 'fall_start_time'):
            getattr_hits.append(n.lineno)
    check(len(getattr_hits) == 0,
          "main.py 内 getattr(self,'fall_start_time') 调用数 = 0（实测 %d）"
          % len(getattr_hits))
    mod_hits = []
    for fn in sorted(os.listdir(MODULES_DIR)):
        if not fn.endswith('.py'):
            continue
        p = os.path.join(MODULES_DIR, fn)
        try:
            s = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        if 'fall_start_time' in s:
            mod_hits.append(fn)
    check(not mod_hits,
          'modules/*.py 内不得出现 fall_start_time（实测命中 %s）' % (mod_hits or '无'))
    # 反向控制：注释里应留有"已删除"的说明，证明这不是"整个字段从没存在过"
    check('fall_start_time' in src,
          '反向控制：源码注释里仍留有 fall_start_time 的删除说明（判据不是空扫）')

    # ---------------- C. init_movement 重复赋值 ----------------
    print('\n[C] init_movement 内同一字段不得重复赋值')
    im = _func(tree, 'init_movement')
    check(im is not None, '能定位 init_movement（AST）')
    if im is not None:
        for field in ('is_falling', 'is_recovering', 'fall_duration',
                      'max_fall_duration', 'fall_start_time'):
            n = _attr_assign_count(im, field)
            if field == 'fall_start_time':
                check(n == 0, 'init_movement 内 %s 赋值语句数 = 0（已整体删除，实测 %d）'
                              % (field, n))
            else:
                check(n <= 1, 'init_movement 内 %s 赋值语句数 ≤ 1（实测 %d）'
                              % (field, n))
        # 反向控制：这 4 个字段确实还在 init_movement 内被赋值
        for field in ('is_falling', 'is_recovering', 'fall_duration',
                      'max_fall_duration', 'is_gravity_falling'):
            n = _attr_assign_count(im, field)
            check(n >= 1,
                  '反向控制：init_movement 内仍有 %s 的初始化（实测 %d）' % (field, n))

    # ---------------- C2. max_fall_duration 初值必须保持 2.0 ----------------
    # 去重时若误取先出现的 5.0，就把运行时初值从 2.0 静默改成 5.0 —— 这是引入 bug。
    print('\n[C2] init_movement 的 max_fall_duration 初值必须保持运行时等价（2.0）')
    if im is not None:
        vals = []
        for st in ast.walk(im):
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    if (isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name) and t.value.id == 'self'
                            and t.attr == 'max_fall_duration'):
                        if isinstance(st.value, ast.Constant):
                            vals.append(st.value.value)
        check(vals == [2.0],
              'init_movement 内 max_fall_duration 的常量初值恰为 [2.0]（实测 %s）' % vals)

    # ---------------- D. start_fall 的 is_moving 提取 ----------------
    print('\n[D] start_fall 内 is_moving 赋值语句数 = 1 且位于分支之前')
    sf = _func(tree, 'start_fall')
    check(sf is not None, '能定位 start_fall（AST）')
    if sf is not None:
        n = _attr_assign_count(sf, 'is_moving')
        check(n == 1, 'start_fall 内 is_moving 赋值语句数 == 1（实测 %d）' % n)
        # 反向控制：该赋值必须在第一个 `if reason ==` 之前
        assign_line = None
        for st in ast.walk(sf):
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    if (isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name) and t.value.id == 'self'
                            and t.attr == 'is_moving'):
                        assign_line = st.lineno
        reason_if_line = None
        for n2 in ast.walk(sf):
            if isinstance(n2, ast.If):
                # 找 `if reason == "..."` 形态
                tst = n2.test
                if (isinstance(tst, ast.Compare)
                        and isinstance(tst.left, ast.Name) and tst.left.id == 'reason'):
                    reason_if_line = n2.lineno
                    break
        check(assign_line is not None and reason_if_line is not None
              and assign_line < reason_if_line,
              # ⚠️ 断言的是**相对关系**（先后），消息里**不许**打印绝对行号 ——
              # 打印行号会让"在上方任意一行插入代码"（例：diff 基线）也触发 DIFF，
              # 那是**与判据无关的漂移**，会把真回退淹没在噪声里（第 34 轮踩过）。
              '反向控制：is_moving=False 位于 reason 分支之前'
              '（相对位置：赋值的行号 < 分支的行号 = %s）'
              % (assign_line < reason_if_line
                 if (assign_line is not None and reason_if_line is not None)
                 else 'N/A'))
        # 反向控制：idle_timer 的差异化赋值必须保留（两处，不是四处）
        nt = _attr_assign_count(sf, 'idle_timer')
        check(nt == 2,
              '反向控制：start_fall 内 idle_timer 赋值语句数 == 2'
              '（真实差异被保留，实测 %d）' % nt)

    # ---------------- E. 日志 rollover 兜底 ----------------
    print('\n[E] 日志 handler 的 rollover 失败必须被兜住')
    ls = _read(LOGGER_PY)
    lt = ast.parse(ls)
    check(_func(lt, 'doRollover') is not None,
          'logger_utils 里有 doRollover 覆盖（AST）')
    # 从源码文本找类名并 import 它做行为验证
    cls_name = None
    for n in ast.walk(lt):
        if isinstance(n, ast.ClassDef):
            for base in n.bases:
                bname = None
                if isinstance(base, ast.Name):
                    bname = base.id
                elif isinstance(base, ast.Attribute):
                    bname = base.attr
                if bname == 'TimedRotatingFileHandler':
                    cls_name = n.name
                    break
    check(cls_name is not None,
          'logger_utils 里存在 TimedRotatingFileHandler 的子类（实测 %s）' % cls_name)
    check('TimedRotatingFileHandler(' not in ls.replace('_SafeTimedRotatingFileHandler(', ''),
          '初始化处不再直接用裸 TimedRotatingFileHandler')

    if cls_name is not None:
        # 把 logger_utils 以独立模块加载（不污染包导入链）
        import importlib.util
        spec = importlib.util.spec_from_file_location('_lu_probe_r34', LOGGER_PY)
        lu = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lu)
        SafeCls = getattr(lu, cls_name, None)
        check(SafeCls is not None, '能取到安全 handler 类')
        if SafeCls is not None:
            check(issubclass(SafeCls, logging.handlers.TimedRotatingFileHandler),
                  '安全 handler 是 TimedRotatingFileHandler 的子类')
            d = tempfile.mkdtemp(prefix='r34_rollover_')
            p = os.path.join(d, 'x.log')
            orig_rename = os.rename

            def _boom(a, b):
                raise OSError(1, '函数不正确。')

            try:
                # 负控制：原生 handler 会吐 --- Logging error ---
                os.rename = _boom
                h0 = logging.handlers.TimedRotatingFileHandler(
                    p, when='midnight', interval=1, backupCount=7, encoding='utf-8')
                h0.suffix = '%Y-%m-%d'
                h0.rolloverAt = 0
                lg0 = logging.getLogger('_r34_neg')
                lg0.setLevel(logging.INFO)
                lg0.propagate = False
                lg0.addHandler(h0)
                buf0 = io.StringIO()
                old_err = sys.stderr
                sys.stderr = buf0
                try:
                    lg0.info('neg')
                finally:
                    sys.stderr = old_err
                neg_tb = 'Logging error' in buf0.getvalue()
                h0.close()
                lg0.removeHandler(h0)
                check(neg_tb,
                      '负控制：原生 handler 在 rollover 失败时确实吐 Logging error'
                      '（判据有鉴别力）')

                # 正控制：安全 handler 不吐，且继续写盘
                h1 = SafeCls(p, when='midnight', interval=1, backupCount=7,
                             encoding='utf-8')
                h1.suffix = '%Y-%m-%d'
                h1.rolloverAt = 0
                lg1 = logging.getLogger('_r34_pos')
                lg1.setLevel(logging.INFO)
                lg1.propagate = False
                lg1.addHandler(h1)
                buf1 = io.StringIO()
                old_err = sys.stderr
                sys.stderr = buf1
                try:
                    lg1.info('pos-one')
                    lg1.info('pos-two')
                finally:
                    sys.stderr = old_err
                pos_tb = 'Logging error' in buf1.getvalue()
                h1.close()
                lg1.removeHandler(h1)
                check(not pos_tb,
                      '正控制：安全 handler 在同样故障下不吐 Logging error')
                content = io.open(p, encoding='utf-8').read()
                check('pos-one' in content,
                      '正控制：rollover 失败后日志仍继续写入当前文件')
            finally:
                os.rename = orig_rename
                try:
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

    print('\n' + '=' * 72)
    print('结果：PASS=%d FAIL=%d' % (PASS, FAIL))
    print('=' * 72)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
