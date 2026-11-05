# -*- coding: utf-8 -*-
u"""第163轮变异测试：证明 `check163.py` 的判据**真会报红**。

铁律：夹具不保真 = 报假问题；判据恒绿 = 比不写还危险。
本支每次都把 `main.py` 复制到 `%TEMP%\\mut163\\main.py` 再改**副本**，
通过 `CQ_SRC_DIR` 喂给 check163 —— **产品文件一个字节都不动**。

每个变异体都必须让 check163 至少 FAIL 一条；若某个变异体全绿 ⇒ 报「判据漏守」。

跑法：C:\\Python311\\python.exe mutate163.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
REAL_MAIN = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check163.py')
WORK = os.path.join(tempfile.gettempdir(), 'mut163')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_ORIG_RAW = io.open(REAL_MAIN, encoding='utf-8', newline='').read()
# ★ 锚点匹配要按 LF 归一：产品文件是 CRLF，多行 old 串用 `\n` 匹配不上
#   （第一版就是这里让 M2/M4 报"锚点没找到"）。写变体时再转回 CRLF，保持原 EOL。
_ORIG = _ORIG_RAW.replace('\r\n', '\n')


def run_check(src_dir):
    env = dict(os.environ)
    env['CQ_SRC_DIR'] = src_dir
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, CHECK], capture_output=True, env=env,
                       cwd=HERE, timeout=300)
    # ★ 必须合并 stderr：第一版只看 stdout，于是"套件在 import 阶段崩掉"
    #   （stdout 空、traceback 在 stderr）被判成"全绿 ⇒ 漏守"。
    out = (p.stdout or b'').decode('utf-8', 'replace')
    err = (p.stderr or b'').decode('utf-8', 'replace')
    fails = re.findall(r'\[FAIL\] (.+)', out)
    return p.returncode, fails, out + err


def make_variant(name, transform):
    """transform(orig) -> new；返回 (variant_dir, 是否有实际改动)。"""
    new = transform(_ORIG)
    if new == _ORIG:
        return None, False
    d = os.path.join(WORK, name)
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, 'main.py'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(new.replace('\n', '\r\n'))      # 还原产品原本的 CRLF
    return d, True


MUTANTS = []


def mutant(name, desc):
    def deco(fn):
        MUTANTS.append((name, desc, fn))
        return fn
    return deco


@mutant('M1', u'垂直落位退回"钉中心"（本次修复的反向）')
def _m1(s):
    old = '            dy = ch - int(round(_bb_bottom * scale_factor))'
    new = ('            dy = (ch - sprite.height()) // 2 '
           '- int(round(_off_y * scale_factor))')
    assert old in s, 'M1 锚点没找到'
    return s.replace(old, new, 1)


@mutant('M2', u'`_anim_anchor_bottom` 恒返回 None（全退回中心口径）')
def _m2(s):
    old = '''        vals = bcache.get(animation)
        if not vals:
            return None'''
    new = '''        vals = bcache.get(animation)
        if not vals:
            return None
        return None'''
    assert old in s, 'M2 锚点没找到'
    return s.replace(old, new, 1)


@mutant('M3', u'`_compose_anchored_sprite` 不再使用本体下沿（拿到也不用）')
def _m3(s):
    # ★ 产品后来为了兼容旧桩把直接调用改成了 `getattr(...)` + `_ab(...)`，
    #   所以变异锚点要跟着改（旧串 `_bb_bottom = self._anim_anchor_bottom(...)` 已不存在）。
    old = '            _bb_bottom = _ab(animation, frame_index)'
    new = '            _bb_bottom = None'
    assert old in s, 'M3 锚点没找到'
    return s.replace(old, new, 1)


@mutant('M4', u'新缓存字段与旧缓存重名（同表不同键 ⇒ 静默错值）')
def _m4(s):
    # 只改 `_anim_anchor_offsets` 里写 bcache 的那几处，制造"同一张表存两种值"
    old = '''        bcache = getattr(self, '_anim_bottom_cache', None)
        if bcache is None:
            bcache = {}
            self._anim_bottom_cache = bcache'''
    new = '''        bcache = cache'''
    assert old in s, 'M4 锚点没找到'
    return s.replace(old, new, 1)


@mutant('M5', u'少一处合成调用点（静止分支不再走合成）')
def _m5(s):
    """把**第二处** `self._compose_anchored_sprite(...)` 整段调用（含配对括号里的参数）
    替换成 `scaled_sprite`。★ 必须吃掉整个调用：第一版只替换到左括号就收手，
    剩下的实参成了语法错（IndentationError），于是"被 B0 抓"而不是"被 B4 抓"——
    变异不保真，等于没测到 B4。"""
    marker = 'cached_sprite = self._compose_anchored_sprite('
    i1 = s.find(marker)
    assert i1 >= 0, 'M5 找不到第一个调用点'
    i2 = s.find(marker, i1 + 1)
    assert i2 >= 0, 'M5 找不到第二个调用点'
    start = i2 + len('cached_sprite = ')
    open_idx = s.index('(', start)
    depth = 0
    j = open_idx
    while j < len(s):
        if s[j] == '(':
            depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    assert depth == 0, 'M5 括号没配对'
    return s[:i2] + 'cached_sprite = scaled_sprite' + s[j + 1:]


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    print('=' * 66)
    print('基线：未变异的产品原文')
    print('=' * 66)
    rc, fails, out = run_check(os.path.join(PET, 'src'))
    print('  returncode=%d  FAIL 条数=%d' % (rc, len(fails)))
    base_green = (rc == 0 and not fails)
    if not base_green:
        print('  [!] 基线本身不绿，变异测试无意义，先修基线：')
        for f in fails:
            print('      - %s' % f)
        return 1
    print('  [PASS] 基线全绿（否则"变异后报红"无法归因）')

    n_caught = 0
    missed = []
    for name, desc, fn in MUTANTS:
        print('\n' + '-' * 66)
        print('%s  %s' % (name, desc))
        try:
            vdir, changed = make_variant(name, fn)
        except AssertionError as e:
            print('  [SKIP] 变异锚点失效（产品代码已变，需更新本支）：%s' % e)
            missed.append('%s(锚点失效)' % name)
            continue
        if not changed:
            print('  [SKIP] 变异后与原文一致，等于没改')
            missed.append('%s(空变异)' % name)
            continue
        rc2, fails2, out2 = run_check(vdir)
        # ★ 非零退出也算"抓住"：变异若把文件改出语法错/让套件崩掉，那同样证明
        #   判据所在的那棵树**不再是绿的**（第一版只认 `[FAIL]` 行，把这种情况
        #   误判成"漏守"）。但仍要求它至少打出点东西，避免"根本没跑起来"混过去。
        if rc2 != 0 and (fails2 or out2.strip()):
            n_caught += 1
            if fails2:
                print('  [CAUGHT] 报红 %d 条：' % len(fails2))
                for f in fails2:
                    print('      - %s' % f)
            else:
                print('  [CAUGHT] 套件非零退出（无 [FAIL] 行，崩溃/语法错也算失败）')
        else:
            print('  [MISSED] 变异后依然全绿 ⇒ 判据漏守！')
            missed.append(name)

    print('\n' + '=' * 66)
    print('变异 %d 个：抓住 %d / 漏 %d' % (len(MUTANTS), n_caught, len(missed)))
    if missed:
        print('漏守：%s' % missed)
        return 1
    print('[PASS] 全部变异体都被判据抓住')
    return 0


if __name__ == '__main__':
    sys.exit(main())
