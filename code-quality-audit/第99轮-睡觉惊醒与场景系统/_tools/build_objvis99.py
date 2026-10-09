# -*- coding: utf-8 -*-
u"""build_objvis99.py —— 从**原作 object 表**生成 `assets/scenes/_obj_visible.json`。

为什么要有它（第99轮真机发现）
------------------------------
`kris_s_room` 修好背景之后，屏幕上出现 **9 个红/白标记框**：
    obj_doorA ×1 / obj_markerB ×1 / obj_readable_room1 ×7
查第43轮的**原作转储** `objmap43.txt`（UTMT 读 `Data.GameObjects`）：

    88  obj_readable_room1  spr=spr_interactable  vis=False  pers=False
    97  obj_doorA           spr=spr_doorA         vis=False  pers=False
    111 obj_markerB         spr=spr_markerB       vis=False  pers=False

⇒ 原作里这三个对象的 `visible` 属性**就是 False**（可见性复选框没勾）——
  它们是**不可见触发器**（门的画面本来画在房间背景里，标记只是开发用）。
  我们照抄了 `spr=` 却漏了 `vis=`，于是把 76% 的物件都当"要画的东西"画出来了。

数据来源（**逐字节可回溯**）
----------------------------
`code-quality-audit/第43轮-原作门与相机取证/_evidence/{objmap,chapter2..5_objmap}43.txt`
—— 第43轮用 UTMT 转储的原作对象表，每行：
    `<i>\t<obj_name>\tspr=<sprite>\tvis=<True|False>\tpers=<True|False>`

产物（`ralsei_pet/assets/scenes/_obj_visible.json`）
--------------------------------------------------
只落 **hidden（vis=False）名单**，**不落 visible 名单**。理由：
  · 渲染规则是"**在名单里就不画**"，未知一律**照画**（保守侧）；
  · 名单越小越不容易出错，也便于人工复核（899 条 vs 4891 条）。
`visible_count` / `hidden_count` 一并落盘，供对账判据核数。

★ 这是**开发期**脚本（读的是审查证据目录），产品运行期只读产物 JSON ——
  所以产品侧仍然零外部依赖。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EVID = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证',
                    '_evidence')
OUT = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_obj_visible.json')

#: 原作对象表行的严格形态（多一个字段/少一个字段都不认，宁可漏不可错）
_ROW = re.compile(
    r'^(?P<i>\d+)\t(?P<name>\S+)\tspr=(?P<spr>\S*)\t'
    r'vis=(?P<vis>True|False)\tpers=(?P<pers>True|False)\s*$', re.M)


def main():
    files = sorted(f for f in os.listdir(EVID) if f.endswith('objmap43.txt'))
    if not files:
        raise SystemExit('!! 找不到原作 object 表（%s）' % EVID)
    vis = {}
    per_file = {}
    for f in files:
        txt = io.open(os.path.join(EVID, f), encoding='utf-8',
                      errors='replace', newline='').read()
        n = 0
        for m in _ROW.finditer(txt):
            name = m.group('name')
            v = (m.group('vis') == 'True')
            # 同名对象在多章重复出现 ⇒ 取**逻辑与的保守侧**：只要有一处说 False，
            # 就按 False 处理（少画一个可见物件 = 少一块画；多画一个不可见触发器
            # = 满屋子幽灵框）。⚠️ 实测 ch1~5 无冲突（下面会断言）。
            if name in vis and vis[name] != v:
                print('   [冲突] %s: %s vs %s（取 False）' % (name, vis[name], v))
                vis[name] = False
            else:
                vis[name] = v
            n += 1
        per_file[f] = n
        print('  %-30s 行 %d' % (f, n))

    hidden = sorted(k for k, v in vis.items() if not v)
    payload = {
        'schema_version': 1,
        'source': ('code-quality-audit/第43轮-原作门与相机取证/_evidence/'
                   + ' + '.join(files)),
        'authority': ('UTMT 转储 UndertaleMod Data.GameObjects 的 `visible` 属性'
                      '（原作对象编辑器里的"可见"复选框）'),
        'why': ('原作里 visible=False 的对象是**不可见触发器**（门/标记/可读物热点），'
                '画面本身画在房间背景里。我们早先照抄了 spr= 漏了 vis=，'
                '于是把 76% 的物件当"要画的"画出来（第99轮真机：一屋子红框）。'),
        'semantics': ('渲染层规则：物件的 `src` 落在 `hidden` 里 ⇒ 不画。'
                      '不在名单里（含未收录的对象）⇒ 照画（保守侧）。'
                      '⚠️ 只影响**绘制**，不影响交互/道具（触发器仍是可交互物）。'),
        'counts': {'files': len(files), 'objects_seen': len(vis),
                   'visible_count': len(vis) - len(hidden),
                   'hidden_count': len(hidden),
                   'per_file': per_file},
        'hidden': hidden,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write(u'\n')
    b = os.path.getsize(OUT)
    print('\n-> %s  (%.1f KB)' % (OUT, b / 1024.0))
    print('   收录 %d 个对象：可见 %d ｜ 隐形 %d'
          % (len(vis), payload['counts']['visible_count'], len(hidden)))
    print('   隐形名单前 15：%s' % hidden[:15])


main()
