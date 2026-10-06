# -*- coding: utf-8 -*-
u"""把 tag `backup/worktree-89round` 里的**参考文件**原样（字节级）抽到
`_evidence/ref89/`，供逐项 diff 审查。

★ 为什么用 Python 而不是 PowerShell 重定向：`>` / `Out-File` 会改编码与 EOL，
  比对时会凭空产生 BOM/EOL 噪声（记忆 §65.2）。这里走 `subprocess` + bytes，
  落地也用 `newline=''` 原样写。
★ 用 `git show <tag>:<path>`（不是 `git checkout`）：只读，不碰工作区。
"""
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REF = os.path.join(HERE, '..', '_evidence', 'ref89')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TAG = 'backup/worktree-89round'

PATHS = [
    'ralsei_pet/assets/scenes/desktop.json',
    'ralsei_pet/assets/scenes/_room_geometry.json',
    'ralsei_pet/assets/scenes/_routes.json',
    'ralsei_pet/assets/scenes/_index.json',
    'ralsei_pet/modules/scene_render.py',
    'ralsei_pet/modules/scene_pathfind.py',
    'ralsei_pet/modules/scene_controller.py',
    'ralsei_pet/modules/scene_canvas.py',
    'ralsei_pet/modules/item_interact.py',
    'ralsei_pet/modules/video_controller.py',
    'ralsei_pet/modules/dialogue_ui.py',
    'ralsei_pet/modules/memory_system.py',
    'ralsei_pet/src/main.py',
]


def main():
    if not os.path.isdir(REF):
        os.makedirs(REF)
    for p in PATHS:
        r = subprocess.run(['git', 'show', '%s:%s' % (TAG, p)],
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        base = p.replace('/', '__')
        if r.returncode != 0:
            print('[MISS] %-58s %s' % (p, r.stderr.decode('utf-8', 'replace').strip()[:80]))
            continue
        dst = os.path.join(REF, base)
        with open(dst, 'wb') as fh:
            fh.write(r.stdout)
        cur = os.path.join(ROOT, p)
        csz = os.path.getsize(cur) if os.path.exists(cur) else -1
        print('[OK]   %-58s ref89=%7d  now=%7d  delta=%+d'
              % (p, len(r.stdout), csz, csz - len(r.stdout)))
    print('参考版本 -> %s' % REF)


if __name__ == '__main__':
    sys.exit(main())
