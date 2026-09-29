# -*- coding: utf-8 -*-
u"""把拓扑边引用到的 GML 出处文件蒸馏进仓库（只拷被引用到的，21 个以内）。

理由（记忆铁律）：回归/证据**不得依赖外部盘或"用后即删"的临时区**（E 盘掉线即暴露）。
⇒ 把「要的事实」搬进仓库，让仓内读者能自证每条 explicit/cond 边的出处。
"""
from __future__ import print_function
import io, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, '..')
EV = os.path.join(AUD, '_evidence')
OUT = os.path.join(EV, 'gml_evidence65')

SRC = {
    'ut': ('ut_topology65.json', 'E:/Download/_extract61/_data/undertale/u65/gml65ut'),
    'uty': ('uty_topology65.json', 'E:/Download/_extract61/_data/undertale_yellow/uty65/gml65'),
    'ry': ('ry_topology65.json', 'E:/Download/_extract64/assets/redyellow65/gml65'),
}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    man = {'note': u'拓扑边引用到的 GML 出处文件（蒸馏进仓，避免依赖 E 盘）。'
                   u'obj_doorA_Alarm_2 是 SPECIAL 边的代码位置标签，非文件。',
           'works': {}}
    for k, (topo, src) in SRC.items():
        t = json.load(io.open(os.path.join(EV, topo), encoding='utf-8'))
        refs = sorted(set(e['evidence_file'] for e in t['edges']
                          if e.get('evidence_file')
                          and not e['evidence_file'].endswith('instance_creation_code')))
        od = os.path.join(OUT, k)
        if not os.path.isdir(od):
            os.makedirs(od)
        copied, label = [], []
        for r in refs:
            p = os.path.join(src, r)
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(od, r))
                copied.append(r)
            else:
                label.append(r)
        man['works'][k] = {'topology': topo, 'src_dir': src,
                           'referenced': len(refs), 'copied': len(copied),
                           'copied_files': copied, 'label_only': label}
        print('%s: referenced=%d copied=%d label_only=%s'
              % (k, len(refs), len(copied), label))
    io.open(os.path.join(OUT, '_manifest.json'), 'w', encoding='utf-8').write(
        json.dumps(man, ensure_ascii=False, indent=1))
    tot = sum(v['copied'] for v in man['works'].values())
    print('total copied = %d  -> %s' % (tot, OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
