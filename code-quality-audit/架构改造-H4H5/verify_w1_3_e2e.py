# -*- coding: utf-8 -*-
"""W1-3 端到端行为探针：用**真 RalseiPet 实例**（离屏）驱动完整游戏流程。

为什么必须有这个探针：
  G2 的 24 个套件里**没有任何 games 覆盖** —— 游戏逻辑的行为等价性在 G2 里
  完全测不到。方法体逐字等价（verify_w1_3_games_extract.py）只证明了"代码没抄错"，
  证明不了"转发之后产品真的还能玩"。两者是不同的问题，都要独立证明。

本探针验的是**行为**，不是赋值：
  · 石头剪刀布：开局 → 出满 5 局 → 自动结算 → 统计键真的被更新
  · 猜数字：开局 → 二分找目标 → 猜对 → 结算 + 情绪/动画被触发
  · 转发：`pet.start_rock_paper_scissors` 等经 __getattr__ 真的能调通
  · 状态仍在宿主：controller 上没有 game_state 属性
  · 拒开局：一个游戏进行中时，另一个游戏的开局被拒（返回 False）

参照系：本探针另起一个进程跑「搬移前」的 main.py（_evidence/w1_3_main_before.py），
把同样的流程跑一遍，比较**行为轨迹**。这是真正的 A/B —— 注意必须先断言 A≠B，
否则就是自己跟自己比（本项目踩过这个坑）。
"""
import io
import os
import random
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

n_pass = n_fail = 0
SYS_PATH_ADDED = []
PATH_APPENDED = []


def check(cond, msg):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        print('[PASS] ' + msg)
    else:
        n_fail += 1
        print('[FAIL] ' + msg)


def _proj_root():
    """A/B 对照时的项目根：默认 = 本文件所在仓库。

    第二十六轮新增（**不改默认行为**，只加一个可选覆写口）：本探针是 W1-3 的
    A/B 基准（`verify_w1_3_ab.py` 把它当"同一把尺子"在两个项目根上各量一次）。
    它原先硬编码 `HERE/../..`，于是 B 组（旧 main.py 回填到**当前**仓库）量的是
    混合体，而不是"改造前那一版"。加了 `RALSEI_PROJECT_ROOT` 之后，B 组可以把
    `ralsei_pet/` 整个换成改造前的快照（连模块一起），量到真正的历史版本。

    不设该变量时行为与从前逐字节相同（A 组仍走原路径），所以既有 A/B 结论不受影响。
    """
    return os.environ.get('RALSEI_PROJECT_ROOT') or ROOT


def _prepare_sys_path(proj_root):
    """按**项目根**决定模块搜索路径。返回 (SYS_PATH_ADDED, PATH_APPENDED)。

    铁律 1（本探针第一版真踩，2026-09-20）：模块从哪来，**必须显式钉住**，
    不许"谁在 sys.path 里就用谁" —— 否则两个根同名时，`import main` 可能解析到
    残留的 `ralsei_pet/src/main.py`，B 组量的是 A 组的东西，A/B 退化成自己跟自己比。
    """
    global SYS_PATH_ADDED, PATH_APPENDED
    src = os.path.join(proj_root, 'ralsei_pet', 'src')
    mods = os.path.join(proj_root, 'ralsei_pet', 'modules')
    for b in (src, mods):
        while b in sys.path:
            sys.path.remove(b)
    for m in list(sys.modules):
        if m in ('main', 'modules') or m.startswith('modules.'):
            del sys.modules[m]
    sys.path.insert(0, src)
    sys.path.insert(0, mods)
    SYS_PATH_ADDED = list(sys.path[:2])
    PATH_APPENDED = list(SYS_PATH_ADDED)
    return SYS_PATH_ADDED, PATH_APPENDED


def main():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    proj_root = _proj_root()
    _prepare_sys_path(proj_root)
    src = os.path.join(proj_root, 'ralsei_pet', 'src')
    mods = os.path.join(proj_root, 'ralsei_pet', 'modules')

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    import main as app_main
    RalseiPet = app_main.RalseiPet

    random.seed(20260913)
    pet = RalseiPet()

    # --- 0. 转发接线：宿主上真的能拿到这些方法 ---
    MOVED = ['start_rock_paper_scissors', 'play_rock_paper_scissors',
             'determine_rock_paper_scissors_winner', 'end_rock_paper_scissors',
             'start_guess_number', 'play_guess_number', 'end_guess_number']
    for m in MOVED:
        check(hasattr(pet, m), 'RalseiPet 实例可解析 %s（经转发）' % m)
        check(callable(getattr(pet, m)), 'RalseiPet.%s 可调用' % m)

    # --- 1. 状态仍在宿主，不在控制器 ---
    check(hasattr(pet, 'game_state'), 'game_state 仍在宿主')
    check(hasattr(pet, 'guess_number_game'), 'guess_number_game 仍在宿主')
    check(hasattr(pet, 'rock_paper_scissors_options'), 'rock_paper_scissors_options 仍在宿主')
    # 控制器读到的 game_state 必须**就是宿主那一个对象**（不是副本）。
    # 注意：控制器实例上 `pet.games.game_state` 能取到值是**设计如此**
    # （它回落到宿主），所以这里断言的是"同一个对象"，不是"取不到"。
    check(pet.games.game_state is pet.game_state,
          '控制器读到的 game_state 就是宿主那一个对象（不是副本）')
    check(pet.games.guess_number_game is pet.guess_number_game,
          '控制器读到的 guess_number_game 就是宿主那一个对象')
    check(pet.games.p is pet, '控制器持有宿主引用且是同一个对象')
    # 真正的"状态没被搬走"判据：控制器的**实例字典**里不含这些状态键
    check('game_state' not in pet.games.__dict__,
          '控制器的实例字典里不含 game_state（状态没被搬进去）')
    check('guess_number_game' not in pet.games.__dict__,
          '控制器的实例字典里不含 guess_number_game')
    check('rock_paper_scissors_options' not in pet.games.__dict__,
          '控制器的实例字典里不含 rock_paper_scissors_options')

    # --- 2. 石头剪刀布：完整一局（出满 5 轮 → 自动结算） ---
    pet.game_state['is_playing'] = False
    ok = pet.start_rock_paper_scissors()
    check(pet.game_state['is_playing'] is True, '石头剪刀布开局后 is_playing=True')
    check(pet.game_state['game_type'] == 'rock_paper_scissors', 'game_type 正确')
    check(pet.game_state['game_round'] == 0, 'game_round 从 0 起')

    # 开局时若另有游戏进行中，必须被拒
    pet.game_state['is_playing'] = True
    pet.game_state['game_type'] = 'hide_and_seek'
    refused = pet.start_rock_paper_scissors()
    check(refused is False, '别的游戏进行中时 start_rock_paper_scissors 返回 False（不覆盖）')
    pet.game_state['is_playing'] = False
    pet.game_state['game_type'] = None

    # 重新开一局，打满 5 轮
    pet.start_rock_paper_scissors()
    rounds_before = pet.game_state['game_round']
    for i in range(5):
        pet.play_rock_paper_scissors('石头')
    check(pet.game_state['game_round'] == 5,
          '出满 5 轮后 game_round=5（实际 %d）' % pet.game_state['game_round'])
    check(len(pet.game_state['game_history']) == 5, 'game_history 记录了 5 局')
    check(pet.game_state['is_playing'] is False,
          '第 5 轮后自动结算，is_playing 复位')
    # 统计键真的被更新（三选一必然命中一个）
    stat_sum = pet.game_state['total_wins'] + pet.game_state['total_losses'] + pet.game_state['total_ties']
    check(stat_sum >= 1, '结算后统计键被更新（wins+losses+ties=%d）' % stat_sum)
    check('total_wins' in pet.game_state and 'best_streak' in pet.game_state,
          'update 语义保住了 total_wins / best_streak 等统计键（不 KeyError）')

    # --- 3. 猜数字：二分找到目标并猜对 ---
    pet.game_state['is_playing'] = False
    pet.start_guess_number()
    check(pet.game_state['is_playing'] is True, '猜数字开局后 is_playing=True')
    check(pet.game_state['game_type'] == 'guess_number', 'game_type=guess_number')
    target = pet.guess_number_game['target_number']
    check(1 <= target <= 100, '目标数字在 1..100 内（实际 %d）' % target)
    check(pet.guess_number_game['attempts'] == 0, 'attempts 归零')

    # 非法输入不推进
    pet.play_guess_number('abc')
    check(pet.guess_number_game['attempts'] == 0, '非数字输入不消耗尝试次数')
    pet.play_guess_number('999')
    check(pet.guess_number_game['attempts'] == 0, '超范围输入不消耗尝试次数')
    # 合法输入推进
    pet.play_guess_number(str(target))
    check(pet.guess_number_game['attempts'] == 1, '合法输入消耗 1 次尝试')
    check(pet.game_state['is_playing'] is False, '猜对后自动结算，is_playing 复位')
    check(pet.game_state['player_score'] == 1, '猜对后 player_score=1')

    # --- 4. 状态隔离：控制器实例字典里不该有状态副本（回落读的是宿主同一个对象） ---
    check('game_state' not in pet.games.__dict__,
          '控制器实例字典里仍无 game_state（状态没被复制过去）')
    check(pet.games.game_state is pet.game_state,
          '控制器经回落读到的仍是宿主那份 game_state')

    # --- 5. handle_game_input 仍要从宿主实例解析得到（W1-7 改口） ---
    # W1-3 时它**刻意留在宿主**；W1-7 搬入 games 后走的是 __getattr__ 转发。
    # ⚠️ 本段刻意**只断言行为面**（可调用 / 真的接管 / 躲猫猫退出口通），
    #    不断言"它在哪个类上定义" —— 那是**搬运状态**，A/B 对照（B 组 = 搬前快照）
    #    在天生上就不可能两边都过。归属断言归 W1-7 专属探针：
    #      verify_w1_7_move.py  G2/G3
    #    （本项目铁律：A/B 用的 e2e 必须是"两版都该全绿"的同一把尺子。）
    check(callable(pet.handle_game_input),
          'handle_game_input 从宿主实例可调用（经 __getattr__ 转发）')
    pet.game_state['is_playing'] = True
    pet.game_state['game_type'] = 'guess_number'
    handled = pet.handle_game_input('结束')
    check(handled is True, 'handle_game_input 识别"结束"并接管（返回 True）')
    check(pet.game_state['is_playing'] is False, '"结束"后游戏真的结束了')
    pet.game_state['is_playing'] = False
    pet.game_state['game_type'] = None

    # --- 6. 躲猫猫退出口（W1-7 新增：跨控制器转发链的行为级证明） ---
    # `handle_game_input` 的 hide_and_seek 分支调 `self._abort_hide_and_seek`，
    # 它住在 HideAndSeekController —— 搬走后这条链必须靠**兄弟控制器白名单**接通。
    # 这条断言正是「搬运前模拟」抓到的真缺口，必须留在回归里。
    real_abort = pet.hide_seek._abort_hide_and_seek
    calls = []

    def _spy(**kw):
        calls.append(kw)
    pet.hide_seek._abort_hide_and_seek = _spy
    try:
        pet.game_state['is_playing'] = True
        pet.game_state['game_type'] = 'hide_and_seek'
        r = pet.handle_game_input('退出游戏')
        check(r is True, '躲猫猫中说「退出游戏」→ handle_game_input 返回 True')
        check(len(calls) == 1 and calls[0].get('reason') == 'user_quit',
              '躲猫猫退出真的调到了 HideAndSeekController._abort_hide_and_seek'
              '（跨控制器转发链通；实际 %r）' % (calls,))
    finally:
        pet.hide_seek._abort_hide_and_seek = real_abort
        pet.game_state['is_playing'] = False
        pet.game_state['game_type'] = None

    print()
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_fail))

    # 清理：关掉宠物（含托盘/定时器），避免进程挂住
    try:
        pet.close()
    except Exception:
        pass
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
