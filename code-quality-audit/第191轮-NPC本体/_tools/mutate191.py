# -*- coding: utf-8 -*-
u"""第191轮 · `check191` 的变异套件 —— 证明每一条判据**真的在守东西**。

## 为什么必须有它

`check191` 有 67 条判据。67 条全绿只说明"现在的代码满足它们"，**不说明**
它们能在代码被改坏时变红。第85/129轮的血泪：判据写歪了会**恒真**，
而那比不写更危险 —— 它给人"已经验过了"的错觉。

做法：逐条往产品代码里塞一个**定点变异**，跑一遍 `check191`，断言

  `0 < 红数 < 67`

- `红数 == 0` ⇒ 这条变异没被任何判据抓住（判据漏了，或变异的锚点没命中）
- `红数 == 67` ⇒ 套件**崩了**（不是"抓到了"，是 `[FAIL]` 一条都没打出来——
  第178轮 M3 / 第185轮 `once` 删逗号都是这个形态：rc=1 但红项为空）

## 三条纪律（都在下面的代码里，不是嘴上说的）

1. **整文件还原 + 核 sha1**：每条变异只动它声明的文件，跑完立刻按原字节写回，
   再逐个核 sha256。**不做"改回来靠记忆"**。
2. **双跑一致**：同一条变异跑两遍，红数与被点名的判据集合必须逐字相同
   （排除"偶然抖一下"）。
3. **锚点必须恰好命中 1 次**：`main.py` / `npc_body_render.py` 盘上是 **CRLF**，
   而锚点写的是 `\n` ⇒ 第185轮 M11~M15 五条**全部空转**、表现像"判据不灵"。
   这里先 `lf()` 归一，再断言 `count == 1`，最后按**原 EOL** 写回。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')
RENDER = os.path.join(REPO, 'ralsei_pet', 'modules', 'npc_body_render.py')
MANIFEST = os.path.join(REPO, 'ralsei_pet', 'assets', 'sprites', 'dr',
                        '_npc_frames.json')
SUSIE_D0 = os.path.join(REPO, 'ralsei_pet', 'assets', 'sprites', 'dr',
                        'susie', 'down_0.png')
SUSIE_ORPHAN = os.path.join(REPO, 'ralsei_pet', 'assets', 'sprites', 'dr',
                            'susie', 'zz_orphan_191.png')
CHECK = os.path.join(HERE, 'check191.py')

TOTAL = 69


# ---------------------------------------------------------------- 文件读写
def raw(p):
    with io.open(p, 'rb') as f:
        return f.read()


def lf(s):
    return s.replace('\r\n', '\n')


def put_raw(p, data):
    with io.open(p, 'wb') as f:
        f.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_text(path, old, new):
    """行内替换。★ 先 LF 归一（源文件是 CRLF），写回时按**原 EOL** 还原。"""
    data = raw(path)
    s = data.decode('utf-8')
    crlf = '\r\n' in s
    s_lf = lf(s)
    n = s_lf.count(old)
    if n != 1:
        raise AssertionError(u'锚点在 %s 里命中 %d 次（必须恰好 1 次）：%r'
                             % (os.path.basename(path), n, old[:60]))
    out = s_lf.replace(old, new)
    if crlf:
        out = out.replace('\n', '\r\n')
    put_raw(path, out.encode('utf-8'))


def patch_json(path, func):
    data = json.loads(raw(path).decode('utf-8'))
    func(data)
    put_raw(path, json.dumps(data, ensure_ascii=False, indent=2,
                             sort_keys=True).encode('utf-8'))


# ---------------------------------------------------------------- 变异表
# 每条：id / 想破坏什么 / 动作（闭包）/ 动到哪些文件
MUTS = []


def mut(mid, why, touches):
    def deco(fn):
        MUTS.append(dict(id=mid, why=why, touches=touches, fn=fn))
        return fn
    return deco


# ---- A 数据面（清单 ↔ 磁盘）----
@mut('M01', u'把 susie 的两个方向删掉（walk 类只剩 2 向）', [MANIFEST])
def _m01():
    def f(d):
        fr = d['characters']['susie']['frames']
        fr.pop('left', None)
        fr.pop('right', None)
    patch_json(MANIFEST, f)


@mut('M02', u'改一帧的 sha256（清单不再是磁盘的事实）', [MANIFEST])
def _m02():
    def f(d):
        row = d['characters']['susie']['frames']['down'][0]
        row['sha256'] = ('0' if row['sha256'][0] != '0' else '1') + row['sha256'][1:]
    patch_json(MANIFEST, f)


@mut('M03', u'改一帧的宽度 +1（尺寸不再等于真图）', [MANIFEST])
def _m03():
    def f(d):
        d['characters']['susie']['frames']['down'][0]['w'] += 1
    patch_json(MANIFEST, f)


@mut('M04', u'从磁盘删掉一帧（清单说有、盘上没有）', [SUSIE_D0])
def _m04():
    os.remove(SUSIE_D0)


@mut('M05', u'往目录里塞一张清单外的散图（复制了却没登记）', [SUSIE_ORPHAN])
def _m05():
    put_raw(SUSIE_ORPHAN, raw(SUSIE_D0))


@mut('M06', u'把 ralsei 从 no_art 里摘掉（他会被当成"该有立绘的人"）', [MANIFEST])
def _m06():
    def f(d):
        d['no_art'] = [x for x in d['no_art'] if x != 'ralsei']
    patch_json(MANIFEST, f)


@mut('M07', u'把 sign 从 no_art 摘掉（非人登记与"没立绘"口径打架）', [MANIFEST])
def _m07():
    def f(d):
        d['no_art'] = [x for x in d['no_art'] if x != 'sign']
    patch_json(MANIFEST, f)


@mut('M08', u'把 susie（4 向 × 4 帧）标成 stand —— 站着的人不该播走路', [MANIFEST])
def _m08():
    def f(d):
        d['characters']['susie']['kind'] = 'stand'
    patch_json(MANIFEST, f)


@mut('M09', u'给一个方向塞到 5 帧（超过 max_frames_per_dir=4）', [MANIFEST])
def _m09():
    def f(d):
        fr = d['characters']['susie']['frames']['down']
        fr.append(dict(fr[0]))
    patch_json(MANIFEST, f)


# ---- B/C 渲染层（行为面）----
@mut('M10', u'让左右方向互转（左右脸不一样，转了就是另一个人）', [RENDER])
def _m10():
    patch_text(RENDER,
               u"DIR_FALLBACK = ('down', 'up', 'left', 'right')",
               u"DIR_FALLBACK = ('down', 'right', 'left', 'up')")


@mut('M11', u'缩放缓存键改回 float 原值（浮点噪声 ⇒ 缓存永不命中）', [RENDER])
def _m11():
    patch_text(RENDER, u'        k = int(round(s * 1000))', u'        k = s')


@mut('M12', u'去掉"中心 → 脚底"的半高换算（脚底按中心算）', [RENDER])
def _m12():
    patch_text(RENDER,
               u"            if anchor == 'center':\n"
               u"                foot_y += win.height() / 2.0",
               u"            if anchor == 'center':\n"
               u"                pass")


@mut('M13', u'窗口按中心摆而不是按脚底摆（遮挡锚点错位半高）', [RENDER])
def _m13():
    patch_text(RENDER,
               u'        self.move(int(round(foot_x - w / 2.0)), '
               u'int(round(foot_y - h)))',
               u'        self.move(int(round(foot_x - w / 2.0)), '
               u'int(round(foot_y - h / 2.0)))')


@mut('M14', u'给本体窗口加 WindowStaysOnTopHint（遮挡彻底失效）', [RENDER])
def _m14():
    patch_text(RENDER,
               u'        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint\n'
               u'                            | Qt.WindowDoesNotAcceptFocus',
               u'        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint\n'
               u'                            | Qt.WindowStaysOnTopHint\n'
               u'                            | Qt.WindowDoesNotAcceptFocus')


@mut('M15', u'站着的人也播走路帧（抽腿）', [RENDER])
def _m15():
    patch_text(RENDER, u'            if moving and n > 1:',
               u'            if n > 1:')


@mut('M16', u'去掉同屏上限（14 个人就 14 个 SetWindowPos）', [RENDER])
def _m16():
    patch_text(RENDER,
               u'            if len(want) >= MAX_BODIES:\n                break',
               u'            if False:\n                break')


@mut('M17', u'`visible_windows` 反向排序（成组置顶的前后关系会反）', [RENDER])
def _m17():
    patch_text(RENDER, u'        out.sort(key=lambda t: (t[2], t[0]))',
               u'        out.sort(key=lambda t: (t[2], t[0]), reverse=True)')


@mut('M18', u'没立绘的人 `dir_of` 也返回 down（调用方会画空窗）', [RENDER])
def _m18():
    patch_text(RENDER, u'        if not have:\n            return None',
               u"        if not have:\n            return 'down'")


@mut('M19', u'去掉坏倍率保护（0 / 负 / "x" / None 直接进 float()）', [RENDER])
def _m19():
    patch_text(RENDER,
               u'        try:\n'
               u'            s = float(scale)\n'
               u'        except (TypeError, ValueError):\n'
               u'            s = 1.0',
               u'        s = float(scale)')


@mut('M20', u'`hide_all` 不清可见集合（下一帧还以为人都在）', [RENDER])
def _m20():
    patch_text(RENDER,
               u'    def hide_all(self):\n'
               u'        for win in self._wins.values():\n'
               u'            try:\n'
               u'                win.hide()\n'
               u'            except Exception:\n'
               u'                pass\n'
               u'        self._visible = set()',
               u'    def hide_all(self):\n'
               u'        for win in self._wins.values():\n'
               u'            try:\n'
               u'                win.hide()\n'
               u'            except Exception:\n'
               u'                pass')


@mut('M21', u'窗口不复用（每次都新建 ⇒ 句柄泄漏）', [RENDER])
def _m21():
    patch_text(RENDER,
               u'            win = self._wins.get(nid)\n'
               u'            if win is None:\n'
               u'                win = BodyWindow()\n'
               u'                self._wins[nid] = win',
               u'            win = BodyWindow()\n'
               u'            self._wins[nid] = win')


@mut('M22', u'渲染层反向依赖宿主（成环）', [RENDER])
def _m22():
    # ★ 故意放进 `if False:` —— 只要 AST 看得见这条 import 就够了，
    #   真去 import `main` 会把套件拖垮（那就成了"崩了"而不是"抓到了"）。
    patch_text(RENDER,
               u'MANIFEST_NAME = \'_npc_frames.json\'',
               u'MANIFEST_NAME = \'_npc_frames.json\'\n'
               u'\n'
               u'if False:  # 变异探针：AST 能看见，运行期不执行\n'
               u'    from modules import main  # noqa: F401')


# ---- D 接线（宿主侧）----
@mut('M23', u'本体推进挪到场景层更新**之前**（读到上一帧的相机）', [MAIN])
def _m23():
    # ★ 两步而不是一步：两个调用之间夹着 8 行注释，整块当锚点
    #   会因为注释里一个字不对而空转（第185轮 M11~M15 同款）。
    #   先把原来那句换成占位符（保证全文只剩 0 个 tick 调用），
    #   再把 tick 插到 update **之前** ⇒ 全文恰好 1 个调用，且顺序反了。
    patch_text(MAIN, u'        self._npc_body_tick()',
               u'        pass  # MUT_TICK')
    patch_text(MAIN, u'        self._update_scene_layer()',
               u'        self._npc_body_tick()\n        self._update_scene_layer()')


@mut('M24', u'倍率优先取 `_cached_scale_factor`（含 pet_scale ⇒ 整条街跟着变大）',
     [MAIN])
def _m24():
    patch_text(MAIN,
               u'        cam = self.__dict__.get(\'_scene_camera\')\n'
               u'        try:\n'
               u'            sc = float(getattr(cam, \'scale\', 0.0)) if cam is not None else 0.0\n'
               u'        except (TypeError, ValueError):\n'
               u'            sc = 0.0\n'
               u'        if sc > 0:\n'
               u'            return sc\n'
               u'        try:\n'
               u'            v = float(self.__dict__.get(\'_cached_scale_factor\', 0.0))\n'
               u'        except (TypeError, ValueError):\n'
               u'            v = 0.0\n'
               u'        return v if v > 0 else 2.0',
               u'        try:\n'
               u'            v = float(self.__dict__.get(\'_cached_scale_factor\', 0.0))\n'
               u'        except (TypeError, ValueError):\n'
               u'            v = 0.0\n'
               u'        if v > 0:\n'
               u'            return v\n'
               u'        cam = self.__dict__.get(\'_scene_camera\')\n'
               u'        try:\n'
               u'            sc = float(getattr(cam, \'scale\', 0.0)) if cam is not None else 0.0\n'
               u'        except (TypeError, ValueError):\n'
               u'            sc = 0.0\n'
               u'        return sc if sc > 0 else 2.0')


@mut('M25', u'去掉置顶态下的早退（"插到某人之后"在置顶带里无意义）', [MAIN])
def _m25():
    patch_text(MAIN,
               u"        if getattr(self, '_scene_topmost_on', False):\n"
               u"            return False\n"
               u"        fm = getattr(self, 'floor_manager', None)",
               u"        fm = getattr(self, 'floor_manager', None)")


@mut('M26', u'z 序回调不真去插（只返回 True，谁也不动）', [MAIN])
def _m26():
    patch_text(MAIN,
               u'        return FloorManager.set_window_behind(hwnd, insert)',
               u'        return True')


@mut('M27', u'`_set_scene_topmost` 用回老排序（新函数白写）', [MAIN])
def _m27():
    patch_text(MAIN,
               u'        targets = self._scene_topmost_targets_ordered()',
               u'        targets = self._scene_topmost_targets()')


@mut('M28', u'去掉"人"的脚底 Y 排序（NPC 追加在桌宠后面 ⇒ 前后反了）', [MAIN])
def _m28():
    patch_text(MAIN, u'        people.sort(key=lambda t: (t[0], t[1]))\n', u'')


@mut('M29', u'宿主按 id 白名单过滤（把 ralsei 特殊对待）', [MAIN])
def _m29():
    patch_text(MAIN,
               u'            for nid, b in bodies.items():\n'
               u'                try:\n'
               u"                    items.append({'id': nid, 'x': float(b.x), 'y': float(b.y),",
               u'            for nid, b in bodies.items():\n'
               u"                if nid == 'ralsei':\n"
               u'                    continue\n'
               u'                try:\n'
               u"                    items.append({'id': nid, 'x': float(b.x), 'y': float(b.y),")


@mut('M30', u'老排序函数也去读 NPC 窗口（负控制失效：两个函数变成同一份）', [MAIN])
def _m30():
    patch_text(MAIN,
               u"        for _name in ('scene_canvas', 'self', 'soul', 'ghost'):",
               u"        self.__dict__.get('_npc_body_layer') and "
               u"self.__dict__.get('_npc_body_layer').visible_windows()\n"
               u"        for _name in ('scene_canvas', 'self', 'soul', 'ghost'):")


@mut('M31', u'`destroy_all` 不清窗口池（析构后参考还在）', [RENDER])
def _m31():
    patch_text(RENDER,
               u'    def destroy_all(self):\n'
               u'        for win in self._wins.values():\n'
               u'            try:\n'
               u'                win.hide()\n'
               u'                win.deleteLater()\n'
               u'            except Exception:\n'
               u'                pass\n'
               u'        self._wins.clear()',
               u'    def destroy_all(self):\n'
               u'        for win in self._wins.values():\n'
               u'            try:\n'
               u'                win.hide()\n'
               u'                win.deleteLater()\n'
               u'            except Exception:\n'
               u'                pass')


# ---------------------------------------------------------------- 跑
def run_check():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONHASHSEED'] = '0'
    env['QT_QPA_PLATFORM'] = 'offscreen'
    p = subprocess.run([sys.executable, CHECK], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    fails = re.findall(u'^\\[FAIL\\] (.+?)(?:    |$)', out, re.M)
    fails = [f.strip() for f in fails]
    n_pass = len(re.findall(u'^\\[PASS\\] ', out, re.M))
    return p.returncode, n_pass, fails, out


def main():
    print(u'=== 基线：不变异时应当全绿 ===')
    rc, np_, fails, out = run_check()
    if rc != 0 or fails:
        print(u'基线不绿（rc=%s / PASS=%d / FAIL=%r）—— 先修 check191 再谈变异'
              % (rc, np_, fails))
        return 2
    print(u'基线 %d PASS / 0 FAIL（总数 %d）' % (np_, TOTAL))
    if np_ != TOTAL:
        print(u'★ 条数与声明的 %d 不符（实际 %d）—— 先对齐 EXPECT' % (TOTAL, np_))
        return 2

    bad = []
    for m in MUTS:
        orig = {}
        for p in m['touches']:
            orig[p] = raw(p) if os.path.exists(p) else None
        try:
            m['fn']()
            r1, n1, f1, o1 = run_check()
            r2, n2, f2, o2 = run_check()
        finally:
            for p, data in orig.items():
                if data is None:
                    if os.path.exists(p):
                        os.remove(p)
                else:
                    put_raw(p, data)
        # ---- 还原核验（逐文件 sha1）----
        rest_ok = True
        for p, data in orig.items():
            now = raw(p) if os.path.exists(p) else None
            if (data is None) != (now is None) or (data is not None and sha(data) != sha(now)):
                rest_ok = False
        n_red = len(f1)
        weird = u''
        if not rest_ok:
            weird = u'★ 还原失败'
        elif r1 != 0 and n1 == 0:
            weird = u'★ 套件崩了（rc=%s 且一条 [PASS] 都没有）' % r1
        elif n_red == 0:
            weird = u'★ 一条都没抓到（判据漏了，或锚点空转）'
        elif n_red >= TOTAL:
            weird = u'★ 红满 %d 条 = 崩了而不是抓到' % n_red
        elif f1 != f2 or n1 != n2:
            weird = u'★ 双跑不一致（%r vs %r）' % (f1[:2], f2[:2])
        ok = not weird
        print(u'%s %s 红 %2d/%d  %s'
              % (u'[ OK ]' if ok else u'[ !! ]', m['id'], n_red, TOTAL, m['why']))
        if n_red and n_red < TOTAL:
            print(u'        抓到：%s' % u' / '.join(f.split(u' ')[0] for f in f1[:6]))
        if weird:
            print(u'        %s' % weird)
            bad.append(m['id'])

    print()
    print(u'变异 %d 条：%d 全抓 / %d 有问题'
          % (len(MUTS), len(MUTS) - len(bad), len(bad)))
    if bad:
        print(u'有问题：%r' % (bad,))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
