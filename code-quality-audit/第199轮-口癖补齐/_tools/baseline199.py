# -*- coding: utf-8 -*-
"""第199轮 · 生成判据用的**派生基线**（小文件），并把原始备份搬出工作区

为什么不能把 76 份人设备份直接放进仓库：
  · 那是 1.4 MB 的**重复正文**，`git add -A` 会把它当新增文件提交；
  · 本项目铁律：**临时/备份禁放工作区**（否则 `add -A` 会把"移动"记成"删除+新增"）。

⇒ 备份搬去 `D:\\_tmp\\persona_bak199\\`（施工脚本也改指那里），
   仓库里只留**派生量**：尾块 sha、行尾计数、【】节名、英文词集合。
   这些都足以复核"尾块没动 / 英文台词没删 / 节结构没变"，且只有几十 KB。
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
BAK_IN = os.path.join(ROUND, '_evidence', '_persona_bak')
BAK_OUT = r'D:\_tmp\persona_bak199'
OUT = os.path.join(ROUND, '_evidence', 'baseline199.json')
TAIL = u'【本项目补充'.encode('utf-8')
SEC_RE = re.compile(u'^【[^】]+】')
ENG = re.compile(u'[A-Za-z][A-Za-z\'’\\.\\-]{2,}')


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def main():
    # 1) 把备份搬出去（只搬一次；已在外面就用外面的）
    if os.path.isdir(BAK_IN):
        if not os.path.isdir(BAK_OUT):
            os.makedirs(BAK_OUT)
        n = 0
        for fn in sorted(os.listdir(BAK_IN)):
            dst = os.path.join(BAK_OUT, fn)
            if not os.path.exists(dst):
                shutil.move(os.path.join(BAK_IN, fn), dst)
                n += 1
        print('[搬出] %d 份 → %s' % (n, BAK_OUT))
        try:
            os.rmdir(BAK_IN)
            print('[清理] 工作区内备份目录已删空并移除')
        except OSError as e:
            print('[注意] 目录非空，未删：%s' % e)
    else:
        print('[跳过] 工作区内没有备份目录（已在 %s）' % BAK_OUT)

    # 2) 生成派生基线（用搬出去的原始备份 + 当前磁盘）
    names = sorted(n for n in os.listdir(PER) if n.endswith('.txt'))
    base = {'schema': 1, 'note': '第199轮改动**之前**的派生量；check199 拿它当基准',
            'files': {}}
    for n in names:
        ob = rd(os.path.join(BAK_OUT, n + '.before199'))
        i = ob.rfind(TAIL)
        j = ob.rfind(b'\n', 0, i) + 1
        tail = ob[j:]
        head = ob[:j]
        ot = ob.decode('utf-8')
        base['files'][n] = {
            'tail_sha256': hashlib.sha256(tail).hexdigest(),
            'crlf': ob.count(b'\r\n'),
            'bare_lf_in_body': head.count(b'\n') - head.count(b'\r\n'),
            'sections': [ln.strip() for ln in ot.split(u'\r\n') if SEC_RE.match(ln.strip())],
            'eng': sorted(set(ENG.findall(ot))),
        }
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(base, ensure_ascii=False, indent=1))
    print('[写出] %s  %.1f KB  份数=%d' % (
        OUT, os.path.getsize(OUT) / 1024.0, len(names)))

    # 3) 自证：基线里的尾块 sha 与"当前磁盘"应不同（正文变了），但 76 份之间应相同
    ts = set(v['tail_sha256'] for v in base['files'].values())
    print('[自检] 基线内尾块 sha 去重数=%d（应为 1）' % len(ts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
