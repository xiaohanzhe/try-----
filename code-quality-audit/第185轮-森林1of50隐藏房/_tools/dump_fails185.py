# -*- coding: utf-8 -*-
u"""把 run_all.py 里所有套件的 `[FAIL]` 行捞出来（只跑列出来的那几个 id）。

从 run_all.py 的 `SUITES` **静态**读 id -> script（ast，不 import，避免副作用），
再逐个 `subprocess` 跑、`grep [FAIL]`。用法：python dump_fails.py check182 check175 ...
"""
import ast
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = u'C:/Users/23002/Desktop/\u9879\u76ee\u6587\u4ef6\u5939/try - \u526f\u672c'
RUN = os.path.join(REPO, 'code-quality-audit', 'regress', 'run_all.py')

src = io.open(RUN, encoding='utf-8', newline='').read()
tree = ast.parse(src)


def _path_of(v):
    u"""把 `os.path.join(ROOT, 'code-quality-audit', '第xx轮', '_tools', 'check.py')` 解出来。

    ★ 不能 `literal_eval`：那是个 `Call`，第一个实参还是 `ast.Name`（ROOT）。
      做法：只取**字符串常量**实参，拼到仓库根上 —— 与 run_all.py 里的 ROOT 等价。
    """
    if isinstance(v, ast.Constant) and isinstance(v.value, str):
        return v.value
    if isinstance(v, ast.Call):
        parts = [a.value for a in v.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if parts:
            return os.path.join(REPO, *parts)
    return None


MAP = {}
for n in ast.walk(tree):
    if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'SUITES':
        for el in n.value.elts:
            d = {}
            for k, v in zip(el.keys, el.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    d[k.value] = (v.value if isinstance(v, ast.Constant) else _path_of(v))
            if d.get('id') and d.get('script'):
                MAP[d['id']] = d['script']

want = sys.argv[1:]
if not want:
    print(u'用法：dump_fails.py <id> [id...]')
    sys.exit(2)

for wid in want:
    p = MAP.get(wid)
    if not p:
        print(u'%-24s ★ 未找到' % wid)
        continue
    p = p.replace('/', os.sep)
    r = subprocess.run([sys.executable, p], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    fails = [l for l in out.split('\n') if l.startswith('[FAIL]')]
    print('')
    print('=' * 78)
    print('%s  rc=%d  FAIL=%d' % (wid, r.returncode, len(fails)))
    print('=' * 78)
    for l in fails:
        print('  ' + l[:400])
