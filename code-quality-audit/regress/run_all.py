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
import subprocess
import sys

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
SUITES = [
    {
        'id': 'round5_smoke',
        'script': os.path.join(ROOT, 'code-quality-audit', '第五轮', 'smoke_import_round5.py'),
        'offscreen': False,
        'desc': '第五轮：25 个 modules 全量导入冒烟 + 2 个源码不变量',
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
]

# ---------------------------------------------------------------- 归一化
_TS = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?')
_ADDR = re.compile(r'0x[0-9a-fA-F]{6,}')
_DUR = re.compile(r'(?:耗时[:：]?\s*)?\d+(?:\.\d+)?\s*(?:秒|s\b|ms\b)')
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

    proc = subprocess.run(
        [PYTHON or sys.executable, SEED_RUNNER, str(SEED), script],
        cwd=os.path.dirname(script),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
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


def save_baseline(results):
    data = {
        'version': 1,
        'note': '归一化输出的 SHA-256 快照。改造前后必须逐字节一致；有意变更时用 --update 重建。',
        'suites': {
            r['id']: {'exit': r['exit'], 'pass': r['pass'], 'fail': r['fail'], 'sha256': r['sha256']}
            for r in results if r['status'] != 'SKIP'
        },
    }
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
        print('基线已重建：%s' % BASELINE)
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
