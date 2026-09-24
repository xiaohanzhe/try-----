# -*- coding: utf-8 -*-
"""量化：把「实例能映射到的 obj sprite」搬进仓库需要多少张 / 多大。

为什么要搬（不能直接引用 E:\\Download\\_tmp）：
  记忆铁律 —— 「仓库内产物留项目目录」+「回归套件不许依赖用后即删的临时区」。
  E:\\Download\\_tmp\\dr_out 是第 37 轮的**临时解包区**，随时会被清；
  一旦清掉，objs 的 sprite 全部失效 ⇒ 渲染层退化为一片品红描边框。
  ⇒ 用到的图必须进仓库。

判据：
  P1 参与映射的 obj 名数、去重后的 sprite 名数
  P2 五章 sprite 文件总张数（用于复制的实际文件集）
  P3 总字节数（决定是否可接受）
  P4 只复制**真正被实例引用**的 sprite（不是全量 7 万张）
  + 输出一份可直接消费的「复制清单」 JSON
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
OUT = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_evidence')
DR_OUT = r'E:\Download\_tmp\dr_out'
CHDIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows',
         'ch3': 'chapter3_windows', 'ch4': 'chapter4_windows',
         'ch5': 'chapter5_windows'}
INST = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
        'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def parse_objmap(path):
    out = {}
    with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            name = parts[1].strip()
            vm = re.search(r'spr=([^\t]*)', line)
            if name:
                out[name] = vm.group(1).strip() if vm and vm.group(1).strip() else None
    return out


def main():
    objmap = parse_objmap(os.path.join(E43, 'objmap43.txt'))

    # 实例里用到的 obj → 计数；只保留有 spr 的
    used = {}
    for ch in INST:
        d = load(os.path.join(E42, INST[ch]))
        for rec in (d.get('rooms') or []):
            for it in (rec.get('insts') or []):
                nm = it.get('obj')
                if nm:
                    used[nm] = used.get(nm, 0) + 1

    drawable_obj = sorted(n for n in used if objmap.get(n))
    spr_names = sorted(set(objmap[n] for n in drawable_obj))
    print('实例里出现的 obj 名 = %d' % len(used))
    print('其中有 spr 的 obj 名 = %d' % len(drawable_obj))
    print('去重后 sprite 名 = %d' % len(spr_names))
    print('sprite 名列表 = %s' % (spr_names if len(spr_names) <= 60 else
                                  (spr_names[:60] + ['...'])))

    # 逐章找文件（一个 sprite 可能有多帧 _0/_1/...；先按 _0 优先）
    plan = {}          # spr_name -> {ch: [files]}
    total_files = 0
    total_bytes = 0
    per_ch_files = {}
    for ch in INST:
        sd = os.path.join(DR_OUT, CHDIR[ch], 'Sprites')
        if not os.path.isdir(sd):
            print('  %s: Sprites 目录缺失' % ch)
            continue
        files = os.listdir(sd)
        # 建索引：spr_xxx_0.png → 找同名前缀
        idx = {}
        for f in files:
            if not f.lower().endswith('.png'):
                continue
            base = f[:-4]
            # 去掉尾部 _<数字>
            m = re.match(r'^(.*)_(\d+)$', base)
            key = m.group(1) if m else base
            idx.setdefault(key, []).append(f)
        got = 0
        for spr in spr_names:
            fl = sorted(idx.get(spr, []))
            if fl:
                plan.setdefault(spr, {})[ch] = fl
                got += 1
                per_ch_files[ch] = per_ch_files.get(ch, 0) + len(fl)
                total_files += len(fl)
                for f in fl:
                    try:
                        total_bytes += os.path.getsize(os.path.join(sd, f))
                    except OSError:
                        pass
        print('  %s: sprite 命中 %d / %d，文件 %d' %
              (ch, got, len(spr_names), per_ch_files.get(ch, 0)))

    print('')
    print('总文件数 = %d' % total_files)
    print('总字节   = %d (%.2f MB)' % (total_bytes, total_bytes / 1048576.0))

    # 未命中的 sprite（有 spr 名但五章都没文件）
    miss = [s for s in spr_names if s not in plan]
    print('五章都没有文件的 sprite = %d %s' % (len(miss), miss[:20]))

    payload = {
        'schema_version': 1,
        'note': '实例普查里可绘制 obj 的 sprite 复制清单（第44轮 objects 补全用）',
        'source_root': DR_OUT,
        'spr_names': spr_names,
        'plan': plan,
        'total_files': total_files,
        'total_bytes': total_bytes,
    }
    op = os.path.join(OUT, 'obj_sprite_copy_plan44.json')
    with io.open(op, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print('')
    print('清单已写: %s' % os.path.relpath(op, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
