# -*- coding: utf-8 -*-
"""修补 main.py 单实例互斥量句柄生命周期（保留 CRLF 换行）"""
import io

p = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"
with io.open(p, "r", encoding="utf-8", newline="") as f:
    src = f.read()

NL = "\r\n"

old1 = (
    "    优先使用 Windows 命名互斥量，失败时回退到文件锁。" + NL + '    """' + NL + "    import atexit"
)
new1 = (
    "    优先使用 Windows 命名互斥量，失败时回退到文件锁。" + NL + '    """' + NL
    + "    global _single_instance_mutex" + NL + "    import atexit"
)
assert src.count(old1) == 1, "old1 count=%d" % src.count(old1)
src = src.replace(old1, new1)

old2 = (
    '            _log.debug("单实例检查通过，互斥量已创建")' + NL
    + "            # 互斥量会在进程结束时自动释放" + NL
    + '            _log.debug("单实例检查通过，可以正常运行！")' + NL
    + "            return True"
)
new2 = (
    '            _log.debug("单实例检查通过，互斥量已创建")' + NL
    + "            # 修复：句柄必须保持存活到进程结束。局部变量在函数返回后被 GC" + NL
    + "            # 关闭句柄，命名互斥量在最后一个句柄关闭时会被系统销毁，导致第二次" + NL
    + "            # 启动可成功创建同名互斥量 → 单实例保护失效（双实例并存）。" + NL
    + "            # 存入模块级引用，进程退出时由操作系统自动释放。" + NL
    + "            _single_instance_mutex = mutex" + NL
    + '            _log.debug("单实例检查通过，可以正常运行！")' + NL
    + "            return True"
)
assert src.count(old2) == 1, "old2 count=%d" % src.count(old2)
src = src.replace(old2, new2)

with io.open(p, "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("PATCH OK")
