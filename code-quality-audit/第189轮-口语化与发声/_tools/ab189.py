# -*- coding: utf-8 -*-
"""第189轮c · 口语化 A/B：**人设例句是不是真杠杆**（剂量实验）。

要回答的问题
------------
用户批注③「全员口语化，别说书面语」。第189轮量完 3696 轮发现：
  · 均句长 16.96 字、长句(≥40) 4.08%、含书面连词 9.50%、含口语词 60.63%
  · 最"书面"的角色几乎都能用人设解释（`rouxls` 文言、`hy_guardener` 明写"像机械播报、
    不用语气词"、`berdly` 爱用大词是本性格）⇒ **这些人不该改**
  · `npc_persona.SPEAK_RULES` 早就写了「像真人在聊天框里随手打字」「一句话就是一口气」
⇒ 结论是"规则不缺，是人设例句压过规则"。本轮**不动规则**，只验证这句话对不对。

实验设计（剂量-响应，不是"改 vs 不改"）
------------------------------------
对象 3 人（书面语率 14.6%~22.9%，且**没有**"文雅/机器/学者"这类设定约束）：
    hy_martlet 22.9% · hy_ace 18.8% · os_niko 14.6%
基线 = `_evidence/raw30` 里已有的 48 轮（第187轮那批，一个字节不动）。

臂：
  armB = 在「语言风格」段末尾追加 **2 条**中性中文正例
  armC = 追加 **6 条**同风格正例
⇒ 若 armC 的书面语率 < armB < 基线，就是剂量-响应，说明"例句是杠杆"且"越多越有效"；
   若两臂都比基线差，说明"加正例反而稀释人设"（第113轮g 的另一种形态）；
   若都没动，说明书面语不来自例句，得回头看规则或模型能力。

★ 正例的写法（第113轮g 的硬约束）：
  **只给中性正例，不写"禁令式描述"**。113g 实证：规则里描述「那种行为长什么样」
  ⇒ 同类违规率 1/10 → 10/10；给中性正例反而落到 1/10。
  所以这里一句"不要用然而/因此"都没有，全是"平常一句话长什么样"。

安全（夜里无人看守，最重要的一节）
--------------------------------
* 改人设前把**原始字节**读进内存 + 落备份盘；`try/finally` 里**按字节写回**，
  绝不用 `git checkout`（`autocrlf` 会把尾块也转成 CRLF，见 `tail_lf189.py`）；
* 每臂结束都断言 sha256 与原始一致，不一致就**大声报错并停**；
* `atexit` 再兜一层（进程被杀也要还原）；
* 输出目录独立：`_evidence/ab189/<arm>/{raw,tr}`，**不写 `raw30`**（那是不可再生的基线）。

用法
----
    python ab189.py --check                 # 只看环境（ollama / 3 人语料在不在），不训练
    python ab189.py --arms armB             # 只跑一臂
    python ab189.py                         # 两臂全跑（约 1.5~2 小时，CPU 推理）
"""
import atexit
import hashlib
import io
import json
import os
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
TOOLS113 = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools')
EVID = os.path.join(ROUND, '_evidence')
AB = os.path.join(EVID, 'ab189')
BAK = os.path.join(AB, '_persona_bak')
OLLAMA = r'C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe'
OLLAMA_LOG = os.path.join(AB, 'ollama_serve.log')

sys.path.insert(0, TOOLS113)
import common113 as C      # noqa: E402
import train30 as T        # noqa: E402

#: (角色 id, 插入锚点整行) —— 锚点必须在该文件里**唯一**
TARGETS = [
    ('hy_martlet', u'· 你经常道歉。你会为迟到道歉，为忘记事情道歉，为设置了一个太简单的谜题道歉。'
                   u'你会说“Sorry! I know I should have been paying more attention.”'),
    ('hy_ace',     u'· 你在严肃时会变得安静而真诚。当事情真的重要时，你会放下你的法语词，你会放下你的扑克术语。'
                   u'你会说“Starlo, this ain\'t right.”你会说“Ceroba, don\'t do this.”'
                   u'你会说“Clover, I\'m not gonna let you hurt them.”你的真诚比你的表演更有力量。'),
    ('os_niko',    u'· 你会用“嗯……”“那个……”“我觉得……”来开头，这些是你的思考方式，也是你说话时的自然停顿。'),
]

#: 正例池（中性、口语、无书面连词、无英文、不含"不要…"这类禁令）
EX = [
    u'· 平常接话的样子：“嗯，我想想啊。”“哦，对，就是那样。”',
    u'· 普通一句话就是一口气说完：“我也是刚知道，还没细看呢。”',
    u'· “等下，我好像记错了。”“你说得对，我搞混了。”',
    u'· “这个啊……我一时说不上来，反正不坏。”“行，那就这样吧。”',
    u'· “刚才有点乱，现在好多了。”“是有点怪，不过还能应付。”',
    u'· “你要是着急就先走，我随后跟上。”',
]

ARMS = {'armB': 2, 'armC': 6}

_ORIG = {}          # fid -> 原始字节（内存副本，用于 finally 还原）
_RESTORED = [False]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ensure_ollama():
    """本脚本自己的子进程（随脚本存活；脚本结束才回收）。"""
    try:
        urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=3).read()
        return True
    except Exception:  # noqa: BLE001
        pass
    if not os.path.isfile(OLLAMA):
        print('[失败] 找不到 ollama.exe')
        return False
    os.makedirs(AB, exist_ok=True)
    fh = open(OLLAMA_LOG, 'ab')
    subprocess_flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0
    import subprocess
    subprocess.Popen([OLLAMA, 'serve'], stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
                     creationflags=subprocess_flags, close_fds=True)
    for _ in range(60):
        time.sleep(2)
        try:
            urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=3).read()
            print('ollama 已就绪')
            return True
        except Exception:  # noqa: BLE001
            continue
    print('[失败] ollama 120s 内没起来')
    return False


def snapshot():
    """在任何改动**之前**把原始字节收进内存（两臂共用同一份"原版"）。"""
    for fid, _a in TARGETS:
        if fid not in _ORIG:
            _ORIG[fid] = open(os.path.join(PER, fid + '.txt'), 'rb').read()
    return {fid: sha(b)[:12] for fid, b in _ORIG.items()}


def apply_arm(n):
    """在锚点行之后插入 n 条正例（字节级，保留 CRLF）。

    ★ 每臂开始前必须把还原闸复位：`restore()` 是"一次性"的，
      若不复位，**第二臂结束后不会还原**，三份人设就带着 armC 的正例留在盘上
      （夜里无人看守 ⇒ 污染产品真源）。这是本脚本第一版的真 bug。
    """
    _RESTORED[0] = False
    for fid, anchor in TARGETS:
        path = os.path.join(PER, fid + '.txt')
        raw = open(path, 'rb').read()
        if fid not in _ORIG:
            _ORIG[fid] = raw
        txt = raw.decode('utf-8')
        eol = '\r\n' if '\r\n' in txt else '\n'
        if txt.count(anchor) != 1:
            raise SystemExit('[停手] %s 锚点命中 %d 次（应为 1）' % (fid, txt.count(anchor)))
        # ★★★ 必须是**整行**：只判 count==1 会漏掉"锚点是某行前缀"的情况，
        # 于是正例被插进句子中间、把原句切成两截（hy_ace 实测踩到）。
        _i = txt.find(anchor)
        _before = (_i == 0) or (txt[_i - 1] == '\n')
        _after = (_i + len(anchor) >= len(txt)) or (txt[_i + len(anchor)] == '\n')
        if not (_before and _after):
            raise SystemExit('[停手] %s 锚点不是整行（前=%r 后=%r）'
                             % (fid, txt[_i - 1:_i], txt[_i + len(anchor):_i + len(anchor) + 1]))
        add = ''.join(eol + e for e in EX[:n])
        new = txt.replace(anchor, anchor + add, 1)
        data = new.encode('utf-8')
        assert data.count(b'\r\n') == raw.count(b'\r\n') + n, '%s 行尾混了' % fid
        tmp = path + '.tmp'
        with io.open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, path)
        print('  [改人设] %-16s +%d 条正例  %d → %d B' % (fid, n, len(raw), len(data)))


def restore():
    if _RESTORED[0]:
        return
    _RESTORED[0] = True
    for fid, raw in _ORIG.items():
        path = os.path.join(PER, fid + '.txt')
        cur = open(path, 'rb').read()
        if cur == raw:
            continue
        os.makedirs(BAK, exist_ok=True)
        with io.open(os.path.join(BAK, fid + '.before.txt'), 'wb') as fh:
            fh.write(cur)
        tmp = path + '.tmp'
        with io.open(tmp, 'wb') as fh:
            fh.write(raw)
        os.replace(tmp, path)
        print('  [还原] %-16s %s' % (fid, sha(open(path, 'rb').read())[:12]))
    bad = [fid for fid, raw in _ORIG.items()
           if sha(open(os.path.join(PER, fid + '.txt'), 'rb').read()) != sha(raw)]
    if bad:
        print('!!! [严重] 还原后 sha 不一致：%r' % bad)
    elif _ORIG:
        print('  [自检] %d 份人设已逐字节还原' % len(_ORIG))


atexit.register(restore)


# ---------------------------------------------------------------- 评分
#: ★ 词表与口径**逐字照抄 `measure189.py`**（187/189 的基线表就是这套跑出来的）。
#:   自己另定一套 = 两边的百分比不可比，A/B 结论就是废的。这是"判据也是被测物"。
BOOKISH = [u'然而', u'因此', u'此外', u'总之', u'事实上', u'不仅', u'而且',
           u'尽管', u'即便', u'倘若', u'除此之外', u'与之相比', u'总而言之',
           u'由此可见', u'与此同时', u'换言之', u'基于', u'鉴于', u'进而',
           u'从而', u'无非', u'尚未', u'颇为', u'亦', u'乃', u'其所']
SPOKEN = [u'啊', u'呢', u'吧', u'嘛', u'呀', u'哦', u'啦', u'哎', u'诶',
          u'哈', u'唔', u'唉', u'嘿', u'咋', u'咱']


def split_sent(t):
    u"""按中英文句末标点切句（与 `measure189.split_sent` 同一口径）。"""
    import re as _re
    return [p.strip() for p in _re.split(u'[。！？!?]+', t) if p.strip()]


def score(rawdir, fid, markers):
    """从某臂的 raw jsonl 里取 turns_n==48 的记录，算口语化指标。

    ★ 字段是 `final`（模型直出）不是 `reply` —— 第一版写 `reply` 恒取空、
      于是 score() 恒返回 None，被 `--check` 的"没有 turns_n==48 的记录"挡下来了。
      **判据恒空＝恒真的反面**，这次是分母闸救的。
    """
    import re as _re
    p = os.path.join(rawdir, fid + '.jsonl')
    rec = None
    if os.path.isfile(p):
        for line in io.open(p, encoding='utf-8', errors='replace'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(r, dict) and r.get('turns_n') == 48:
                rec = r
    if not rec:
        return None
    replies = [t.get('final') or '' for t in (rec.get('turns') or [])]
    replies = [x for x in replies if x.strip()]
    if not replies:
        return None
    CJK = _re.compile(u'[\u4e00-\u9fff]')
    n = len(replies)
    book = sum(1 for x in replies if any(w in x for w in BOOKISH))
    spok = sum(1 for x in replies if any(w in x for w in SPOKEN))
    sents, n_cjk = [], 0
    for x in replies:
        sents += split_sent(x)
        n_cjk += len(CJK.findall(x))
    avg_len = n_cjk / len(sents) if sents else 0
    mk = sum(1 for x in replies if any(m in x for m in (markers or [])))
    return {'turns': n, 'bookish_turns': book, 'bookish_rate': round(book * 100.0 / n, 1),
            'spoken_rate': round(spok * 100.0 / n, 1), 'avg_sent': round(avg_len, 2),
            'marker_rate': round(mk * 100.0 / n, 1) if markers else None}



def markers_of(fid):
    p = os.path.join(C.TRAIN_DIR, 'cards', fid + '.json')
    card = C.load_json(p) or {}
    return card.get('voice_markers') or []


def main():
    argv = sys.argv[1:]
    check_only = '--check' in argv
    arms = list(ARMS)
    if '--arms' in argv:
        arms = [x.strip() for x in argv[argv.index('--arms') + 1].split(',') if x.strip()]

    print('=' * 70)
    print('口语化 A/B（剂量实验）  对象 %d 人 × 2 臂' % len(TARGETS))
    for fid, _a in TARGETS:
        print('  %-16s 现有语料 %s  markers=%r'
              % (fid, '在' if os.path.isfile(os.path.join(C.RAW30, fid + '.jsonl')) else '缺',
                 markers_of(fid)[:5]))
    if not all(os.path.isfile(os.path.join(C.RAW30, f + '.jsonl')) for f, _ in TARGETS):
        print('[停手] 有角色缺 48 轮基线语料，A/B 没有对照')
        return 2
    if check_only:
        for fid, _a in TARGETS:
            b = score(C.RAW30, fid, markers_of(fid))
            if b is None:
                print('[停手] %s 的 raw30 里没有 turns_n==48 的记录' % fid)
                return 2
            print('  基线 %-16s 书面%s%% / 口语%s%% / 句长%s / 口癖%s%%（%d 轮）'
                  % (fid, b['bookish_rate'], b['spoken_rate'], b['avg_sent'],
                     b['marker_rate'], b['turns']))
        print('（--check：只看环境，不训练）')
        return 0

    snap = snapshot()
    print('原始 sha（改动前）：%r' % snap)

    os.makedirs(AB, exist_ok=True)
    summary_path = os.path.join(AB, 'summary.json')
    summary = {}
    if os.path.isfile(summary_path):
        summary = C.load_json(summary_path) or {}

    for arm in arms:
        n = ARMS.get(arm)
        if not n:
            print('[跳过] 未知臂 %r' % arm)
            continue
        out = os.path.join(AB, arm)
        rawdir = os.path.join(out, 'raw')
        os.makedirs(rawdir, exist_ok=True)
        T.RAW30 = rawdir
        T.TR30 = os.path.join(out, 'tr')
        if not ensure_ollama():
            return 3
        print('\n---------- %s：+%d 条正例 ----------' % (arm, n))
        try:
            apply_arm(n)
            T.main(['--only', ','.join(f for f, _ in TARGETS),
                    '--turns', '48', '--sleep', '3',
                    '--pause-every', '3', '--pause-sec', '20',
                    '--log', os.path.join(out, 'train.log')])
        finally:
            restore()
        # 评分（基线 + 本臂）
        for fid, _a in TARGETS:
            m = markers_of(fid)
            base = score(C.RAW30, fid, m)
            got = score(rawdir, fid, m)
            summary.setdefault(fid, {})['baseline'] = base
            summary[fid][arm] = got
            print('  %-16s 基线 书面%s%% / 口语%s%% / 句长%s / 口癖%s%%'
                  % (fid, (base or {}).get('bookish_rate'), (base or {}).get('spoken_rate'),
                     (base or {}).get('avg_sent'), (base or {}).get('marker_rate')))
            print('  %-16s %s   书面%s%% / 口语%s%% / 句长%s / 口癖%s%%'
                  % ('', arm, (got or {}).get('bookish_rate'), (got or {}).get('spoken_rate'),
                     (got or {}).get('avg_sent'), (got or {}).get('marker_rate')))
        with io.open(summary_path, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=1)
            fh.write('\n')

    print('\n汇总 → %s' % summary_path)
    bad = [fid for fid in _ORIG
           if sha(open(os.path.join(PER, fid + '.txt'), 'rb').read()) != sha(_ORIG[fid])]
    print('收尾核验：%s' % ('三份人设与改动前逐字节一致' if not bad else '!!! 未还原 %r' % bad))
    return 0 if not bad else 4


if __name__ == '__main__':
    sys.exit(main())
