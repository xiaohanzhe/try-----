# -*- coding: utf-8 -*-
"""跑本轮的验证套件，并把 stdout 交给 **Python 自己** 写成证据文件。

为什么需要这一层（第十三轮的真实翻车，见 MEMORY 环境铁律 10）：
用 PowerShell 的 `*>` / `Out-File` 捕获原生程序 stdout 时，字节会先按控制台代码页
（本机 GBK）解码、再按 UTF-8 重写 → **中文全部变成看不懂的方块字，文件内容本身已经坏了**。
所以证据文件必须由 Python `open(path, 'w', encoding='utf-8')` 直接写。

用法：
  & C:\\Python311\\python.exe run_check.py verify_s7_event_speech.py
"""
import io
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, '_evidence')


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: run_check.py <suite.py>\n')
        return 2
    target = argv[1]
    if not os.path.isabs(target):
        target = os.path.join(HERE, target)
    stem = os.path.splitext(os.path.basename(target))[0]
    out = argv[2] if len(argv) > 2 else os.path.join(EV, stem + '_out.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    code = 0
    try:
        runpy.run_path(target, run_name='__main__')
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        import traceback
        buf.write('\n[runner] 套件自身异常: %r\n%s\n' % (e, traceback.format_exc()))
        code = 3
    finally:
        sys.stdout = old

    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(buf.getvalue())
        f.write('\nEXIT=%d\n' % code)
    old.write('EXIT=%d  ->  %s\n' % (code, out))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
