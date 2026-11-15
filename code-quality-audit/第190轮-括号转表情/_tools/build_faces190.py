# -*- coding: utf-8 -*-
u"""第190轮 · 把已确证"齐全"的原作素材落进 `ralsei_pet/assets/faces/`。

★ 为什么分两类落（别混为一谈）
------------------------------
用户口径：`齐全的就正常做，没有的不动就好`。而"齐全"在这个功能上**有两种含义**：

  · **expression（能驱动情绪）**：名字里带情绪词、且每个角色有多张
      ⇒ 只有黄魂 `spr_portrait_<角色>_<情绪>` 满足（8 个角色可对上项目 id，共 219 帧）
  · **portrait（只能当身份卡）**：每角色只有 1 张整图
      ⇒ OneShot 26 张（21 个 id）。它们是 424×276 的**彩绘插图带背景**，
        不是透明精灵，塞进气泡会糊住画面 ⇒ 只能"说话时显示一张头像卡"

⇒ manifest 里用 `kind` 区分，产品侧按需取，**不要**把两类当同一种东西用。

★★ 黄魂肖像必须先转（否则不能用）
--------------------------------
实测：`spr_portrait_*` 是 **100% 不透明、黑占 72% + 白线 28%** 的**黑底线稿**。
直接贴到浅色气泡上 = 一块黑砖。而 §3.4 已用代码证据确认**原作不着色**
（19/19 处 `draw_sprite_ext(..., c_white)`）⇒ 这就是它的"原貌"，不是解码坏了。

转换用**亮度→alpha**（单调、可验，不做阈值硬切）：
    黑(L=0) → 全透明；白(L=255) → 不透明；中间值 → 半透明
    颜色统一成黑（`ink` 变体，配浅色气泡）或白（`line` 变体，配深色气泡）
★ 比"if L<64 就透明"那种硬阈值好：**不会把抗锯齿边缘切掉**，也不会把
  近黑背景像素（如 `(42,6,24)`）漏进画面。

★★ 三种变体，**默认 original**
----------------------------
用户 2026-11-15 看过三行对照图后裁定：`ok，按原样来就好`
⇒ 默认 `original`：**不做任何颜色/透明度变换，直接用原作像素**
（黑底 + 白填充，100% 不透明 —— 游戏里就长这样，且**不依赖气泡底色**，
  换成深底浅底都不会"看不见"）。这也最符合项目口径「一切根据原作」。

另外两种保留为可选（`--mode ink` / `--mode line`），不默认生成：
  · `ink`  黑填充 + 透明底 —— 浅色气泡更清楚，但角色像剪影
  · `line` 白填充 + 透明底 —— 原作观感，但浅底上会看不见

用法
----
    python build_faces190.py --dry              # 只出计划表，不写盘
    python build_faces190.py                    # 默认 original
    python build_faces190.py --mode ink         # 需要时再生成
"""
import io
import json
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
OUT_ROOT = os.path.join(REPO, 'ralsei_pet', 'assets', 'faces')

#: original = 原样（默认）；ink/line = 见 docstring
MODE = 'original'

HY_MAN = u'D:\\_tmp190\\cropped\\hy\\_manifest.json'
HY_DIR = u'D:\\_tmp190\\cropped\\hy'
OS_DIR = u'E:\\项目文件夹\\xnbcli（oneshot)\\unpacked\\the_world_machine\\portraits'

#: UTY 肖像角色 → 项目角色 id。**只登记能对上的**；对不上的必须打印出来（不许静默丢）
HY_ROLE = {
    'ceroba': 'hy_ceroba_ketsukane',
    'chujin': 'hy_chujin_ketsukane',
    'starlo': 'hy_starlo',
    'mooch':  'hy_mooch',
    'moray':  'hy_moray',
    'ace':    'hy_ace',
    'axis':   'hy_axis',
    'ed':     'hy_ed',
}
#: 有肖像但项目里没有对应 id ⇒ 如实登记，不硬塞
HY_NO_ID = ['kanako', 'asgore', 'alphys', 'fchujin']

#: OneShot 文件名 → 项目角色 id（**20 条**；加 george1..6 归一的 os_george 共 21 个 id）
OS_MAP = {
    'alula': 'os_alula', 'calamus': 'os_calamus', 'cedric': 'os_cedric',
    'kelvin': 'os_kelvin', 'kip': 'os_kip', 'lamplighter': 'os_lamplighter',
    'ling': 'os_ling', 'magpie': 'os_magpie', 'maize': 'os_maize',
    'mason': 'os_mason', 'niko': 'os_niko', 'prophet': 'os_prophetbot',
    'prototype': 'os_prototype', 'rowbot': 'os_rowbot', 'rue': 'os_rue',
    'shepherd': 'os_shepherd', 'silver': 'os_silver', 'watcher': 'os_watcher',
    'author': 'os_the_author', 'world_machine': 'os_the_world_machine',
}
#: george1..6 全部归到 os_george（一个人多个立绘）
OS_GEORGE = 'os_george'


def arg(key, default=None):
    a = sys.argv[1:]
    if key not in a:
        return default
    i = a.index(key)
    return a[i + 1] if i + 1 < len(a) else default


def lum(r, g, b):
    # 整数近似（0.299/0.587/0.114），避免浮点在像素循环里太慢
    return (299 * r + 587 * g + 114 * b) // 1000


def to_ink(im, color=(0, 0, 0)):
    """亮度→alpha，颜色统一成 color。返回新的 RGBA 图。"""
    src = im.convert('RGBA')
    w, h = src.size
    out = Image.new('RGBA', (w, h))
    sp = src.load()
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a == 0:
                op[x, y] = (0, 0, 0, 0)
                continue
            L = (lum(r, g, b) * a) // 255      # 预乘：半透明源也算暗
            op[x, y] = (color[0], color[1], color[2], L)
    return out


def split_name(nm):
    """`spr_portrait_ceroba_happy` → ('ceroba', 'happy')；无法拆则 (None, None)。

    ★ fchujin 必须排在 chujin 前面判（否则会被 chujin 吃掉前半截）。
    """
    if not nm.startswith('spr_portrait_'):
        return None, None
    rest = nm[len('spr_portrait_'):]
    for role in sorted(list(HY_ROLE) + HY_NO_ID, key=len, reverse=True):
        if rest == role:
            return role, 'default'
        if rest.startswith(role + '_'):
            return role, rest[len(role) + 1:]
    return None, None


def main():
    global MODE
    dry = '--dry' in sys.argv[1:]
    if '--mode' in sys.argv:
        i = sys.argv.index('--mode')
        MODE = sys.argv[i + 1] if i + 1 < len(sys.argv) else 'original'
    print(u'[模式] %s（用户 2026-11-15 裁定「按原样来就好」⇒ 默认 original）' % MODE)
    if not os.path.isfile(HY_MAN):
        print(u'[停手] 缺黄魂裁切清单：%s' % HY_MAN)
        return 2
    hy = json.load(io.open(HY_MAN, encoding='utf-8'))
    print(u'[输入] 黄魂裁切 %d 条' % len(hy))

    # ── 分组 ──────────────────────────────────────────────────────
    plan = {}       # (id, emotion, frame) -> (src_path, kind)
    skipped = []
    unknown = []
    for m in hy:
        role, emo = split_name(m['name'])
        if role is None:
            unknown.append(m['name'])
            continue
        if role in HY_NO_ID:
            skipped.append((m['name'], u'项目无此 id'))
            continue
        cid = HY_ROLE[role]
        fr = m['frame']
        key = (cid, emo, fr)
        if key in plan:
            print(u'[撞键] %s 已存在，跳过 %s' % (key, m['file']))
            continue
        plan[key] = (os.path.join(HY_DIR, m['file']), 'expression')

    if unknown:
        print(u'[警告] %d 条名字拆不出角色（不许静默丢）：%s' % (len(unknown), unknown[:5]))

    # OneShot
    os_plan = []
    if os.path.isdir(OS_DIR):
        for fn in sorted(os.listdir(OS_DIR)):
            if not fn.lower().endswith('.png'):
                continue
            base = fn[:-4]
            if base.startswith('george'):
                os_plan.append((OS_GEORGE, base, os.path.join(OS_DIR, fn)))
            elif base in OS_MAP:
                # ★★ 第二格必须是**文件名 base**，不是字面量 'portrait'。
                #   第一版写成了 `(OS_MAP[base], 'portrait', ...)`（把 kind 塞进来了），
                #   结果 20 个角色目录里全叫 `portrait.png`、manifest 的 emotion
                #   也退化成 'portrait' ⇒ 人名信息丢失、无法反推源文件。
                #   `kind` 在 manifest 里是硬编码 'portrait'，不需要从这里传。
                os_plan.append((OS_MAP[base], base, os.path.join(OS_DIR, fn)))
            else:
                print(u'[警告] OneShot 有文件但无 id 映射：%s' % fn)
    else:
        print(u'[警告] OneShot 目录不存在：%s' % OS_DIR)

    # ── 汇总 ──────────────────────────────────────────────────────
    by_id = {}
    for (cid, emo, fr), (_p, kind) in plan.items():
        by_id.setdefault(cid, {'kind': kind, 'items': []})['items'].append((emo, fr))
    print(u'')
    print(u'%-24s %-11s %s' % ('角色 id', '类别', '情绪数/帧数'))
    for cid in sorted(by_id):
        emos = set(e for e, _f in by_id[cid]['items'])
        print(u'%-24s %-11s 情绪 %d / 帧 %d'
              % (cid, by_id[cid]['kind'], len(emos), len(by_id[cid]['items'])))
    print(u'')
    print(u'[OneShot] %d 个 id / %d 个文件' % (len(set(x[0] for x in os_plan)), len(os_plan)))
    if skipped:
        print(u'[跳过 %d 条，项目无对应 id] %s' % (len(skipped), sorted(set(s[0] for s in skipped))[:6]))

    if dry:
        print(u'[dry] 不写盘')
        return 0

    # ── 落盘 ──────────────────────────────────────────────────────
    if os.path.isdir(OUT_ROOT):
        # ★ 只清本脚本自己产出的东西（manifest.json + 各角色目录），别动别人
        for nm in os.listdir(OUT_ROOT):
            p = os.path.join(OUT_ROOT, nm)
            if nm == 'manifest.json' or os.path.isdir(p):
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    else:
        os.makedirs(OUT_ROOT)

    manifest = []
    n_expr = 0
    g2_checked = 0
    g2_bad = []

    for (cid, emo, fr), (src, kind) in sorted(plan.items()):
        d = os.path.join(OUT_ROOT, cid)
        os.makedirs(d, exist_ok=True)
        im = Image.open(src).convert('RGBA')
        # ★ 按模式出图。`original`（用户选定）**完全不改像素**，只换目录/文件名。
        if MODE == 'original':
            out = im
        elif MODE == 'ink':
            out = to_ink(im, (0, 0, 0))
        elif MODE == 'line':
            out = to_ink(im, (255, 255, 255))
        else:
            print(u'[停手] 未知 mode：%s' % MODE)
            return 3
        fn = ('%s.png' % emo) if fr == 0 else ('%s_f%d.png' % (emo, fr))
        out.save(os.path.join(d, fn))

        # ── 闸②：判据必须跟着 mode 走（**同口径**，这是上一版翻车的地方）──
        g2_checked += 1
        if MODE == 'original':
            # 原样模式：**逐像素完全相同**才叫"没改"。
            #   ★★ 必须**读回落盘文件**再比，不能拿 `out` 比 —— `out is im`，
            #   `im.tobytes() != out.tobytes()` 是**恒假**（同一对象比自己），
            #   那样这道闸等于不存在（记忆铁律：恒真/恒假判据比不写还危险）。
            #   读回来还能顺带抓 PNG 保存的位深/调色板损失。
            back = Image.open(os.path.join(d, fn)).convert('RGBA')
            if im.tobytes() != back.tobytes():
                g2_bad.append((fn, 'pixels-differ'))
            got = sum(1 for p in back.getdata() if p[3] > 0)
        else:
            # 转换模式：源亮度(预乘) ≥128 的像素数 == 产物 alpha≥128 的像素数
            #   ★★ 第一版这里写错过：`to_ink` 的 alpha 是连续值 L（0~255），
            #   闸却用 `a > 0` 当"不透明"统计 ⇒ 任何 L>0 的像素都算进去，
            #   于是必然比"L>=128 的个数"多，报出一堆假红。
            #   教训：**闸的判据必须和被测实现的定义同口径**，否则量的是两件事。
            want = sum(1 for p in im.getdata()
                       if (lum(p[0], p[1], p[2]) * p[3]) // 255 >= 128)
            got = sum(1 for p in out.getdata() if p[3] >= 128)
            if abs(want - got) > 2:
                g2_bad.append((fn, want, got))

        manifest.append({'id': cid, 'kind': kind, 'emotion': emo, 'frame': fr,
                         'variant': MODE,
                         'file': '%s/%s' % (cid, fn), 'wxh': list(out.size),
                         'opaque_pct': round(100.0 * got / (out.size[0] * out.size[1]), 1)})
        n_expr += 1

    for cid, base, src in os_plan:
        d = os.path.join(OUT_ROOT, cid)
        os.makedirs(d, exist_ok=True)
        im = Image.open(src).convert('RGBA')
        fn = '%s.png' % base
        im.save(os.path.join(d, fn))
        manifest.append({'id': cid, 'kind': 'portrait', 'emotion': base, 'frame': 0,
                         'file': '%s/%s' % (cid, fn), 'wxh': list(im.size),
                         'opaque_pct': 100.0})

    mf = os.path.join(OUT_ROOT, 'manifest.json')
    with io.open(mf, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=1))

    # ── 四道闸 ────────────────────────────────────────────────────
    print(u'')
    print(u'[闸①] 磁盘文件数 vs manifest 条目数')
    n_disk = 0
    for dp, _dn, fns in os.walk(OUT_ROOT):
        for f in fns:
            if f.lower().endswith('.png'):
                n_disk += 1
    ok1 = (n_disk == len(manifest))
    print(u'   %s  磁盘 %d / manifest %d' % (u'OK' if ok1 else u'报红', n_disk, len(manifest)))

    if MODE == 'original':
        print(u'[闸②] 原样保真（落盘文件读回后逐像素 == 源图）')
    else:
        print(u'[闸②] 亮度→alpha 守恒（源 L>=128 的像素数 == 产物不透明像素数）')
    ok2 = (not g2_bad)
    print(u'   %s  抽检 %d 张，不一致的 %d 张 %s'
          % (u'OK' if ok2 else u'报红', g2_checked, len(g2_bad), g2_bad[:3]))
    # ★ 负控制：证明这道闸**真能抓出"像素变了"**。只改内存副本，不碰落盘文件。
    if g2_checked:
        _pm = manifest[0]
        _pp = os.path.join(OUT_ROOT, _pm['file'].replace('/', os.sep))
        _a = Image.open(_pp).convert('RGBA')
        _b = _a.copy()
        _b.putpixel((0, 0), (1, 2, 3, 4))
        print(u'   [负控制] 人为改 1 像素 ⇒ %s'
              % (u'能抓出 OK' if _a.tobytes() != _b.tobytes()
                 else u'抓不出（判据失效，本闸作废）'))

    print(u'[闸③] 每个产物都能重新打开且尺寸与 manifest 一致')
    bad3 = []
    for m in manifest:
        p = os.path.join(OUT_ROOT, m['file'].replace('/', os.sep))
        try:
            im = Image.open(p)
            im.load()
            if list(im.size) != m['wxh']:
                bad3.append((m['file'], 'size', im.size, m['wxh']))
        except Exception as e:  # noqa: BLE001
            bad3.append((m['file'], type(e).__name__))
    ok3 = (not bad3)
    print(u'   %s  不一致 %d %s' % (u'OK' if ok3 else u'报红', len(bad3), bad3[:3]))

    print(u'[闸④] 角色覆盖：黄魂映射 8 个 id 必须都在，未映射的必须已打印')
    ids = set(m['id'] for m in manifest)
    want_ids = set(HY_ROLE.values())
    miss = want_ids - ids
    ok4 = (not miss)
    print(u'   %s  黄魂应到 %d 实到 %d；OneShot 应到 %d 实到 %d'
          % (u'OK' if ok4 else u'报红', len(want_ids), len(want_ids & ids),
             len(OS_MAP) + 1, len(set(x[0] for x in os_plan))))

    print(u'')
    print(u'[结果] expression %d 帧 / portrait %d 张 / 共 %d 个 id'
          % (n_expr, len(os_plan), len(ids)))

    # ── 闸⑤：命名语义（防 20 个角色全存成 portrait.png 那类静默退化）──
    print(u'[闸⑤] 命名语义：emotion 不得等于 kind；同 id 下文件名不得重复')
    bad5 = []
    for m in manifest:
        if m['emotion'] in ('portrait', 'expression'):
            bad5.append((m['file'], u'emotion 退化成 kind 字面量'))
    seen = {}
    for m in manifest:
        k = m['file'].lower()
        if k in seen:
            bad5.append((m['file'], u'与 %s 同名（会互相覆盖）' % seen[k]))
        seen[k] = m['file']
    ok5 = (not bad5)
    print(u'   %s  问题 %d %s' % (u'OK' if ok5 else u'报红', len(bad5), bad5[:4]))

    print(u'[输出] %s' % OUT_ROOT)
    if not (ok1 and ok2 and ok3 and ok4 and ok5):
        print(u'[报红] 有闸未过 ⇒ 不许当成功')
        return 6
    return 0


if __name__ == '__main__':
    sys.exit(main())
