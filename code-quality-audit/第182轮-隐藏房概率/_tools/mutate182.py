# -*- coding: utf-8 -*-
u"""第182轮 · 变异测试 —— 证明 28 条判据**真的会红**（而不是恒绿）。

做法与第181轮同源：
  · 每条变异都从**源文件**重新生成一份副本，改完跑 `check182.py`（用环境变量指向副本）
    ⇒ 天然幂等，跑两次结果一样，不留残渣；
  · 断言"该红的红"：期望的判据 id 必须出现在 `[FAIL]` 里；
  · 同时断言"不许全红"：报红条数必须**少于总条数**，否则说明副本根本没跑起来
    （那种"整段崩掉、一条 FAIL 都没打"的假象，第178轮踩过）。

判据 id 匹配用 `^\\[FAIL\\] <id>(?![0-9])` —— 防止 `B1` 误配到 `B10` / `B11`。
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PY = sys.executable
CHECK = os.path.join(HERE, 'check182.py')
SRC_MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')
SRC_SR = os.path.join(REPO, 'ralsei_pet', 'modules', 'scene_routing.py')
SRC_ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')

WORK = os.path.join('D:\\_tmp182', 'mut')

TOTAL = 28


def rd(p):
    """读源文件并**统一成 LF**。

    ★ 为什么可以这么做：本脚本只**读**源文件，写出去的全是 `D:\\_tmp182\\mut` 下的副本；
      副本的 EOL 不影响任何判据（`ast.parse` / `json.load` 都认 LF）。
      不统一的话，锚点里写 `\\n` 的替换会在 CRLF 文件上**一条都命中不了** ——
      而那正是第181轮踩过的"夹具不保真"（施工失败却看起来像判据不灵）。
    """
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')


def wr(p, s):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def run_check(env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    r = subprocess.run([PY, CHECK], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, cwd=REPO)
    out = r.stdout.decode('utf-8', 'replace')
    fails = set(m.group(1) for m in re.finditer(r'^\[FAIL\] ([A-D]\d+)(?![0-9])', out, re.M))
    return r.returncode, out, fails


def _subj(txt, old, new, tag):
    """一次文本替换；必须真的命中（否则变异没生效 = 假阴性）。"""
    if old not in txt:
        raise RuntimeError(u'[%s] 锚点不在源文件里：%r' % (tag, old[:60]))
    return txt.replace(old, new, 1)


# ---------------------------------------------------------------------------
#  变异定义：(名字, 说明, 施工函数(返回 env), 期望红的 id)
# ---------------------------------------------------------------------------

def m_disable_ch2(tag):
    s = rd(SRC_ROUTES)
    s = _subj(s, u'"scene_name": "赛博都市·man",\n      "enabled": true,',
              u'"scene_name": "赛博都市·man",\n      "enabled": false,', tag)
    p = os.path.join(WORK, tag, '_routes.json')
    wr(p, s)
    return {'CQ_ROUTES_182': p}


def m_prob_wrong(tag):
    s = rd(SRC_ROUTES)
    s = _subj(s, u'"probability": 0.02,\n      "probability_expr": "ceil(random(50)) == 50",\n'
                 u'      "gate": "scr_sideb_get_phase()',
              u'"probability": 0.5,\n      "probability_expr": "ceil(random(50)) == 50",\n'
              u'      "gate": "scr_sideb_get_phase()', tag)
    p = os.path.join(WORK, tag, '_routes.json')
    wr(p, s)
    return {'CQ_ROUTES_182': p}


def m_drop_evidence(tag):
    s = rd(SRC_ROUTES)
    s = _subj(s, u'"evidence": "第181轮 probe181b.ch1..ch5.json',
              u'"evidence_x": "第181轮 probe181b.ch1..ch5.json', tag)
    p = os.path.join(WORK, tag, '_routes.json')
    wr(p, s)
    return {'CQ_ROUTES_182': p}


def m_once_false(tag):
    s = rd(SRC_ROUTES)
    # ★ 逗号必须留在原处：删掉它会让 JSON 直接非法 ⇒ check182 在 jload 处崩掉、
    #   一条 [FAIL] 都打不出来。那正是"看着抓到了、其实什么都没证明"的假象
    #   （第178轮 M3 同款），所以这里**只改值、不动标点**。
    s = _subj(s, u'"once": true,\n      "status": "data_only",',
              u'"once": false,\n      "status": "data_only",', tag)
    p = os.path.join(WORK, tag, '_routes.json')
    wr(p, s)
    return {'CQ_ROUTES_182': p}


def m_no_seen_check(tag):
    s = rd(SRC_SR)
    s = _subj(s, u'        if once and target in seen:\n            continue\n', u'', tag)
    p = os.path.join(WORK, tag, 'scene_routing.py')
    wr(p, s)
    return {'CQ_MODS_182': os.path.join(WORK, tag)}


def m_le_compare(tag):
    s = rd(SRC_SR)
    s = _subj(s, u'        if 0.0 <= r < p:', u'        if 0.0 <= r <= p:', tag)
    p = os.path.join(WORK, tag, 'scene_routing.py')
    wr(p, s)
    return {'CQ_MODS_182': os.path.join(WORK, tag)}


def m_divert_late(tag):
    """把掷骰那一行搬到 `_travel_commit` 之后 ⇒ C1 的行号判据必须红。"""
    s = rd(SRC_MAIN)
    line = (u'            target = self._maybe_divert_to_hidden(before, target)\n')
    s = _subj(s, line, u'', tag)
    s = _subj(s, u'            return self._travel_commit(target, before)',
              line + u'            return self._travel_commit(target, before)', tag)
    p = os.path.join(WORK, tag, 'main.py')
    wr(p, s)
    return {'CQ_MAIN_182': p}


def m_dump_in_divert(tag):
    s = rd(SRC_MAIN)
    s = _subj(s, u'            _log.info(\'隐藏房掷骰命中 ⇒ 改去 %s（原本要去 %s，p=%s）\',',
              u'            json.dump({}, open(\'x.json\', \'w\'))\n'
              u'            _log.info(\'隐藏房掷骰命中 ⇒ 改去 %s（原本要去 %s，p=%s）\',', tag)
    p = os.path.join(WORK, tag, 'main.py')
    wr(p, s)
    return {'CQ_MAIN_182': p}


def m_no_cur_guard(tag):
    s = rd(SRC_MAIN)
    s = _subj(s, u'            if cur != sid:', u'            if False:', tag)
    p = os.path.join(WORK, tag, 'main.py')
    wr(p, s)
    return {'CQ_MAIN_182': p}


def m_rename(tag):
    s = rd(SRC_MAIN)
    s = _subj(s, u'            os.replace(tmp, path)', u'            os.rename(tmp, path)', tag)
    p = os.path.join(WORK, tag, 'main.py')
    wr(p, s)
    return {'CQ_MAIN_182': p}


def m_no_feedback_commit(tag):
    s = rd(SRC_MAIN)
    s = _subj(s, u'            self._commit_hidden_seen()', u'            pass', tag)
    p = os.path.join(WORK, tag, 'main.py')
    wr(p, s)
    return {'CQ_MAIN_182': p}


MUTS = [
    (u'01_disable_ch2', u'把 ch2 的 enabled 改回 false', m_disable_ch2, ['A2']),
    (u'02_prob_wrong', u'把 ch2 概率 0.02 改成 0.5', m_prob_wrong, ['A3', 'B11']),
    (u'03_drop_evidence', u'抹掉一条登记的 evidence', m_drop_evidence, ['A5']),
    (u'04_once_false', u'把 once 改成 false', m_once_false, ['A3', 'B3']),
    (u'05_no_seen_check', u'删掉 pick_hidden 里的"已发现就跳过"', m_no_seen_check, ['B3']),
    (u'06_le_compare', u'把 `r < p` 改成 `r <= p`', m_le_compare, ['B2']),
    (u'07_divert_late', u'把掷骰搬到换房调用之后', m_divert_late, ['C1']),
    (u'08_dump_in_divert', u'在掷骰那一层加一句 json.dump', m_dump_in_divert, ['C4']),
    (u'09_no_cur_guard', u'把 `cur != sid` 守卫改成 False', m_no_cur_guard, ['C3']),
    (u'10_rename', u'把 os.replace 换成 os.rename', m_rename, ['C5']),
    (u'11_no_feedback_commit', u'删掉收尾里的记账调用', m_no_feedback_commit, ['C2']),
]


def main():
    print(u'第182轮 变异测试 —— %d 条' % len(MUTS))
    print(u'=' * 74)
    _ok = 0
    _rows = []
    for tag, desc, fn, want in MUTS:
        try:
            env = fn(tag)
        except Exception as e:                        # noqa: BLE001
            print(u'[FAIL] %-20s 施工失败：%s' % (tag, e))
            _rows.append((tag, desc, 'SETUP', []))
            continue
        rc, out, fails = run_check(env)
        got = sorted(fails)
        hit = [w for w in want if w in fails]
        # 三重断言：期望的必须红；红的条数必须 < 总数（否则是整段崩掉）
        good = bool(hit) and 0 < len(fails) < TOTAL
        if good:
            _ok += 1
        print(u'[%s] %-20s %s' % ('PASS' if good else 'FAIL', tag, desc))
        print(u'        期望 %r  实红 %r  rc=%d  红 %d/%d'
              % (want, got, rc, len(fails), TOTAL))
        _rows.append((tag, desc, 'PASS' if good else 'FAIL', got))

    # 幂等：整轮再跑一次，结果必须逐字一致
    print(u'-' * 74)
    _second = []
    for tag, desc, fn, want in MUTS[:3]:
        try:
            env = fn(tag)
            _rc, _out, _f2 = run_check(env)
            _second.append(sorted(_f2))
        except Exception:                             # noqa: BLE001
            _second.append(None)
    _again = []
    for tag, desc, fn, want in MUTS[:3]:
        try:
            env = fn(tag)
            _rc, _out, _f2 = run_check(env)
            _again.append(sorted(_f2))
        except Exception:                             # noqa: BLE001
            _again.append(None)
    print(u'[%s] 幂等：同一批变异重跑两次，红项集合逐字一致'
          % ('PASS' if _second == _again else 'FAIL'))
    print(u'=' * 74)
    print(u'被抓 %d / %d' % (_ok, len(MUTS)))
    print(u'=' * 74)

    # 清场：副本目录整个删掉（下次从源重建 ⇒ 幂等）
    try:
        if os.path.isdir(WORK):
            shutil.rmtree(WORK, ignore_errors=True)
    except Exception:                                 # noqa: BLE001
        pass

    return 0 if _ok == len(MUTS) else 1


if __name__ == '__main__':
    sys.exit(main())
