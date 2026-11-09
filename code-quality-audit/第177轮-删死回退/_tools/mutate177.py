# -*- coding: utf-8 -*-
u"""第177轮变异：证明 `check177.py` 的每条判据不是摆设。

规矩（与 174/175/176 轮同）
--------------------------
  ① **先备份再改**；② 每轮跑完立即恢复并按 sha1 + 全文核对；
  ③ 「红在哪几条」按**实测**记，但必须包含本变异**针对**的那条；
  ④ 备份落 `D:\\_tmp\\mut177\\`（不在工作区）。

★ M1 是**最忠实**的一条：直接把 `scene_system.py` 换回 `HEAD` 版
  （= 回退代码还在的样子），看那 4 条靶子判据会不会全部报红。
  这比"手工把那 8 行拼回去"更硬 —— 拼错了就成了假夹具。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
TARGET = os.path.join(REPO, 'ralsei_pet', 'modules', 'scene_system.py')
CHECK = os.path.join(HERE, 'check177.py')
BAK = 'D:\\_tmp\\mut177'
REL = 'ralsei_pet/modules/scene_system.py'


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()


def run_check():
    r = subprocess.run([sys.executable, CHECK], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    codes = []
    for ln in out.splitlines():
        if ln.startswith('[FAIL]'):
            codes.append(ln.split('] ', 1)[1].split(u'    ')[0].strip()
                         .split(u' ')[0])
    return r.returncode, codes


# ---------------------------------------------------------------------------
def _sub(old, new, why=u''):
    u"""★ 目标文件是 **CRLF**（`rd` 用 `newline=''` 保留原样），锚点按 LF 写 ⇒
    必须在 LF 空间里替换再换回 CRLF，否则锚点一条都命中不了（本轮实测踩过）。"""
    s = rd(TARGET)
    lf = s.replace(u'\r\n', u'\n')
    assert old in lf, u'锚点没找到（夹具不保真）: %s %s' % (old[:40], why)
    out = lf.replace(old, new, 1)
    assert out != lf
    return out.replace(u'\n', u'\r\n')


def m1_revert():
    u"""整文件换回 `HEAD`：回退代码原样还在。"""
    blob = subprocess.run(['git', 'show', 'HEAD:' + REL], cwd=REPO,
                          stdout=subprocess.PIPE).stdout
    assert blob, u'取不到 HEAD 版'
    txt = blob.decode('utf-8')
    assert 'original_room_id = _oid' in txt, u'HEAD 里没有那段回退，M1 前提不成立'
    assert txt != rd(TARGET), u'HEAD 与工作区相同，M1 没造成差异'
    return TARGET, txt


def m2_drop_area():
    u"""删掉 `area_id` 的取值：分片定位拿不到区域。"""
    return TARGET, _sub(u"        area_id = entry.get('area_id')\n", u'', u'area')


def m3_solo_none():
    u"""独立文件分支 `return scene` 改成 `return None`：88 个场景全挂。"""
    return TARGET, _sub(u"        #   现在改成如实返回 `None` ⇒ 缺字段会显形（`check177 C3/C4` 钉这个）。\n        return scene",
                        u"        return None", u'solo')


def m4_from_dict_guess():
    u"""`from_dict` 缺 rid 时猜 0（补值逻辑换个地方又长出来）。"""
    return TARGET, _sub(u"        self.original_room_id = _oid if isinstance(_oid, int) else None",
                        u"        self.original_room_id = _oid if isinstance(_oid, int) else 0",
                        u'from_dict')


def m5_read_only():
    u"""只在 `load_scene` 里"读一下" entry 的 rid（不赋值，只为打 B2）。"""
    return TARGET, _sub(u"    path = os.path.join(base, scene_id + '.json')",
                        u"    if isinstance(entry, dict):\n"
                        u"        _ = entry.get('original_room_id')\n"
                        u"    path = os.path.join(base, scene_id + '.json')", u'read')


def m6_no_schema():
    u"""删掉 schema 版本守卫。"""
    return TARGET, _sub(u"        if raw.get('schema_version') != SCENE_SCHEMA_VERSION:\n"
                        u"            return None\n", u'', u'schema')


def m7_no_traversal():
    u"""删掉路径穿越守卫。"""
    return TARGET, _sub(u"    if os.sep in scene_id or '/' in scene_id or scene_id in ('.', '..'):\n"
                        u"        return None\n", u'', u'traversal')


def m8_override():
    u"""分片分支改成**无条件**用 entry 的 rid 覆盖（哨兵就会泄漏）。"""
    return TARGET, _sub(u"            return load_zone(chapter_id, area_id, base).get(scene_id)",
                        u"            _sc = load_zone(chapter_id, area_id, base).get(scene_id)\n"
                        u"            if _sc is not None:\n"
                        u"                _o = entry.get('original_room_id')\n"
                        u"                if isinstance(_o, int):\n"
                        u"                    _sc.original_room_id = _o\n"
                        u"            return _sc", u'override')


CASES = [
    (u'M1 整文件换回 HEAD（回退还在）', m1_revert, (u'B1', u'B2', u'C3', u'C4')),
    (u'M2 删掉 area_id 取值', m2_drop_area, (u'B3',)),
    (u'M3 独立文件分支 return None', m3_solo_none, (u'D1',)),
    (u'M4 from_dict 缺 rid 猜 0', m4_from_dict_guess, (u'A4',)),
    (u'M5 只读一下 entry 的 rid', m5_read_only, (u'B2',)),
    (u'M6 删掉 schema 守卫', m6_no_schema, (u'D3',)),
    (u'M7 删掉路径穿越守卫', m7_no_traversal, (u'D5b',)),
    (u'M8 分片分支无条件用 entry 覆盖', m8_override, (u'C2',)),
]


def main():
    os.makedirs(BAK, exist_ok=True)
    os.system('')
    rc, base = run_check()
    print(u'基线：rc=%d 红项=%r' % (rc, base))
    if rc != 0:
        print(u'★ 基线不绿，先修判据再跑变异。')
        return 2

    hit = 0
    for name, fn, want in CASES:
        p, new = fn()
        before = rd(p)
        h0 = sha(p)
        b = os.path.join(BAK, 'scene_system.py.bak')
        shutil.copy2(p, b)
        try:
            wr(p, new)
            rc, reds = run_check()
            ok = rc != 0 and set(want) <= set(reds)
            hit += 1 if ok else 0
            print(u'%-30s rc=%d 红=%r  期望含%r %s'
                  % (name, rc, reds, list(want), u'✔' if ok else u'✘'))
        finally:
            shutil.copy2(b, p)
        h1 = sha(p)
        assert h1 == h0, u'%s 恢复失败' % p
        assert rd(p) == before, u'%s 字节没还原' % p

    print('')
    print('=' * 70)
    print(u'变异：%d/%d 被抓（且抓的是**针对的那一条**）' % (hit, len(CASES)))
    rc, again = run_check()
    print(u'还原后复跑：rc=%d 红项=%r' % (rc, again))
    print('=' * 70)
    return 0 if hit == len(CASES) and rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
