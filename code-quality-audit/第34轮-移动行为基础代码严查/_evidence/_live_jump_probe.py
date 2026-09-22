# -*- coding: utf-8 -*-
"""第 34 轮 · 真机（离屏）验证：跳跃动画必须统一为 `jump_ball`，且坠落链路不受影响。

为什么用离屏：窗口是**透明非置顶 FramelessWindow**，甩飞/抛物线只能离屏断言
（§0 铁律）。这里不测甩飞，只测"动画选型"这条纯逻辑，故离屏足够可信。

判据纪律：
  · 尽量走**产品真函数**（`RalseiPet.start_jump` / `update_animation` / `handle_jump`）；
  · 对照实验：把 `has_ball` 置 True 与 False，两者结果应**相同**（证明恒假条件已去掉）；
  · 坠落链路对照：`start_falling` / `start_fall` 走 `fall` 家族，不得被改成 `jump_ball`。
"""
import io
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件在 code-quality-audit/<轮次>/_evidence/ → 仓库根要上溯 3 层
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
# main.py 在 ralsei_pet/src/（不是 ralsei_pet/）；modules/ 在 ralsei_pet/
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
os.chdir(os.path.join(ROOT, 'ralsei_pet'))          # 让 assets/ 相对路径可解析

from PyQt5.QtWidgets import QApplication           # noqa: E402

app = QApplication.instance() or QApplication([])

import main as M                                    # noqa: E402

print('=' * 72)
print('真机（离屏）验证：跳跃动画统一 jump_ball / 坠落链路不变')
print('=' * 72)


def try_build():
    """尝试构造 RalseiPet；失败则回退到"只读源码 + 驱动纯函数"的降级模式。"""
    try:
        pet = M.RalseiPet()
        return pet, 'constructed'
    except Exception as e:
        return None, 'unavailable: %s' % type(e).__name__


pet, mode = try_build()
print('构造 RalseiPet:', mode)

results = []


def check(cond, msg):
    results.append(bool(cond))
    print('[PASS] %s' % msg if cond else '[FAIL] %s' % msg)


if pet is not None:
    # ---------------- A. start_jump 的起跳帧 ----------------
    print('\n[A] start_jump 起跳准备帧')
    try:
        start_anims = []
        orig_change = pet.change_animation

        def spy_change(name, *a, **kw):
            start_anims.append(name)
            return orig_change(name, *a, **kw)

        pet.change_animation = spy_change
        import inspect
        n_params = len(inspect.signature(M.RalseiPet.start_jump).parameters)
        # start_jump 的签名兼容多种调用方式，这里用最简形式
        try:
            pet.start_jump()
        except TypeError:
            pet.start_jump(None, None, None)
        check(any(a == 'jump_ball' for a in start_anims),
              '[A1] start_jump 期间切到过 jump_ball（实测序列 %s）' % start_anims[:6])
        check('jump_ready' not in start_anims,
              '[A2] start_jump 期间**不再**切 jump_ready（实测 %s）' % start_anims[:6])
        pet.change_animation = orig_change
    except Exception as e:
        check(False, '[A] start_jump 驱动失败: %r' % e)

    # ---------------- B. has_ball 恒假条件已去掉 ----------------
    print('\n[B] has_ball 开关不再影响跳跃选型（对照组应一致）')
    try:
        seen = {}
        for ball in (False, True):
            pet.has_ball = ball
            seq = []
            oc = pet.change_animation

            def mk_spy(seq=seq, oc=oc):
                def spy(name, *a, **kw):
                    seq.append(name)
                    return oc(name, *a, **kw)
                return spy

            pet.change_animation = mk_spy()
            try:
                pet.start_jump()
            except TypeError:
                try:
                    pet.start_jump(None, None, None)
                except Exception:
                    pass
            pet.change_animation = oc
            seen[ball] = [x for x in seq if 'jump' in x]
        check(seen.get(False) == seen.get(True),
              '[B1] has_ball=False 与 True 的跳跃动画序列一致（%s vs %s）'
              % (seen.get(False), seen.get(True)))
        check(all('jump_ball' in (seen.get(b) or []) for b in (False, True)),
              '[B2] 两种 has_ball 取值下都出现 jump_ball')
    except Exception as e:
        check(False, '[B] has_ball 对照失败: %r' % e)

    # ---------------- C. 坠落链路不得被改成 jump_ball ----------------
    print('\n[C] 坠落链路（"摔下去"）仍用原来的素材')
    try:
        pet.has_ball = False
        for reason, want_family in ((None, ('fall', 'splat')),
                                    ('floor_removed', ('fall_mad', 'fall'))):
            # ⚠️ 探针保真（§5）：`start_falling` 开头有一串 early-return 守卫，
            # 上一段 [B] 的 start_jump 会把 is_jumping 置 True → 这里必须先把状态
            # 复位，否则 start_falling 直接 return、什么都不切，日志看着像"坠落链路坏了"。
            pet.is_jumping = False
            pet.is_gravity_falling = False
            pet.is_falling = False
            pet._is_being_dragged = False
            pet._spell_stage = None
            if hasattr(pet, 'game_state') and isinstance(pet.game_state, dict):
                pet.game_state['is_playing'] = False

            seq = []
            oc = pet.change_animation

            def mk_spy2(seq=seq, oc=oc):
                def spy(name, *a, **kw):
                    seq.append(name)
                    return oc(name, *a, **kw)
                return spy

            pet.change_animation = mk_spy2()
            try:
                pet.start_falling(reason=reason)
            finally:
                pet.change_animation = oc
            got = [x for x in seq if x]
            check(bool(got),
                  '[C0] start_falling(reason=%r) 确实产生了动画切换（实测 %s）'
                  % (reason, got[:4]))
            ok = any(isinstance(g, str) and any(g == w or g.startswith(w)
                                                for w in want_family)
                     for g in got)
            check(ok, '[C] start_falling(reason=%r) 用坠落家族 %s（实测 %s）'
                      % (reason, want_family, got[:4]))
            check(not any(g == 'jump_ball' for g in got
                          if isinstance(g, str)),
                  '[C] start_falling(reason=%r) 不得使用 jump_ball（实测 %s）'
                  % (reason, got[:4]))
        # 清理坠落状态，避免影响后续
        pet.is_gravity_falling = False
        pet.is_falling = False
    except Exception as e:
        check(False, '[C] 坠落链路驱动失败: %r' % e)

else:
    print('\n[降级] 无法构造 RalseiPet，改为源码级断言（仅覆盖"选型字面量"）：')
    src = open(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
               encoding='utf-8').read()
    check('self.change_animation("jump_ball", force=True)' in src,
          '[A1*] 源码中存在写死的 change_animation("jump_ball", force=True)')
    check('new_animation = "jump_ball"' in src,
          '[A2*] update_animation 的 jump_phase 推进指向 jump_ball')

print()
n_pass = sum(1 for r in results if r)
print('[SUMMARY] live jump anim: %d/%d PASS' % (n_pass, len(results)))
sys.exit(0 if n_pass == len(results) and results else 1)
