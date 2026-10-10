# -*- coding: utf-8 -*-
u"""mutate103.py —— `check103` 的**变异测试**：把产品弄坏，看锁会不会报红。

为什么必须做：一条锁"全绿"有两种可能 ——
  ① 产品真的对；② 判据恒真（写错了、量错了东西、或根本没走到那条分支）。
只看绿是分不出 ①② 的。本脚本对每个"守点"造一次**保真**的破坏，
要求**指定判据由绿变红**；跑完立刻还原并**逐字节核验还原成功**。

铁律（第85~96轮反复踩过）：
  * 破坏必须**真的破坏**（改数据面，不是改判据）；
  * 判据报红之后要**先怀疑判据**（见注释里标 `★ 判据侧` 的两处 —— 历史上都出过）；
  * 还原要**逐字节**核对哈希，不是"我改回来了"。
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BAK = os.path.join(os.environ.get('TEMP') or '/tmp', 'bak103_mutate')
PY = sys.executable


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def read_raw(p):
    return io.open(p, encoding='utf-8', newline='').read()


def write_raw(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)


TARGETS = [os.path.join(SCENES, f) for f in sorted(os.listdir(SCENES))
           if f.startswith('_zone.oneshot.')]
TARGETS += [os.path.join(EV, 'cells103.json'),
            os.path.join(EV, 'grid_anchor103.json'),
            os.path.join(SCENES, '_index.json')]

os.makedirs(BAK, exist_ok=True)
orig = {}
for p in TARGETS:
    b = os.path.join(BAK, os.path.basename(p).replace(os.sep, '_'))
    shutil.copy2(p, b)
    orig[p] = sha(p)
print('备份 %d 个文件 -> %s' % (len(TARGETS), BAK))


def run_check():
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    pr = subprocess.run([PY, os.path.join(HERE, 'check103.py')], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'^\[FAIL\] (\S+)', out, re.M)
    return pr.returncode, fails


def restore():
    bad = []
    for p in TARGETS:
        b = os.path.join(BAK, os.path.basename(p).replace(os.sep, '_'))
        shutil.copy2(b, p)
        if sha(p) != orig[p]:
            bad.append(p)
    return bad


def pick_obj(zone_needle, idx=0):
    """在某个分片里找第 idx 个物件，返回 (路径, 场景id, 物件的可变引用所需的文本锚)。"""
    for f in sorted(os.listdir(SCENES)):
        if not f.startswith('_zone.oneshot.'):
            continue
        if zone_needle and zone_needle not in f:
            continue
        d = json.loads(re.sub(r',(\s*[}\]])', r'\1', read_raw(os.path.join(SCENES, f))))
        for sid, ent in (d.get('scenes') or {}).items():
            if isinstance(ent, dict) and ent.get('objects'):
                return os.path.join(SCENES, f), sid, ent['objects'][idx]
    return None, None, None


CASES = []


# ---------------------------------------------------------------- 变异 1：pos +1
def m1():
    path, sid, o = pick_obj('refuge')
    t = read_raw(path)
    pos = json.dumps(o['pos'], separators=(',', ':'))
    assert t.count(pos) >= 1, pos
    write_raw(path, t.replace(pos, json.dumps([o['pos'][0] + 1, o['pos'][1]],
                                              separators=(',', ':')), 1))
    return 'A4', '把 %s 的第 1 个物件 `pos[0]` +1px（栅格/锚点判据必须抓到）' % sid


# ---------------------------------------------------------------- 变异 2：depth +1
def m2():
    path, sid, o = pick_obj('refuge')
    t = read_raw(path)
    need = '"pos":%s' % json.dumps(o['pos'], separators=(',', ':'))
    i = t.index(need)
    j = t.index('"depth":', i)
    k = t.index(',', j)
    old = t[j:k]
    write_raw(path, t[:j] + old.replace(str(o['depth']), str(o['depth'] + 1)) + t[k:])
    return 'C9', '把 %s 一个物件的 `depth` +1（等于地面线 → 偏 1px，必须被抓到）' % sid


# ---------------------------------------------------------------- 变异 3：sprite 指向不存在的格
def m3():
    path, sid, o = pick_obj('refuge')
    t = read_raw(path)
    write_raw(path, t.replace(o['sprite'], o['sprite'].replace('.png', '_X.png'), 1))
    return 'B8', '把 %s 一个物件的 `sprite` 改成不存在的格名（"多切/少切"必须抓到）' % sid


# ---------------------------------------------------------------- 变异 4：篡改格清单的 sha
def m4():
    p = os.path.join(EV, 'cells103.json')
    t = read_raw(p)
    old = '"sha256": "'
    i = t.index(old) + len(old)
    j = t.index('"', i)
    t = t[:i] + ('0' * (j - i)) + t[j:]
    write_raw(p, t)
    return 'B3', '把 `cells103.json` 里第 1 条的 sha256 改成全 0（逐张对账必须抓到）'


# ---------------------------------------------------------------- 变异 5：删掉索引里的声明
def m5():
    p = os.path.join(SCENES, '_index.json')
    t = read_raw(p)
    m = re.search(r'\n[ \t]*"objects_source":.*', t)
    assert m, '找不到 objects_source 行'
    # 删**整行**（连它前面的换行一起删）。★ 别用 `,` 顶替 —— 上一行末尾已经有逗号，
    #   再补一个会造出 `,,` ⇒ JSON 直接不合法 ⇒ 锁在 `jload` 处崩掉，
    #   报出来的是"进程异常"而不是"C12 报红"，变异测试就会误判成"判据没抓到"。
    write_raw(p, t[:m.start()] + t[m.end():])
    return 'C12', '把 `_index.json` 的 `meta.objects_source` 声明删掉（"偏差已声明"必须抓到）'


# ---------------------------------------------------------------- 变异 6：把索引内联也填上物件
def m6():
    p = os.path.join(SCENES, '_index.json')
    t = read_raw(p)
    # ★ 必须打**oneshot 章**里的那条 —— 索引里 `desktop`/`ch1` 等场景也有
    #   `"objects": []`，随手 `re.search` 会打到别的章，C11 只查 oneshot ⇒ 打不中。
    i = t.index('"oneshot.')
    j = t.index('"objects": []', i)
    t = t[:j] + '"objects": [{"pos": [0, 0]}]' + t[j + len('"objects": []'):]
    write_raw(p, t)
    return 'C11', ('把 `_index.json` 里第 1 个 **oneshot** 内联副本的 `objects` 填成非空'
                   '（"两层偏差"必须抓到）')


# ---------------------------------------------------------------- 变异 7：证据等级降格
def m7():
    p = os.path.join(EV, 'grid_anchor103.json')
    d = json.load(io.open(p, encoding='utf-8'))
    d['anchor']['horizontal'] = u'authored（推导）'
    io.open(p, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(d, ensure_ascii=False, indent=1))
    return 'A6', '把横向锚点证据等级从 `proven_by_pixel` 降回 `authored`（不许悄悄降级）'


CASES = [('M1', m1), ('M2', m2), ('M3', m3), ('M4', m4),
         ('M5', m5), ('M6', m6), ('M7', m7)]

ok_all = True
print()
print('=' * 96)
print('变异测试（每个变异：破坏 → 跑锁 → 要求**指定判据报红** → 还原 → 逐字节核验）')
print('=' * 96)
rc0, f0 = run_check()
print('变异前基线：exit=%d FAIL=%s' % (rc0, f0[:3] or '(无)'))
if rc0 != 0 or f0:
    print('⚠️ 基线就是红的 —— 先修基线，别拿红基线做变异测试')
    sys.exit(1)

for name, fn in CASES:
    where, desc = fn()
    rc, fails = run_check()
    hit = any(f.startswith(where) for f in fails)
    print('%-4s %s' % (name, desc))
    print('     期望判据 %-4s 报红 -> %s ｜ 实际红：%s'
          % (where, hit, fails[:6] or '(无)'))
    if not hit:
        ok_all = False
    bad = restore()
    if bad:
        print('     ❌ 还原失败：%s' % bad)
        ok_all = False
    else:
        rc2, f2 = run_check()
        print('     还原后锁：exit=%d FAIL=%s' % (rc2, f2[:2] or '(无)'))
        if f2:
            ok_all = False

print()
bad = restore()
if bad:
    print('❌ 最终还原核验失败：%s' % bad)
    sys.exit(1)
print('★ 终态：所有被改文件与备份**逐字节相同**（%d 个）' % len(TARGETS))
rc, fails = run_check()
print('★ 终态锁：exit=%d FAIL=%d' % (rc, len(fails)))
print()
if ok_all and rc == 0 and not fails:
    print('变异测试通过：7 个变异**全部**被对应判据抓到，锁有鉴别力')
    sys.exit(0)
print('变异测试未通过（见上）')
sys.exit(1)
