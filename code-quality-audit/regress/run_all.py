# -*- coding: utf-8 -*-
"""G2 回归基线：一条命令跑完全部回归套件，并对"归一化后的输出"做逐字节比对。

背景（见 `架构改造排期方案_H4-H5_2026-09-13.md` §3 G2）：
项目此前有 9 个手工冒烟脚本 + 每轮的 verify 脚本，但**没有一键可跑的回归入口**，
这是 H4 上帝类拆分最大的障碍——拆分的安全性判据是"行为完全不变"，
只能靠"改造前后跑同一套回归、输出逐字节一致"来证明。

本脚本做三件事：
  1. 按固定顺序、固定环境（offscreen / UTF-8 / 固定 cwd）跑全部套件；
  2. 把输出**归一化**（抹掉时间戳、内存地址、耗时、绝对路径、空行差异）后取 SHA-256；
  3. 与 `baseline.json` 比对：退出码 + PASS/FAIL 计数 + 归一化文本哈希，三项全同才算 IDENTICAL。

用法：
  python run_all.py                 # 跑全部并与基线比对（退出码 = 是否有套件 FAIL/DIFF）
  python run_all.py --update        # 重建基线（只在"改动是有意的"时候用）
  python run_all.py --only s1       # 只跑名字匹配的套件（子串匹配，可多次）
  python run_all.py --list          # 只列套件
  python run_all.py --verbose       # 把原始输出也打到控制台
  python run_all.py --show-diff s1  # 打印某套件的归一化 diff

产物：
  code-quality-audit/regress/baseline.json          基线（纳入 git）
  code-quality-audit/regress/_out/<suite>.txt       原始输出（不纳入 git）
  code-quality-audit/regress/_out/<suite>.diff.txt  出现 DIFF 时的差异
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(HERE, '_out')
BASELINE = os.path.join(HERE, 'baseline.json')
SEED_RUNNER = os.path.join(HERE, '_seed_runner.py')
# 固定随机种子：套件里存在 random.choice（如对话承接语），不钉死就必然漂移。
SEED = 20260913

# ---------------------------------------------------------------- 套件清单
# 顺序固定：先快后慢，先静态后运行时。
#   offscreen=True  → 注入 QT_QPA_PLATFORM=offscreen（涉及 QWidget/QPixmap 的套件必须）
#   needs         → 该套件依赖的前置文件，缺失即判 SKIP（而不是 FAIL）
#   env           → 可调用的"额外环境变量工厂"，返回 (dict, 待清理目录或 None)

def _make_hermetic_env():
    """给「会实例化整个 App」的套件一套每轮全新的隔离存储。

    为什么必须隔离（第十三轮发现的基线缺陷）：
      round8_anim 里会 `RalseiPet()`，于是 memory_system / data_store 真的去解析
      **真实**存储位置。第九轮起记忆住在 E 盘（`E:\\RalseiMemory`），而
      `data_store.vault_root()` 是**委托** `memory_store.find_device_dir()` 的 ——
      所以只强制 `RALSEI_MEMORY_DIR` 一个变量，记忆库与 7 类运行时产物会一起被隔离。

    不隔离的两个后果：
      1. 基线不封闭：套件输出随「E 盘是否在线」「E 盘上是否已有 memory.json」漂移。
         实测症状：E 盘接回后，"新位置无记忆，已从旧版 memory.json 继承"这行不再打印
         → round8_anim 与基线 DIFF（假警报，而真正的回归会被这堆噪声淹没）。
      2. 测试污染用户真实数据：套件跑一次就会往用户 E 盘写日志/成长数据。

    `tempfile.mkdtemp` 保证"新位置一定为空"→ "从旧版继承"必然发生 → 输出可复现；
    路径经 normalize() 归一成 <TMP>，所以每轮不同的随机目录名不会造成漂移。
    """
    base = tempfile.mkdtemp(prefix='ralsei_g2_iso_')
    return {'RALSEI_MEMORY_DIR': os.path.join(base, 'RalseiMemory')}, base


# 需要"隔离真实存储"的套件：凡是会 `RalseiPet()` / 触碰 memory · data_store
# 的套件都在此列。不隔离有三个后果：
#   1. 基线不封闭（输出随"E 盘在不在线""E 盘上有没有 memory.json"漂移）；
#   2. 往用户真实的 E 盘写运行时产物（日志/成长数据/记忆）；
#   3. **第十三轮实测的真问题**：`memory_store._is_writable_dir` 老实现每次调用
#      都真的 建/写/删 一个 `.write_probe`，一次启动被调十几次；17 个套件跑一轮，
#      同一路径 `E:\RalseiMemory\.write_probe` 单轮被删 50+ 次，累积撞上宿主沙箱的
#      删除配额守卫 → 每个套件进程在**开头就被掐掉**，输出只剩
#      `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]`，
#      全套件 `exit=1 PASS=0`（11 个假 DIFF 的真凶，见记忆_store 的快路径修复）。
# 强制 `RALSEI_MEMORY_DIR` 会让 `find_device_dir` 直接 return，连探针都不会跑。
HERMETIC_IDS = frozenset({
    'round5_smoke', 'round5_verify', 'round6_verify',
    's1_anim_miss', 's2_anim_json', 's3_alias_legacy',
    'round8_dialogue', 'round8_floor', 'round8_fling',
    'round9_focus', 'round13_build', 'round14_move',
})


SUITES = [
    {
        'id': 'round5_smoke',
        'script': os.path.join(ROOT, 'code-quality-audit', '第五轮', 'smoke_import_round5.py'),
        'offscreen': False,
        'desc': '第五轮：28 个 modules 全量导入冒烟 + 2 个源码不变量',
    },
    {
        'id': 'round5_verify',
        'script': os.path.join(ROOT, 'code-quality-audit', '第五轮', 'verify_round5_fixes.py'),
        'offscreen': True,
        'desc': '第五轮：16 项缺陷修复断言（对话/施法/成就/记忆）',
    },
    {
        'id': 'round6_verify',
        'script': os.path.join(ROOT, 'code-quality-audit', '第六轮', 'verify_round6_fixes.py'),
        'offscreen': True,
        'desc': '第六轮：39 项行为修复断言（对话/甩飞/抛物线/帧率/多屏）',
    },
    {
        'id': 'round7_launch',
        'script': os.path.join(ROOT, 'code-quality-audit', '第七轮', 'verify_round7_launch_import.py'),
        'offscreen': True,
        'desc': '第七轮：文档化启动（仅 src/ 在 path）不再 ModuleNotFoundError',
    },
    {
        'id': 's1_anim_miss',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s1_animation_miss.py'),
        'offscreen': True,
        'desc': 'H5-S1：动画名未命中自检 17 项 + 501 样本等价性',
    },
    {
        'id': 's2_anim_json',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s2_animations_json.py'),
        'offscreen': True,
        'desc': 'H5-S2：animations.json 与硬编码表深度等价 + 回落可用',
    },
    {
        'id': 's3_alias_legacy',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s3_alias_legacy.py'),
        'offscreen': True,
        'desc': 'H5-S3：alias_of / legacy 显式化后语义仍等价',
    },
    {
        'id': 'round8_dialogue',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_dialogue.py'),
        'offscreen': True,
        'desc': '第八轮：对话框 ▼ 闪烁不再撑高抖动 + 滚动位置不被弹回顶部',
    },
    {
        'id': 'round8_floor',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_floor.py'),
        'offscreen': True,
        'desc': '第八轮：楼层身份改用稳定标识（不再"看到窗口就摔"）+ 落地同步 current_floor',
    },
    {
        'id': 'round8_fling',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_fling.py'),
        'offscreen': True,
        'desc': '第八轮：斜抛（方向由松手速度定）+ 空中可二次抓住（按线速度缓冲减速）+ 卡动画自检',
    },
    {
        'id': 'round8_anim',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_anim.py'),
        'offscreen': True,
        'env': _make_hermetic_env,     # 会 RalseiPet()，必须隔离真实存储（见该函数注释）
        'desc': '第八轮：特殊动画只由 AI 触发（来源闸门）+ 播完不打断不移动 + 待机 3 分钟 + 鞠躬锚点',
    },
    {
        'id': 'round9_focus',
        'script': os.path.join(ROOT, 'code-quality-audit', '第九轮', 'verify_round9_focus.py'),
        'offscreen': True,
        'desc': '第九轮：对话注意力锚（换题只能由用户发起）+ 对话框 20s 无输入隐藏（鼠标压输入栏不隐藏）+ 自主开口不打断聊天',
    },
    {
        'id': 'round9_memory',
        'script': os.path.join(ROOT, 'code-quality-audit', '第九轮', 'verify_round9_memory.py'),
        'offscreen': True,
        'desc': '第九轮：拟人记忆（选择性记住/联想召回/遗忘与日摘要/复习强化）+ 存储落 E 盘与桌面兜底搬运',
    },
    {
        'id': 'round10_graph',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十轮', 'verify_round10_graph.py'),
        'offscreen': False,
        'desc': '第十轮：分层关联图（强/中/弱边 + hub 惩罚）+ 受控多跳检索（路径打分/PPR/每跳过滤/'
                '重排去重/预算/LLM 验证钩子）+ 反馈学习边权 + 离线巩固 + 噪声率·有用率·成功率',
    },
    {
        'id': 'round11_input',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十一轮', 'verify_round11_input.py'),
        'offscreen': False,
        'desc': '第十一轮：联想输入端治理 —— 抽词结构剪刀（碎片灭/真词留/免伤名单/三层择优/'
                '分词器注入）+ 建边拓扑可配（实测后默认仍是 clique，star/chain 因多跳闸门不过而弃用）'
                '+ 多跳闸门 + 残渣账本',
    },
    {
        'id': 'round12_store',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十二轮', 'verify_round12_store.py'),
        'offscreen': False,
        'desc': '第十二轮：jieba 分词接入（走 set_segmenter 注入，软依赖+静默回落）+ 存储统一'
                '（E 盘为最终存储、本地只作中转站：data_store 解析/收编模板/回迁五条安全约定）'
                '+ 7 类运行时产物全部路由到数据根 + 初始化环回归锁'
                '（间接环 lazy_log + 有鉴别力的导入顺序断言）；E 盘真机确认补丁',
    },
    {
        'id': 'round13_build',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十三轮', 'verify_round13_build.py'),
        'offscreen': True,
        'desc': '第十三轮：「建楼」遮挡判定 + 窗口层数 + 渲染层序（按 Windows 原生口径）'
                '—— 可见区域矩形相减（含独立网格 oracle 交叉验证）/ 完全盖住即不存在 / '
                '楼层名次最前最高 / 站立·下落·跳跃都只在可见区域 / '
                'DWM 可见边框·幽灵窗口·按进程排除自身 / SetWindowPos 把宠物插到所站楼板之上',
    },
    {
        'id': 'round14_move',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十四轮', 'verify_round14_move.py'),
        'offscreen': True,
        'desc': '第十四轮：「建楼」的上下动（跨楼层移动接线）—— 楼层判定真正接进产品路径'
                '（防"改了没人调用"复演：行为级证明 check_nearby_windows 走 '
                '_nearest_floor_jump）/ 向上跳落点必须在可见区域（被遮处要被吸附回来）/ '
                '向下跳只到相邻下一层（禁穿透）/ current_window 与 current_floor 单真源同步',
    },
]

# ---------------------------------------------------------------- 归一化
_TS = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?')
_ADDR = re.compile(r'0x[0-9a-fA-F]{6,}')
_DUR = re.compile(r'(?:耗时[:：]?\s*)?\d+(?:\.\d+)?\s*(?:秒|s\b|ms\b)')
# jieba 初始化时用 print 直接打的一行耗时（"Loading model cost 0.622 seconds."），
# 是 jieba 自己的 stdout、不受 setLogLevel 管，且每次都不一样 → 必须归一化。
_JIEBA_COST = re.compile(r'Loading model cost [0-9.]+ seconds\.?')
_TMPDIR = re.compile(r'[A-Za-z]:[\\/][^"\'\s]*?(?:AppData[\\/]Local[\\/]Temp|/tmp|\btmp\b)[^"\'\s]*')
_PID = re.compile(r'\bpid[=: ]?\d+\b', re.I)
_MEM = re.compile(r'内存[^\d]{0,4}\d+(?:\.\d+)?\s*(?:MB|KB|GB|字节)', re.I)
# Qt 离屏插件的环境噪声（与宠物行为无关，且**是否出现取决于本机字体/插件状态**，
# 曾导致 round8_dialogue 基线与现值“假 DIFF”：基线录到了 112 行字体告警，之后
# 同一份代码再跑就不打了）。这些行必须排除，否则基线不可复现。
_QT_NOISE = re.compile(
    r'^(?:QFontDatabase: Cannot find font directory.*'
    r'|Note that Qt no longer ships fonts\..*'
    r'|This plugin does not support .*'
    r'|QWindowsWindow::.*'
    r'|QObject::.*'
    r'|qt\.qpa\..*)$'
)


def normalize(text):
    """把"每次运行都不一样"的东西抹平，只留下语义内容。"""
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    # 绝对路径统一成 <ROOT>/...
    for variant in {ROOT, ROOT.replace('\\', '/'), ROOT.replace('/', '\\')}:
        t = t.replace(variant, '<ROOT>')
    t = _TMPDIR.sub('<TMP>', t)
    t = _JIEBA_COST.sub('Loading model cost <COST> seconds.', t)
    t = _TS.sub('<TS>', t)
    t = _ADDR.sub('<ADDR>', t)
    t = _PID.sub('<PID>', t)
    t = _MEM.sub('<MEM>', t)
    t = _DUR.sub('<DUR>', t)
    t = t.replace('\\', '/')
    lines = [ln.rstrip() for ln in t.split('\n')]
    out, blank = [], False
    for ln in lines:
        if _QT_NOISE.match(ln):      # Qt 插件噪声：不是被测行为的一部分
            continue
        if not ln:
            if blank:
                continue
            blank = True
        else:
            blank = False
        out.append(ln)
    return '\n'.join(out).strip() + '\n'


def count_results(text):
    """各套件的成功/失败标记风格不一：`[PASS]`（verify 系列）与 `[ OK ]`（smoke 系列）。"""
    n_pass = len(re.findall(r'\[PASS\]|\[\s*OK\s*\]', text))
    n_fail = len(re.findall(r'\[FAIL\]', text))
    return n_pass, n_fail


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- 执行
def run_suite(suite, verbose=False):
    script = suite['script']
    if not os.path.exists(script):
        return {'id': suite['id'], 'status': 'SKIP', 'reason': '脚本不存在', 'exit': None}

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONHASHSEED'] = '0'   # 钉死 set 的字符串迭代顺序，避免打印顺序漂移
    if suite.get('offscreen'):
        env['QT_QPA_PLATFORM'] = 'offscreen'
    env.pop('QT_QPA_PLATFORM_OVERRIDE', None)

    cleanup = None
    extra = suite.get('env') or (_make_hermetic_env if suite['id'] in HERMETIC_IDS else None)
    if callable(extra):
        extra_env, cleanup = extra()
        env.update(extra_env)

    try:
        proc = subprocess.run(
            [PYTHON or sys.executable, SEED_RUNNER, str(SEED), script],
            cwd=os.path.dirname(script),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)
    raw = proc.stdout.decode('utf-8', 'replace')
    norm = normalize(raw)
    n_pass, n_fail = count_results(raw)

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    with open(os.path.join(OUT_DIR, suite['id'] + '.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(raw)
    if verbose:
        print(raw)

    return {
        'id': suite['id'],
        'status': 'FAIL' if (proc.returncode != 0 or n_fail) else 'PASS',
        'exit': proc.returncode,
        'pass': n_pass,
        'fail': n_fail,
        'sha256': sha256(norm),
        'norm': norm,
    }


# ---------------------------------------------------------------- 解释器选择
# 套件必须用"装了 PyQt5 且能 import bs4"的解释器跑：本机 C:\Python311\python.exe
# 满足，而 ~/.workbuddy 下的托管 venv（Python 3.13）看不到 3.11 的用户
# site-packages —— 用它跑会得到 round5_smoke 假 FAIL（No module named 'bs4'）
# 以及一批与本项目无关的输出漂移。优先顺序：
#   环境变量 REGRESS_PYTHON > 已知系统解释器 > 当前解释器
_PY_CANDIDATES = (
    os.environ.get('REGRESS_PYTHON'),
    r'C:\Python311\python.exe',
)
PYTHON = None          # main() 里确定，run_suite 使用


def pick_python():
    tried = []
    for cand in _PY_CANDIDATES:
        if not cand or cand in tried:
            continue
        tried.append(cand)
        if not os.path.exists(cand):
            continue
        try:
            proc = subprocess.run([cand, '-c', 'import PyQt5, bs4'],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except Exception:
            continue
        if proc.returncode == 0:
            return cand, tried
    return sys.executable, tried


def load_baseline():
    if not os.path.exists(BASELINE):
        return None
    with open(BASELINE, encoding='utf-8') as fh:
        return json.load(fh)


def save_baseline(results, merge=True):
    """写基线。默认**合并**：只覆盖 results 里出现的套件，其余保留。

    修复（第十三轮）：原来是无条件整体重写，于是
        run_all.py --only round8_anim --update
    会把 baseline.json 里其余 15 个套件**静默删掉** —— 下次全量跑就全部变成
    "BASELINE"（无从比对），而输出看起来一切正常。基线是整个 H4/H5 改造的
    唯一安全性判据，不能有这种一键抹除的路径。
    """
    data = None
    if merge:
        data = load_baseline()
    if not data or 'suites' not in data:
        data = {
            'version': 1,
            'note': '归一化输出的 SHA-256 快照。改造前后必须逐字节一致；有意变更时用 --update 重建。',
            'suites': {},
        }
    for r in results:
        if r['status'] == 'SKIP':
            continue
        data['suites'][r['id']] = {
            'exit': r['exit'], 'pass': r['pass'], 'fail': r['fail'], 'sha256': r['sha256'],
        }
    data['suites'] = dict(sorted(data['suites'].items()))
    with open(BASELINE, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write('\n')


def write_diff(suite_id, old_norm, new_norm):
    """old_norm 为 None 时表示"基线只存了哈希、没存归一化文本"，此时打印全文。"""
    path = os.path.join(OUT_DIR, suite_id + '.diff.txt')
    diff = difflib.unified_diff(
        (old_norm or '').splitlines(True), (new_norm or '').splitlines(True),
        fromfile=suite_id + ' (baseline)', tofile=suite_id + ' (now)', n=3,
    )
    text = ''.join(diff)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text or '(归一化文本相同，仅计数/退出码不同)\n')
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true', help='重建基线')
    ap.add_argument('--only', action='append', default=[], help='只跑匹配的套件（子串）')
    ap.add_argument('--list', action='store_true', help='只列套件')
    ap.add_argument('--verbose', action='store_true', help='打印套件原始输出')
    ap.add_argument('--show-diff', metavar='ID', help='打印指定套件的归一化 diff')
    args = ap.parse_args()

    picked = [s for s in SUITES if not args.only or any(k in s['id'] for k in args.only)]

    if args.list:
        for s in SUITES:
            print('%-16s %-4s %s' % (s['id'], 'offscreen' if s.get('offscreen') else 'in-proc', s['desc']))
        return 0

    baseline = load_baseline()

    global PYTHON
    PYTHON, _tried = pick_python()

    if args.show_diff:
        with open(os.path.join(OUT_DIR, args.show_diff + '.txt'), encoding='utf-8') as fh:
            new_norm = normalize(fh.read())
        old = (baseline or {}).get('suites', {}).get(args.show_diff)
        if not old:
            print('基线里没有该套件')
            return 1
        print('\n'.join(difflib.unified_diff(
            [], new_norm.splitlines(True), fromfile='baseline(sha256=%s)' % old['sha256'][:12],
            tofile='now', n=3)))
        return 0

    print('=' * 72)
    print('回归基线（G2）  ROOT = %s' % ROOT)
    print('解释器 = %s' % PYTHON)
    print('=' * 72)

    results = [run_suite(s, verbose=args.verbose) for s in picked]

    print()
    print('%-16s %-6s %-6s %-6s %-8s %s' % ('suite', 'exit', 'PASS', 'FAIL', '比对', '说明'))
    print('-' * 72)
    verdicts, problems = {}, []
    for s, r in zip(picked, results):
        if r['status'] == 'SKIP':
            print('%-16s %-6s %-6s %-6s %-8s %s' % (r['id'], '-', '-', '-', 'SKIP', r.get('reason', '')))
            continue
        old = (baseline or {}).get('suites', {}).get(r['id'])
        if args.update or old is None:
            cmp_txt = 'BASELINE'
        elif old['sha256'] == r['sha256'] and old['exit'] == r['exit'] and old['pass'] == r['pass']:
            cmp_txt = 'IDENTICAL'
        else:
            cmp_txt = 'DIFF'
        verdicts[r['id']] = cmp_txt
        print('%-16s %-6s %-6s %-6s %-8s %s' % (
            r['id'], r['exit'], r['pass'], r['fail'], cmp_txt, s['desc']))
        if cmp_txt == 'DIFF':
            old_norm = None
            if old:
                old_raw = os.path.join(OUT_DIR, r['id'] + '.baseline.txt')
                if os.path.exists(old_raw):
                    with open(old_raw, encoding='utf-8') as fh:
                        old_norm = normalize(fh.read())
            path = write_diff(r['id'], old_norm, r['norm'])
            problems.append('%s: 输出与基线不一致（%s），%s' % (r['id'], '计数/退出码变化' if old_norm else '无基线文本', path))
        if r['status'] == 'FAIL':
            problems.append('%s: 套件自身 FAIL（exit=%s, fail=%d）' % (r['id'], r['exit'], r['fail']))

    if args.update:
        save_baseline(results)
        print()
        print('基线已更新（合并模式）：%s' % BASELINE)
        if args.only:
            print('  注意：本次只重建了 %d 个被 --only 选中的套件，其余套件的基线保持不动。' % len(picked))
        # 留一份原始文本供下次 DIFF 时做行级对比
        for r in results:
            if r['status'] == 'SKIP':
                continue
            with open(os.path.join(OUT_DIR, r['id'] + '.baseline.txt'), 'w',
                      encoding='utf-8', newline='\n') as fh:
                fh.write(r['norm'])

    tot_pass = sum(r.get('pass') or 0 for r in results)
    tot_fail = sum(r.get('fail') or 0 for r in results)
    print()
    print('合计：PASS=%d FAIL=%d  套件=%d' % (tot_pass, tot_fail, len(results)))
    if problems:
        print()
        print('【问题】')
        for p in problems:
            print('  - ' + p)
        return 1
    if not args.update and baseline is None:
        print()
        print('提示：本次基线为空，已按现状比对为 BASELINE。请用 --update 固化基线。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
