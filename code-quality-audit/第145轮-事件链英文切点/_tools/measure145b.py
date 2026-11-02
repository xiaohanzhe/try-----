# -*- coding: utf-8 -*-
"""第145轮 · A/B：把 ASCII `.` 加进 `_SENTENCE_ENDS`（配过滤）之后，两条链变成什么样。

## 为什么用"HEAD 版 vs 工作区版"而不是复刻夹具

第143轮的教训：**夹具不保真 = 报假问题**。所以这里不重写被测函数，而是
  * 旧版 = `git show HEAD:ralsei_pet/modules/event_speech.py`（真身，落 `D:\\_tmp`）
  * 新版 = 工作区磁盘上的 `ralsei_pet/modules/event_speech.py`
两边都**真 import**，跑同一批语料。

★★ A/B 第一件事是**断言 A ≠ B**：若两份源码 sha1 相同，说明我根本没改到（或改错文件），
  后面所有"有改善"的数字都是假的。

## 判据（与 `measure145.py` 同一个 `cut_midword`）

切在单词中间 ⇔ `res[-1]` 是字母/数字 **且** `t0[len(res)]` 也是字母/数字。
只判右边会把"切在 `。` 之后"全算成坏（中文没有词边界，第一版就这么误判了 3639 条）。
"""
import glob
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
CORPUS = os.path.join(ROOT, 'code-quality-audit',
                      u'第113轮-全体角色AI训练', '_evidence', 'raw30')
NEW_PATH = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')
TMP = r'D:\_tmp'
OLD_PATH = os.path.join(TMP, '_es145_head.py')

CJK = re.compile(u'[\u4e00-\u9fff]')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lang_of(s):
    letters = [c for c in s if c.strip()]
    if not letters:
        return 'none'
    return 'zh' if len(CJK.findall(s)) * 1.0 / len(letters) >= 0.30 else 'en'


def norm(t):
    t = t.strip()
    return t.strip(u'"\'“”「」『』《》').strip()


def mid(res, t0):
    if not res or not t0 or len(res) >= len(t0):
        return False
    return res[-1].isalnum() and t0[len(res)].isalnum()


def main():
    out_old = subprocess.run(
        ['git', 'show', 'HEAD:ralsei_pet/modules/event_speech.py'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    src_old = out_old.stdout
    if not src_old.strip():
        print(u'[FATAL] 取不到 HEAD 版 event_speech.py')
        return 2
    if not os.path.isdir(TMP):
        os.makedirs(TMP)
    with open(OLD_PATH, 'wb') as f:
        f.write(src_old)

    sha_old = hashlib.sha1(src_old).hexdigest()
    with open(NEW_PATH, 'rb') as f:
        sha_new = hashlib.sha1(f.read()).hexdigest()
    print(u'A/B 前置：old sha1=%s ｜ new sha1=%s' % (sha_old[:12], sha_new[:12]))
    if sha_old == sha_new:
        print(u'[FATAL] 两份源码**完全相同** ⇒ 没改到，A/B 无意义')
        return 2
    print(u'✅ A ≠ B（真改到了）')

    OLD = load(OLD_PATH, 'es145_old')
    NEW = load(NEW_PATH, 'es145_new')

    rows = []
    for p in sorted(glob.glob(os.path.join(CORPUS, '*.jsonl'))):
        nid = os.path.splitext(os.path.basename(p))[0]
        with io.open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                for tr in (rec.get('turns') or []):
                    txt = tr.get('final') or ''
                    if not isinstance(txt, str) or not txt.strip():
                        continue
                    t0 = norm(txt)
                    if not t0:
                        continue
                    o24, n24 = OLD.first_sentence(txt), NEW.first_sentence(txt)
                    o40, n40 = OLD.fit_sentences(txt), NEW.fit_sentences(txt)
                    rows.append({
                        'id': nid, 'i': tr.get('i'), 'lang': lang_of(t0),
                        'o24': o24, 'n24': n24, 'o40': o40, 'n40': n40,
                        'mid_o24': mid(o24, t0), 'mid_n24': mid(n24, t0),
                        'mid_o40': mid(o40, t0), 'mid_n40': mid(n40, t0),
                        'changed24': o24 != n24, 'changed40': o40 != n40,
                        'raw': t0[:120],
                    })

    def agg(sub):
        return {
            'turns': len(sub),
            'mid24': [sum(1 for r in sub if r['mid_o24']),
                      sum(1 for r in sub if r['mid_n24'])],
            'mid40': [sum(1 for r in sub if r['mid_o40']),
                      sum(1 for r in sub if r['mid_n40'])],
            'changed24': sum(1 for r in sub if r['changed24']),
            'changed40': sum(1 for r in sub if r['changed40']),
        }

    zh = [r for r in rows if r['lang'] == 'zh']
    en = [r for r in rows if r['lang'] == 'en']
    diff24 = [r for r in rows if r['changed24']]
    diff40 = [r for r in rows if r['changed40']]
    diff24_zh = [r for r in diff24 if r['lang'] == 'zh']

    out = {
        'note': (u'第145轮 A/B：old = HEAD 版 event_speech.py，new = 工作区版'
                 u'（`_SENTENCE_ENDS` 加 ASCII `.` + `_sentence_ends()` 过滤）。'
                 u'mid = 切点两侧都是字母/数字。'),
        'sha1': {'old': sha_old, 'new': sha_new},
        'all': agg(rows), 'zh': agg(zh), 'en': agg(en),
        'diff': {'d24': len(diff24), 'd40': len(diff40),
                 'd24_zh': len(diff24_zh), 'd24_en': len(diff24) - len(diff24_zh)},
        'sample_en_fixed': [
            {'id': r['id'], 'i': r['i'], 'old': r['o24'], 'new': r['n24']}
            for r in diff24 if r['lang'] == 'en'][:10],
        'sample_zh_changed': [
            {'id': r['id'], 'i': r['i'], 'old': r['o24'], 'new': r['n24'],
             'raw': r['raw']} for r in diff24_zh][:10],
    }
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(os.path.join(EV, 'ab145.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))

    print(u'')
    print(u'%-4s %6s  %-22s %-22s  %s' % (u'', u'条数',
                                          u'24 字切在词中(old→new)',
                                          u'40 字切在词中(old→new)', u'输出变了'))
    for k, label in (('all', u'全部'), ('zh', u'中文'), ('en', u'英文')):
        a = out[k]
        print(u'%-4s %6d  %5d → %-5d (%+.1f)   %5d → %-5d (%+.1f)   24:%d 40:%d'
              % (label, a['turns'], a['mid24'][0], a['mid24'][1],
                 a['mid24'][1] - a['mid24'][0], a['mid40'][0], a['mid40'][1],
                 a['mid40'][1] - a['mid40'][0], a['changed24'], a['changed40']))
    print(u'')
    print(u'英文 24 字修好的样例：')
    for s in out['sample_en_fixed']:
        print(u'  [%s#%s]\n     old=%r\n     new=%r' % (s['id'], s['i'],
                                                        s['old'], s['new']))
    print(u'')
    print(u'中文侧变了的 %d 条（必须每条都是"变得更好或至少不更差"）：'
          % len(diff24_zh))
    for s in out['sample_zh_changed']:
        print(u'  [%s#%s] old=%r new=%r ｜ raw=%r'
              % (s['id'], s['i'], s['old'], s['new'], s['raw'][:60]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
