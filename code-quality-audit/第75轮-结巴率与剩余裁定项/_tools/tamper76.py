# -*- coding: utf-8 -*-
"""第七十五轮 B3：`check76` 的篡改自证（mutate-and-revert）。

对每个 case：把目标文件改成"坏写法" → 跑 check76 → **期望它报 FAIL**
（挑的是与本 case 相关的判据名）→ 从内存原样写回 → 复核 sha256 一致。

为什么必须做：`check76` 有 59 条判据，如果它整片变成恒真，
"篡改后仍然全绿"是唯一能暴露这一点的测试。
"""
import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
PY = r'C:\Python311\python.exe'
CHECK = os.path.join(HERE, 'check76.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_interaction.py')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_check():
    r = subprocess.run([PY, CHECK], capture_output=True)
    out = r.stdout.decode('utf-8', errors='replace')
    m = re.search(r'合计：PASS=(\d+) FAIL=(\d+)', out)
    fails = re.findall(r'\[FAIL\] (.+)', out)
    return (int(m.group(1)), int(m.group(2)), fails) if m else (-1, -1, [])


def case(desc, path, old, new, expect_key):
    """打篡改 → 跑 → 期望报红 → 还原 → 复核 sha。

    ★★ EOL 陷阱（本机实测踩到）：仓库文件是 **CRLF**，而本脚本里的夹具串
      写的是 `\n` ⇒ `old in orig` 恒为 False，10 个 case 会**静默跳过**。
      ⇒ 统一先把两边的 `\r\n` 归一成 `\n` 再匹配，写回时**保持原文件的 EOL 风格**。

    ★ 第75轮教训（**过度设计反害事**）：我曾把匹配改成"行内空白不敏感"以图
      让夹具耐受排版漂移（为了修 ⑨）。结果 `_line_flex` 的 `fullmatch` 判定写错，
      把原本**正确的** ①~⑧ 全部变成 SKIP/MISS（`FAIL=-1`：替换后源码语法坏掉、
      被测脚本直接崩）。
      ⇒ 结论：**夹具必须从当前源码逐字拷出**（含缩进），匹配就该是逐字的；
        "空白不敏感"是个陷阱 —— 一旦灵活到能吃换行/行尾，就会替换掉非预期区间。
        真需要放宽时，只放宽**已确认无害的那一处**（见 ⑨ 的处理：它只放宽了
        2 个空格与 1 个空格之差，且**不跨行**）。
    """
    before = sha(path)
    with open(path, 'r', encoding='utf-8', newline='') as f:
        orig = f.read()
    crlf = '\r\n' in orig
    orig_n = orig.replace('\r\n', '\n')
    old_n = old.replace('\r\n', '\n')
    new_n = new.replace('\r\n', '\n')
    if old_n not in orig_n:
        print('[SKIP] %s —— 夹具串没找到（判据/文件已变？）' % desc)
        return None
    tampered_n = orig_n.replace(old_n, new_n, 1)
    assert tampered_n != orig_n, desc
    tampered = tampered_n.replace('\n', '\r\n') if crlf else tampered_n
    try:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(tampered)
        p, fl, fails = run_check()
        hit = any(expect_key in x for x in fails)
        ok = (fl > 0) and hit
        print('[%s] %s  (FAIL=%d, 命中期望=%s)'
              % ('OK  ' if ok else 'MISS', desc, fl, hit))
        if not hit:
            print('       实际报红：%s' % (fails or '（无）'))
        return ok
    finally:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(orig)
        after = sha(path)
        if after != before:
            print('       !! 还原后 sha256 不一致 %s -> %s' % (before[:12], after[:12]))


CASES = [
    # —— 产品侧 ——
    ('① main.py 去掉 tracker 构造 ⇒ C2 报红',
     MAIN,
     'self._pet_tracker = PetInteractionTracker()',
     'self._pet_tracker = None  # tampered',
     'C2 '),

    ('② main.py 去掉 handle_move 的真实调用（改成哨兵值）⇒ C3 报红',
     MAIN,
     '                rel = self._pet_rel_pos(event.pos())\n'
     '                if rel is not None:\n'
     '                    ev = self._pet_tracker.handle_move(rel)',
     '                rel = self._pet_rel_pos(event.pos())\n'
     '                if rel is not None:\n'
     '                    ev = self._pet_tracker.handle_move((0.0, 0.0))',
     'C3 main.py 真用**非哨兵**实参调用 handle_move'),

    ('③ main.py 去掉换帧同步（只留 1 处）⇒ C5 报红',
     MAIN,
     '                    self.sprite_label.setPixmap(cached_sprite)\n'
     '                    # ★ 第75轮 B3：换帧后同步手势判定器的精灵尺寸 / alpha 遮罩\n'
     '                    self._sync_pet_tracker_sprite()\n'
     '        \n'
     '        # 更新状态计时器',
     '                    self.sprite_label.setPixmap(cached_sprite)\n'
     '        \n'
     '        # 更新状态计时器',
     'C5 '),

    ('④ main.py 复活手写状态机（重新读写 _pet_detection_state）⇒ C6 报红',
     MAIN,
     '                rel = self._pet_rel_pos(event.pos())\n'
     '                if rel is not None:\n'
     '                    self._pet_tracker.handle_press(rel)',
     '                self._pet_detection_state = {}\n'
     '                rel = self._pet_rel_pos(event.pos())\n'
     '                if rel is not None:\n'
     '                    self._pet_tracker.handle_press(rel)',
     'C6 '),

    ('⑤ main.py 重新塞进第二份区域表 ⇒ C7 报红',
     MAIN,
     '    def _sync_pet_tracker_sprite(self):',
     '    _TAMPER_REGIONS = [\n'
     '        ("ear", 0, 0, 30, 40),\n'
     '        ("ear", 70, 0, 100, 40),\n'
     '        ("hair", 25, 10, 75, 50),\n'
     '        ("face", 30, 30, 70, 60),\n'
     '        ("belly", 35, 60, 65, 80),\n'
     '        ("body", 20, 50, 80, 80),\n'
     '        ("legs", 30, 80, 70, 100),\n'
     '        ("arm", 0, 40, 30, 70),\n'
     '    ]\n\n'
     '    def _sync_pet_tracker_sprite(self):',
     'C7 main.py 没有第二份部位区域表'),

    ('⑥ main.py 复活 clicked_part 比较分支链 ⇒ C8 报红',
     MAIN,
     '            kind = kind_for(part, Gesture.PAT)',
     '            _clicked_part = part.value\n'
     '            if _clicked_part == "hair":\n'
     '                pass\n'
     '            kind = kind_for(part, Gesture.PAT)',
     'C8 '),

    ('⑦ main.py 复活手写抚摸状态 ⇒ C9 报红',
     MAIN,
     '    def _pet_rel_pos(self, pos):',
     '    def _tamper(self):\n'
     '        self.movement_history = []\n'
     '        self.direction_changes = 0\n\n'
     '    def _pet_rel_pos(self, pos):',
     'C9 main.py 不再有手写抚摸状态 `movement_history`'),

    ('⑧ main.py 双击改走 tracker 手势机 ⇒ C12b 报红',
     MAIN,
     '            kind = kind_for(part, Gesture.PAT)',
     '            self._pet_tracker.handle_release((1.0, 1.0))\n'
     '            kind = kind_for(part, Gesture.PAT)',
     'C12b'),

    # —— 模块侧（证据/常数） ——
    ('⑨ 模块把 BELLY 挪到 TORSO 之后 ⇒ A2 报红',
     MOD,
     # ★ 第75轮修：夹具原先写 `(BodyPart.BELLY,   35.0, 60.0, 65.0, 80.0),`
     #   （`65.0` 前 1 个空格 + 行尾注释），而实现里为视觉对齐写的是 **2 个空格**
     #   且**无行尾注释** ⇒ 逐字匹配失败 ⇒ 静默 SKIP。
     #   ★ 修法是**从当前源码逐字拷出**（而非把匹配器改成空白不敏感 ——
     #     那会跨行贪吃、把 ①~⑧ 一起弄坏，见 `case()` 的 docstring）。
     #   ★★ 二次踩坑：改完仍 SKIP —— 因为 BELLY 行与 TORSO 行**中间隔着**
     #      `# 躯干区域` 这行注释（源码 84/85/86 行）。夹具必须**连注释一起**
     #      拷（否则 `A\nB in src` 恒假，而单独 A、B 都 `in src` 为真 ——
     #      这种"单行都对、拼起来不对"最难查）。
     '    (BodyPart.BELLY,   35.0, 60.0,  65.0, 80.0),\n'
     '    # 躯干区域\n'
     '    (BodyPart.TORSO,   20.0, 50.0,  80.0, 80.0),',
     '    (BodyPart.TORSO,   20.0, 50.0,  80.0, 80.0),\n'
     '    # 躯干区域\n'
     '    (BodyPart.BELLY,   35.0, 60.0,  65.0, 80.0),',
     'A2 '),

    ('⑩ 模块新增一个未登记的事件名 ⇒ A3/A4 报红',
     MOD,
     # ★ 第75轮修：夹具原先写 `_PUSH_DEFAULT = "poke_default"` —— 那是**初版**的名字，
     #   回原文对齐后实现里已不存在该常量 ⇒ 夹具恒找不到 ⇒ 静默 SKIP。
     #   改用**真存在**的锚点（从当前源码逐字拷出）。
     "    'poke_default': _spec((), None, 'happy',",
     "    'poke_zzz_new': _spec((), None, 'happy',",
     'A4 '),
]


def main():
    results = []
    for desc, path, old, new, key in CASES:
        results.append(case(desc, path, old, new, key))
    print('')
    ok = sum(1 for r in results if r is True)
    miss = sum(1 for r in results if r is False)
    skip = sum(1 for r in results if r is None)
    # ★ 第75轮修：**SKIP 必须显式计数并导致失败**。
    #   初版只打 `8/10 命中`，两个 SKIP 混在分母里、退出码仍 0 ⇒
    #   最有价值的两个用例（BELLY 优先级 / 事件名登记）**没跑也没人知道**。
    print('篡改自证：命中 %d / 未命中 %d / 跳过 %d（共 %d）'
          % (ok, miss, skip, len(results)))
    if skip:
        print('  ⚠️ 有 %d 个用例**静默跳过** —— 夹具串已失效，请修夹具（不许留 SKIP）' % skip)
    # 收尾复核：还原后必须仍全绿
    p, fl, fails = run_check()
    print('还原后复核：PASS=%d FAIL=%d %s' % (p, fl, '（全绿）' if fl == 0 else fails))
    return 0 if (ok == len(results) and fl == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
