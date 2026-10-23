# -*- coding: utf-8 -*-
"""第一百一十三轮 · 真源归档（防丢）

用户 2026-10-24 在桌面上放了两份**真源**：
  * `其余人物设定.txt` —— 96 人设定的总源，`assets/npc/persona/*.txt` 全部由它派生；
  * `人物关系叙述.txt`   —— 5 部作品的关系总纲。

桌面文件会被改、会被挪、会丢。这里做**逐字节快照 + sha256 清单**，
让"以后想回溯原文"这件事不依赖那张桌面。

不解析、不改写、不重新编码 —— 原样复制，清单单独记。
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))     # 仓库根
NPC_DIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
OUT_DIR = os.path.join(NPC_DIR, '_relations')

SOURCES = [
    (r'C:\Users\23002\Desktop\其余人物设定.txt', 'personas_source.txt',
     '96 人设定总源：persona/*.txt 全部由它派生（第112轮抽取、第113轮按新版重建 6 份主线）'),
    (r'C:\Users\23002\Desktop\人物关系叙述.txt', 'relations_source.txt',
     '5 部作品关系总纲：`_index.json` 由它切块生成'),
]


def sha_of(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    entries = []
    ok = True
    for src, dst_name, why in SOURCES:
        dst = os.path.join(OUT_DIR, dst_name)
        if not os.path.isfile(src):
            print('[MISS] %s —— 桌面那份不在了，但已归档副本 %s 仍在'
                  % (src, os.path.basename(dst)), flush=True)
            if os.path.isfile(dst):
                entries.append({'name': os.path.basename(src), 'archived': dst_name,
                                'bytes': os.path.getsize(dst), 'sha256': sha_of(dst),
                                'used_for': why, 'note': '源文件已不在原处，此为仅存副本'})
            else:
                ok = False
            continue
        shutil.copyfile(src, dst)
        h_src, h_dst = sha_of(src), sha_of(dst)
        same = h_src == h_dst
        ok = ok and same
        entries.append({'name': os.path.basename(src), 'archived': dst_name,
                        'bytes': os.path.getsize(dst), 'sha256': h_src,
                        'used_for': why, 'same_as_source': same})
        print('%-22s %9d B  sha %s  同源=%s'
              % (dst_name, os.path.getsize(dst), h_src[:16], same), flush=True)

    manifest = {'schema_version': 1,
                'archived_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'note': '桌面真源快照。改动 persona 前先对比这里的 sha256。',
                'sources': entries}
    mpath = os.path.join(OUT_DIR, '_manifest.json')
    with io.open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print('清单：%s' % mpath, flush=True)

    # 回读断言：写完必须能读回来，且 sha 对得上（防"写了但坏了"）
    back = json.load(io.open(mpath, encoding='utf-8'))
    for e in back['sources']:
        p = os.path.join(OUT_DIR, e['archived'])
        actual = sha_of(p)
        if actual != e['sha256']:
            print('[FAIL] 回读不一致：%s' % e['archived'], flush=True)
            ok = False
    print('回读：%d 份，%s' % (len(back['sources']), 'OK' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
