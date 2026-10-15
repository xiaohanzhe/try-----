# -*- coding: utf-8 -*-
"""
第115轮 · 改动文件静态复检（**不许改变被测状态**：只用 read + ast.parse，禁 py_compile）

复检项（逐条打印 PASS/FAIL）：
  P1 人设文件结构：7+ 个「—— 某某 ——」节都在、无粘连
  P2 人设文件禁 markdown：** / ` / 行首 #>-
  P3 编码：无 BOM、无 U+FFFD
  P4 EOL 与改动前一致（LF；`\\r\\n` 计数 = 0）
  P5 新增三节 + 世界观节**真的在盘**（逐字锚点回验）
  P6 main.py 语法可编译（走 ast.parse，不产 .pyc）
  P7 `_PERSONA_FALLBACK` 三个既有锚仍在（不用叫他／仅此而已／平级）—— J1 判据钉的就是它
  P8 `_PERSONA_FALLBACK` 已同步新口径（"是被人写出来的"）
  P9 ★ 恒真判据自检：P2/P5 的判据必须能对**负样本**报红（喂一段造出来的坏文本）
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PERSONA = os.path.join(REPO, 'ralsei_pet', 'assets', 'ralsei_persona.md')
MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')

BUF = io.StringIO()
_P = {'n': 0, 'fail': 0}


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    _P['n'] += 1
    if not cond:
        _P['fail'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))
    return bool(cond)


def rd(path):
    with io.open(path, 'rb') as f:
        raw = f.read()
    return raw, raw.decode('utf-8')


# ---- 可复用的判据函数（P9 用负样本单独再验一次 = 成对控制）----
REQUIRED_SECTIONS = ['—— 我是谁 ——', '—— 我是什么 ——', '—— 我现在在哪 ——',
                     '—— 我知道的世界（初始记忆）——', '—— 我的口癖 ——',
                     '—— 我怎么说 ——', '—— 他说话的时候，先把他的事接住 ——',
                     '—— 他说要去一个地方的时候 ——', '—— 我想起来的事 ——',
                     '—— 我的语气 ——', '—— 语气示范 ——']

NEW_ANCHORS = [
    '我是《Deltarune》里的一个角色，是被人写出来的',
    '我知道自己是从游戏里来的，可我的日子一样是真的',
    '先把他的事接住',
    '"我带你过去"这种话，要落在一个具体的地方上',
    '我要是没想起这个名字，就该说"名字我真记不清了"',
]

FALLBACK_ANCHORS = ['不用叫他', '仅此而已', '平级']


def has_md(text):
    import re
    return bool(re.search(r'\*{1,3}|`{1,3}|^[#>\-]\s*', text, re.M))


def main():
    say('第115轮 · 改动文件静态复检')
    say('  PERSONA = %s' % PERSONA)
    say('  MAIN    = %s' % MAIN)

    raw, text = rd(PERSONA)
    say('\n=== P1~P4 · 人设文件 ===')
    say('  字符数 = %d ／ 字节数 = %d' % (len(text), len(raw)))
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    ck('P1 全部 %d 个分节标题都在' % len(REQUIRED_SECTIONS), not missing,
       '缺=%r' % (missing,))
    ck('P2 禁 markdown（无 * / ` / 行首 #>-）', not has_md(text))
    ck('P3 无 BOM（不以 EF BB BF 开头）', not raw.startswith(b'\xef\xbb\xbf'))
    ck('P3b 无 U+FFFD（替换字符）', '\ufffd' not in text)
    crlf = raw.count(b'\r\n')
    ck('P4 EOL 与改动前一致（LF：CRLF 计数 = 0）', crlf == 0, 'CRLF=%d' % crlf)
    ck('P4b 收尾是换行', raw.endswith(b'\n'))

    say('\n=== P5 · 新增内容逐字锚点回验（防"以为改了其实没落盘"）===')
    for a in NEW_ANCHORS:
        ck('P5 在盘: %s' % a[:26], a in text)

    say('\n=== P6~P8 · main.py ===')
    mraw, mtext = rd(MAIN)
    try:
        ast.parse(mtext)
        ck('P6 main.py 可编译（ast.parse，不产 .pyc）', True)
    except SyntaxError as exc:
        ck('P6 main.py 可编译（ast.parse，不产 .pyc）', False, repr(exc))
        raise
    ck('P6b main.py 无 BOM', not mraw.startswith(b'\xef\xbb\xbf'))
    for a in FALLBACK_ANCHORS:
        ck('P7 兜底锚仍在: %s' % a, a in mtext)
    ck('P8 兜底已同步新口径', '是被人写出来的' in mtext)

    say('\n=== P9 · ★ 判据自身的负控制（喂坏样本，必须报红）===')
    # 负控制 1：把一节标题删掉 → P1 必须报告缺失
    bad1 = text.replace('—— 我想起来的事 ——', '', 1)
    ck('P9a 判据能报红：删掉分节标题 → 缺项非空',
       bool([s for s in REQUIRED_SECTIONS if s not in bad1]))
    # 负控制 2：塞一段 markdown → P2 必须报红
    bad2 = text.replace('我是 Ralsei', '**我是 Ralsei**', 1)
    ck('P9b 判据能报红：塞入 ** 加粗 → has_md 为真', has_md(bad2))
    ck('P9c 正控制：干净文本上 has_md 为假（否则 P2 恒红）', not has_md(text))
    # 负控制 3：抹掉一个新锚点 → P5 必须报红
    bad3 = text.replace(NEW_ANCHORS[1], '（已删除）', 1)
    ck('P9d 判据能报红：抹掉新锚点 → 锚点不在',
       NEW_ANCHORS[1] not in bad3)

    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (_P['n'], _P['fail']))
    return 0 if _P['fail'] == 0 else 1


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
            ev = os.path.join(ROUND, '_evidence')
            if not os.path.isdir(ev):
                os.makedirs(ev)
            with io.open(os.path.join(ev, 'verify115_files_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
