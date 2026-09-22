# -*- coding: utf-8 -*-
"""鉴别力体检：把 F34-1 的修复回退成缺陷写法，看回归锁是否报红。
跑完请用 restore 模式还原（或直接 git checkout --）。
"""
import io
import os
import shutil
import sys

P = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py'
BAK = P + '.probe_discrim'

mode = sys.argv[1] if len(sys.argv) > 1 else 'break'

if mode == 'break':
    if not os.path.exists(BAK):
        shutil.copy2(P, BAK)
    s = io.open(P, encoding='utf-8', newline='').read()

    # 文件是 CRLF（仓库口径），用 newline='' 读时 \r\n 原样保留 ⇒ 片段必须写 \r\n
    E = '\r\n'
    # 修复写法（当前）：赋值在 if 块内
    fixed = (
        "        try:" + E +
        "            if not hasattr(self, '_last_desktop_elem_check') or "
        "current_time - self._last_desktop_elem_check > 5.0:" + E +
        "                self.check_nearby_desktop_elements()" + E +
        "                self._last_desktop_elem_check = current_time" + E +
        "        except Exception as e:" + E +
        '            _log.warning(f"check_nearby_desktop_elements 异常: {e}")' + E
    )
    # 缺陷写法：赋值搬到 try 外
    broken = (
        "        try:" + E +
        "            if not hasattr(self, '_last_desktop_elem_check') or "
        "current_time - self._last_desktop_elem_check > 5.0:" + E +
        "                self.check_nearby_desktop_elements()" + E +
        "        except Exception as e:" + E +
        '            _log.warning(f"check_nearby_desktop_elements 异常: {e}")' + E +
        "        self._last_desktop_elem_check = current_time" + E
    )

    n = s.count(fixed)
    print('fixed 片段匹配数 =', n)
    if n != 1:
        print('❗未唯一匹配，放弃（不修改文件）')
        sys.exit(2)
    s = s.replace(fixed, broken)
    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('已回退为缺陷写法；备份 =', BAK)

elif mode == 'restore':
    if os.path.exists(BAK):
        shutil.copy2(BAK, P)
        os.remove(BAK)
        print('已还原修复写法，备份已删')
    else:
        print('无备份（可能已 git checkout --）')
