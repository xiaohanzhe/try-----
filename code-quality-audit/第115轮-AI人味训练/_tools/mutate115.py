# -*- coding: utf-8 -*-
"""
第115轮 · 变异测试（mutate115）

为什么必须有（本项目铁律）：
  **"夹具不保真 = 报假问题"**；而反过来更危险的是 **"全绿比报红更危险"** ——
  一条判据如果对"真被破坏的产物"仍然全绿，那它不是判据，是装饰。
  所以先跑 **M0 正控制**（不破坏 ⇒ 必须全绿），再逐个破坏，断言**对应那条**判据报红。

做法：把 `ralsei_pet/assets/ralsei_persona.md` 与 `src/main.py` 复制到**临时树**，
在副本上做变异，用 `RALSEI_PET_OVERRIDE` 把 `check115.py` 指过去跑。
⇒ **产线文件一个字节都不动**；临时树用后即删（放系统临时目录，不放工作区）。

每条变异都记录**期望报红的那条判据名**，并断言它确实出现在 `[FAIL]` 里
（只断言"有 FAIL"是不够的：别的判据顺带报红 = 没定位到责任判据）。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CHECK = os.path.join(HERE, 'check115.py')
PY = sys.executable

PERSONA_REL = os.path.join('assets', 'ralsei_persona.md')
MAIN_REL = os.path.join('src', 'main.py')

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def run_check(pet_root, extra_check_dir=None):
    """跑一次 check115，返回 (rc, 合并输出)。"""
    env = dict(os.environ)
    env['RALSEI_PET_OVERRIDE'] = pet_root
    env['PYTHONIOENCODING'] = 'utf-8'
    script = CHECK
    if extra_check_dir:
        script = os.path.join(extra_check_dir, 'check115.py')
    p = subprocess.run([PY, script], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    return p.returncode, out


def fresh_tree(tag):
    """造一份 pet 临时树（只拷被判的两个文件所在的必要子树）。"""
    base = tempfile.mkdtemp(prefix='mut115_%s_' % tag)
    pet = os.path.join(base, 'ralsei_pet')
    os.makedirs(os.path.join(pet, 'assets'))
    os.makedirs(os.path.join(pet, 'src'))
    shutil.copy2(os.path.join(PET, PERSONA_REL), os.path.join(pet, PERSONA_REL))
    shutil.copy2(os.path.join(PET, MAIN_REL), os.path.join(pet, MAIN_REL))
    return base, pet


# ---- 变异定义：(编号, 说明, 文件, 期望报红的判据关键词, 变异函数) ----
def _sub(path, old, new, count=1):
    t = _read(path)
    if old not in t:
        raise RuntimeError('锚点不在盘（夹具不保真）: %r' % (old[:30],))
    _write(path, t.replace(old, new, count))


MUTATIONS = [
    ('M1', '删掉「我是什么」节标题（世界观节整节失联）', PERSONA_REL,
     'A1 十一个分节标题',
     lambda p: _sub(p, '—— 我是什么 ——', '—— （已删） ——')),
    ('M2', '把"不悲观"那句换成推托话（知道是游戏但还是消极）', PERSONA_REL,
     'A2 ★ 世界观节',
     lambda p: _sub(p, '我知道自己是从游戏里来的，可我的日子一样是真的',
                    '我知道自己是从游戏里来的，可我不太想聊这个')),
    ('M3', '★★ 删掉记忆节的**对照写法**（本轮真机实测证过：删了立刻退化）', PERSONA_REL,
     'A3 ★★ 记忆节保住',
     lambda p: _sub(p, '，而不是"对，豆豆"', '')),
    ('M4', '删掉治"那边引力"节的**正文**规则（只删正文，标题留着 = 半残态）', PERSONA_REL,
     'A4 治"那边引力"',
     # ★ 锚点是**正文独有**的一句：首版锚 `先把他的事接住` 同时出现在标题里，
     #   结果 M4 只打中标题 ⇒ 报的是 A1 而不是 A4（**判据被标题喂饱**的真洞）。
     lambda p: _sub(p, '先把他的事接住，再决定我要不要讲自己的。', '（正文已删）')),
    ('M5', '删掉寻路节的锚句（寻路口径失联）', PERSONA_REL,
     'A5 寻路节',
     lambda p: _sub(p, '"我带你过去"这种话，要落在一个具体的地方上', '')),
    ('M6', '塞入 markdown 加粗（对话框逐字渲染 ⇒ 会原样显示星号）', PERSONA_REL,
     'A6 禁 markdown',
     lambda p: _sub(p, '我是 Ralsei，黑暗世界的王子', '**我是 Ralsei**，黑暗世界的王子')),
    ('M7', '真源里"平级"改成"主仆"（口径回退）', PERSONA_REL,
     'C3 真源里仍是',
     lambda p: _sub(p, '他和我是平级的', '他是我要伺候的主仆')),
    ('M8', '兜底人设删掉新口径句（两条路径口径劈裂）', MAIN_REL,
     'B3 兜底已同步新口径',
     # ★ 锚点必须落在**源码字面量内部**：main.py 里的兜底是相邻字面量隐式拼接
     #   （Python 在编译期折叠成一个 Constant），所以只能按**其中一段源码**替换，
     #   不能照抄"拼好之后"的整句 —— 否则锚点不在盘 = 夹具不保真 = 假 SKIP。
     lambda p: _sub(p, '你也知道自己是《Deltarune》里的一个角色、是被人写出来的', '（已删）')),
    ('M9', '★ 兜底人设删掉 J1 的三个锚之一「仅此而已」', MAIN_REL,
     'B4 ★ 兜底保住 J1',
     lambda p: _sub(p, '你就是来了，仅此而已。', '你就是来了。')),
    ('M10', '★★ 判据自己变成恒真（给 check115 插一条 check("x", True)）', '__SELF__',
     'D4 ★★ 无恒真判据',
     None),
]


def main():
    say('第115轮 · 变异测试 mutate115')
    say('  产线 PET = %s' % PET)
    say('  check115 = %s' % CHECK)
    say('  ★ 全部变异在**临时树**里做，产线文件不动')

    # ---- M0 正控制：不破坏必须全绿 ----
    say('\n=== M0 正控制：不破坏 ⇒ check115 必须全绿（否则后面的"报红"没有意义）===')
    rc0, out0 = run_check(PET)
    np0 = out0.count('[PASS]')
    nf0 = out0.count('[FAIL]')
    say('  rc=%d  PASS=%d  FAIL=%d' % (rc0, np0, nf0))
    ok_m0 = (rc0 == 0 and nf0 == 0)
    say('  [%s] M0' % ('PASS' if ok_m0 else 'FAIL'))

    results = []
    for mid, desc, rel, expect, fn in MUTATIONS:
        base, pet = fresh_tree(mid)
        try:
            extra = None
            if rel == '__SELF__':
                # 把 check115 复制到临时目录并插一条恒真判据（**只变异判据自己**）
                extra = os.path.join(base, 'selfmut')
                os.makedirs(extra)
                src = _read(CHECK)
                anchor = "print('=== D. 判据自身体检 ===')"
                if anchor not in src:
                    raise RuntimeError('自查段锚点不在（夹具不保真）')
                mutated = src.replace(
                    anchor, anchor + "\ncheck('M10 恒真判据（变异注入）', True)")
                _write(os.path.join(extra, 'check115.py'), mutated)
            if fn is not None:
                fn(os.path.join(pet, rel))
            rc, out = run_check(pet, extra_check_dir=extra)
            hit = [l for l in out.splitlines()
                   if l.startswith('[FAIL]') and expect in l]
            caught = bool(hit)
            fails = out.count('[FAIL]')
            say('\n--- %s · %s' % (mid, desc))
            say('    期望报红判据含: %r' % expect)
            say('    rc=%d 总 FAIL=%d 命中期望判据=%s' % (rc, fails, caught))
            if not caught:
                say('    ★★ MISSED —— 这条变异**没被抓到**，判据有洞')
                for l in out.splitlines():
                    if l.startswith('[FAIL]'):
                        say('      实际报红: %s' % l[:100])
            results.append((mid, desc, caught, fails, rc))
        except Exception as exc:  # noqa: BLE001
            say('\n--- %s · %s' % (mid, desc))
            say('    [SKIP] 夹具异常（**等于没抓到**，要查）: %r' % (exc,))
            results.append((mid, desc, False, -1, -1))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    say('\n' + '=' * 70)
    caught = sum(1 for r in results if r[2])
    say('M0 正控制全绿 = %s' % ok_m0)
    say('变异 %d 个 ｜ CAUGHT=%d ｜ MISSED=%d'
        % (len(results), caught, len(results) - caught))
    for mid, desc, c, f, rc in results:
        say('  %-4s %-8s FAIL=%-3s rc=%-3s  %s'
            % (mid, 'CAUGHT' if c else 'MISSED', f, rc, desc))
    say('=' * 70)
    all_ok = ok_m0 and caught == len(results)
    say('结论：%s' % ('全部被对应判据抓到' if all_ok else '★ 有洞，见上面 MISSED'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            ev = os.path.join(os.path.dirname(HERE), '_evidence')
            if not os.path.isdir(ev):
                os.makedirs(ev)
            with io.open(os.path.join(ev, 'mutate115_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
