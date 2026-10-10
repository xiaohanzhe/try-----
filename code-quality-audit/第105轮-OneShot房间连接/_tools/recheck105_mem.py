# -*- coding: utf-8 -*-
"""第105轮 · 记忆改动复检：速查本被压缩掉的令牌，逐个回「速查本+详版」`in` 一次。

为什么需要它：本轮为腾出 §18（第105轮）的注入空间，把速查本 `MEMORY.md` 的
§15/§16/§17 与 §12 做了**结构性下沉**（原文进详版 §105.9）。按 skil
`agent-memory-compaction` 的铁律：**压完必须逐令牌回验** —— 每个被删/改写的
可检索令牌都要在「速查本或详版」至少出现一次，否则就是静默丢信息。

★ 判据自身修正过两处（都是"判据太窄"的经典坑，本项目已多次栽）：
  ① 原只查详版 ⇒ `尊重用户口径` 那句**操作纪律本来就该留在速查本**，压到详版
     反而找不到 ⇒ 改为**任一侧可达即算通过**；
  ② `cell = (sheet_w//4, sheet_h//4)` 在详版里写作 `cell = (sheet_w // 4,
     sheet_h // 4)`（**等价写法**）⇒ 按符号形式而非字面形式匹配。

用法：
    C:\\Python311\\python.exe _tools\\recheck105_mem.py
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')          # 仓库根
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

TOKENS = [
    # 原 §15（99）
    'fit_bg_world', 'K_ROOM_FILL', 'spr=', 'vis=', 'plan_frame',
    '加过滤器前先查自造数据有没有借它的名字', 'authored is True',
    '_AUTHORED_KINDS', 'TRANSPARENT_BG', 'pet_in_frame', 'GEN99_SELFTEST',
    'VERDICT=FAIL', '2166', '四世界 1152', '等比 cover', '品红',
    # 原 §16（103）
    'cell = (sheet_w // 4, sheet_h // 4)', '(w//4', 'DIR_ROW', '2:0,4:1,6:2,8:3',
    '底边贴瓦片底', 'DOORS2', 'map4', '54:0', 'grid_anchor103.json',
    'anchor_cases103.json', 'oneshot_cells', '7804+1==7805',
    'meta.objects_source', 'objects_round44', 'verify_scene_fit99',
    '85.5%', '24.9%', 'npc_BIG', 'objs/', '世界格 16px', 'tmx',
    # 原 §17（104）
    'opacity / 255.0', 'CompositionMode_Plus', '191', '7,405', 'finally',
    '1e-3', '1e-6', '32 条假红', 'condition', 'self_switch_ch', '*_valid',
    '5003', '407', '222', '34', '389', '399',
    # 原 §12（真机取证）→ 并入 §11 行
    'QScreen.grabWindow(0)', 'QApplication', '_subpixel', 'mp4v',
    'current_speed_x/y', 'change_animation', 'L11800',
    # 原 §11 压缩掉的
    'ch1.kris_room', '立刻参与', 'outertale_pending', '先落',
    '尊重用户口径', '含 CRLF',
    # 第105轮新增（两侧至少一侧在）
    'code 201', 'Transfer Player', 'oneshot_transfer', 'original_room_id',
    '826', '749', '420', '730', '196', 'check105', 'mutate105', 'verify105',
    '5051', 'PRIO_BASE', '3000', 'oneshot_transfers.json', 'when_door',
    'DEBUG', 'A3b', 'A3c', 'C3a2', 'C3a3',
]


def main():
    mem = io.open(MEM, 'r', encoding='utf-8', newline='').read()
    det = io.open(DET, 'r', encoding='utf-8', newline='').read()

    js = len(mem.encode('utf-16-le')) // 2
    print('[INFO] 速查本 js_len = %d（上限 10000，余量 %+d）' % (js, 10000 - js))
    print('[INFO] 详版 chars = %d' % len(det))
    print('-' * 76)

    miss = [t for t in TOKENS if (t not in det) and (t not in mem)]
    if miss:
        for t in miss:
            print('[MISS] 两侧都找不到: %r' % t)
        print('结论：FAIL —— %d/%d 令牌在速查本与详版均缺位'
              % (len(miss), len(TOKENS)))
    else:
        print('结论：PASS —— %d/%d 令牌全部可在速查本或详版检索到'
              % (len(TOKENS), len(TOKENS)))

    # 结构自检：章节标题全在且各 1 次（不粘连）
    need = ['## 0.', '## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.',
            '## 7.', '## 8.', '## 9.', '## 10.', '## 11.', '## 15.',
            '## 16.', '## 17.', '## 18.']
    bad = [n for n in need if mem.count(n) != 1]
    print('[STRUCT] 标题逐一 == 1 次：%s' % ('OK' if not bad else '异常 %r' % bad))
    print('[STRUCT] 无 BOM：%s ｜ 无 U+FFFD：%s ｜ js_len<=10000：%s'
          % (io.open(MEM, 'rb').read()[:3] != b'\xef\xbb\xbf',
             '\ufffd' not in mem, js <= 10000))
    print('[STRUCT] 详版含 §105：%s ｜ 含下沉段 §105.9：%s'
          % ('## §105 ' in det, '§105.9' in det))


if __name__ == '__main__':
    main()
