# -*- coding: utf-8 -*-
"""
第115轮 · 把新口径铺到 76 份 NPC 人设（默认 **dry-run**，加 `--apply` 才写盘）

用户口径是**复数**：「**他们**知道他们是游戏，但并不对此感到悲观」——
Ralsei 已落（`assets/ralsei_persona.md` 的「我是什么」节），76 份 NPC 还没铺。

★ 为什么敢批量：`probe115f/g` 已证明
  ① 76 份的尾部「本项目补充 —— 桌宠运行口径」块**逐字节完全相同**；
  ② 该块**一直到 EOF**、且**内部是 LF**（正文是 CRLF）；
  ③ 索引 `_personas.json` 的 `tail_sha256 = sha256(tail_text)`（LF、无尾换行），
     每记录 `chars`=含 CRLF 的字符数 · `bytes`=磁盘字节 · `sha256`=sha(raw) · `sha256_lf`=sha(LF 归一)。
  ⇒ 改这一处 = 一处改、76 份一致（**单一真源**），不必逐份手改。

本脚本做四件事：
  1) 用**单一的 NEW_BULLET** 生成 NEW_TAIL = OLD_TAIL + "\\n" + NEW_BULLET；
  2) 对 76 份 .txt 做**字节级**替换 `OLD_TAIL+"\\n"` → `NEW_TAIL+"\\n"`（正文一个字节都不碰）；
  3) 更新索引的 `tail_text` / `tail_sha256`（全局唯一值）＋ 每记录 4 个哈希/计数；
  4) **自证**：正文前缀逐字节等于 git HEAD 版本；尾块 == NEW_TAIL；所有哈希重算命中。

风险控制：
  · 默认 dry-run，只打印将要发生的事与自证结果；
  · 写盘前对每个文件要求 `raw.count(old_bytes) == 1`（不唯一就跳过并报红）；
  · 写盘后**立刻读回**再验一次（不信写入通道）。
"""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
INDEX = os.path.join(NPC, '_personas.json')

MARK = u'【本项目补充'

# ★★ 要铺进去的那一句。措辞与 `ralsei_persona.md` 的「我是什么」节**同源**，
#    但**不能点名作品**（76 份跨 Deltarune / Undertale / OneShot / UTY，点名就会串）。
#    刻意保持"知道 · 不悲观 · 不悲情 · 不聊设定"四要素，与 Ralsei 那条一一对应。
NEW_BULLET = (u'· 你知道自己是游戏里的一个角色，是被人写出来的 —— 这件事不让你难过，'
              u'就当是出身，日子照样是真的过。被问到就平平淡淡认一句，'
              u'认完顺着往下聊；不悲情，也不许把话拐到"设定""程序""模型"上去。')

BUF = io.StringIO()
S = {'n': 0, 'f': 0}


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    S['n'] += 1
    if not cond:
        S['f'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_head_bytes(relpath):
    """取 git HEAD 版本的文件字节（**独立来源**，用来证明"正文没被我碰过"）。"""
    p = subprocess.run(['git', 'show', 'HEAD:%s' % relpath], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout if p.returncode == 0 else None


def main():
    apply = '--apply' in sys.argv
    say('第115轮 · 铺 NPC 新口径 ｜ 模式 = %s' % ('**APPLY（写盘）**' if apply else 'DRY-RUN（只读）'))

    idx_raw = io.open(INDEX, 'rb').read()
    idx = json.loads(idx_raw.decode('utf-8'))
    OLD_TAIL = idx['tail_text']
    OLD_TAIL_SHA = idx['tail_sha256']
    NEW_TAIL = OLD_TAIL + '\n' + NEW_BULLET

    say('\n=== 0. 前置自证（口径必须是钉死的那套）===')
    ck('0a 索引 tail_sha256 == sha256(tail_text)', sha(OLD_TAIL.encode('utf-8')) == OLD_TAIL_SHA)
    ck('0b tail_text 里没有 CR（是 LF 口径）', '\r' not in OLD_TAIL)
    ck('0c 新句不与旧块重复', NEW_BULLET not in OLD_TAIL)
    say('  旧 tail_text = %d 字符 ｜ 新 = %d 字符（+%d）'
        % (len(OLD_TAIL), len(NEW_TAIL), len(NEW_TAIL) - len(OLD_TAIL)))
    say('  新 tail_sha256 = %s' % sha(NEW_TAIL.encode('utf-8')))

    old_bytes = (OLD_TAIL + '\n').encode('utf-8')
    new_bytes = (NEW_TAIL + '\n').encode('utf-8')

    files = sorted(f for f in os.listdir(PDIR) if f.endswith('.txt'))
    say('\n=== 1. 76 份 .txt：字节级替换 + 自证 ===')
    plans = []
    bad = []
    for fn in files:
        p = os.path.join(PDIR, fn)
        raw = io.open(p, 'rb').read()
        n = raw.count(old_bytes)
        if n != 1:
            bad.append((fn, 'old_tail 出现 %d 次（要求恰好 1）' % n))
            continue
        i = raw.index(old_bytes)
        new_raw = raw[:i] + new_bytes
        # 自证 1：尾块之后就是 EOF（正文不含尾块）
        if i + len(old_bytes) != len(raw):
            bad.append((fn, '尾块不在 EOF（后面还有 %d 字节）' % (len(raw) - i - len(old_bytes))))
            continue
        # 自证 2：正文前缀**逐字节**等于 git HEAD 版本的前缀（证明没碰正文）
        # ★ 必须用**正斜杠**：`os.path.join` 在 Windows 上给反斜杠，
        #   而 git 的 `<rev>:<path>` 只认正斜杠 —— 反斜杠会让 `git show` 直接 rc≠0
        #   （本轮 dry-run 就是被这条安全闸拦下的，属"夹具不保真先别写盘"的正确行为）。
        rel = 'ralsei_pet/assets/npc/persona/%s' % fn
        head = git_head_bytes(rel)
        if head is None:
            bad.append((fn, 'git show 取不到 HEAD 版本'))
            continue
        # ★ git blob 是 LF 归一化的（仓库 autocrlf=true）⇒ 比较前也要 LF 归一，
        #   否则每条都会"正文前缀不一致"（假红）。
        head_lf = head.replace(b'\r\n', b'\n')
        raw_lf = raw.replace(b'\r\n', b'\n')
        i_lf = raw_lf.index(old_bytes.replace(b'\r\n', b'\n'))
        if head_lf[:i_lf] != raw_lf[:i_lf]:
            bad.append((fn, '正文前缀与 HEAD 不一致（夹具不保真）'))
            continue
        # 自证 3：新尾块内部仍是 LF（不许引入 CR）
        if b'\r' in new_bytes:
            bad.append((fn, '新尾块里混进了 CR'))
            continue
        plans.append((fn, p, new_raw, i))
    say('  可改 = %d 份 ｜ 跳过/报红 = %d 份' % (len(plans), len(bad)))
    for fn, why in bad:
        say('    [SKIP] %s：%s' % (fn, why))
    ck('1a 76 份全部可改（没有跳过项）', not bad and len(plans) == len(files),
       '可改=%d/%d' % (len(plans), len(files)))
    ck('1b 新旧尾块长度差 == 新句长度 + 1（换行）',
       len(new_bytes) - len(old_bytes) == len(NEW_BULLET.encode('utf-8')) + 1)

    say('\n=== 2. 索引更新计划 ===')
    recs = idx.get('personas') or []
    say('  顶层：tail_text %d→%d 字符 ｜ tail_sha256 %s→%s'
        % (len(OLD_TAIL), len(NEW_TAIL), OLD_TAIL_SHA[:12],
           sha(NEW_TAIL.encode('utf-8'))[:12]))
    say('  记录：%d 条，每条更新 chars / bytes / sha256 / sha256_lf / tail_sha256' % len(recs))
    say('  不动：schema_version / source* / note / chars_def / count / by_work / extraction_fix / round*')

    if not apply:
        say('\n[DRY-RUN] 未写盘。加 `--apply` 执行。')
        return 0

    say('\n=== 3. 写盘 ===')
    for fn, p, new_raw, _i in plans:
        with io.open(p, 'wb') as f:
            f.write(new_raw)
    say('  已写 %d 份 .txt' % len(plans))

    new_idx = json.loads(json.dumps(idx, ensure_ascii=False))   # 深拷贝
    new_idx['tail_text'] = NEW_TAIL
    new_idx['tail_sha256'] = sha(NEW_TAIL.encode('utf-8'))
    for r in new_idx.get('personas', []):
        p = os.path.join(NPC, r['file'])
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        r['chars'] = len(txt)
        r['bytes'] = len(raw)
        r['sha256'] = sha(raw)
        r['sha256_lf'] = sha(raw.replace(b'\r\n', b'\n'))
        r['tail_sha256'] = new_idx['tail_sha256']

    indent = 2
    first_nl = idx_raw.find(b'\n')
    if first_nl > 0:
        probe = idx_raw[first_nl + 1:first_nl + 60].decode('utf-8', 'replace')
        indent = max(1, len(probe) - len(probe.lstrip(' ')))
    with io.open(INDEX, 'w', encoding='utf-8', newline='') as f:
        json.dump(new_idx, f, ensure_ascii=False, indent=indent)
        f.write('\n')
    say('  已写索引（indent=%d）' % indent)

    say('\n=== 4. 写盘后读回再验（不信写入通道）===')
    idx2 = json.loads(io.open(INDEX, 'rb').read().decode('utf-8'))
    ck('4a 索引读回：tail_sha256 正确',
       idx2['tail_sha256'] == sha(NEW_TAIL.encode('utf-8')))
    ck('4b 索引读回：tail_text 正确', idx2['tail_text'] == NEW_TAIL)
    # 非目标字段一个都没动。
    # ★ 首版判据写成"顶层所有键"，于是 `personas` 必然报红 —— 而它**正是要改的**。
    #   （又一次"判据过粗 = 误报"；改成**字段级**：顶层放行 2 个键，
    #    `personas` 每条放行 5 个字段，其余逐个比对。）
    top_moved = [k for k in idx if k not in ('tail_text', 'tail_sha256')
                 and idx[k] != idx2.get(k)]
    ck('4c 索引顶层非目标键逐字未变', not top_moved, '变了=%r' % (top_moved,))
    _ALLOWED = {'chars', 'bytes', 'sha256', 'sha256_lf', 'tail_sha256'}
    rec_moved = []
    _o, _n = idx.get('personas') or [], idx2.get('personas') or []
    if len(_o) != len(_n):
        rec_moved.append(('__count__', len(_o), len(_n)))
    for a, b in zip(_o, _n):
        for k in set(a) | set(b):
            if k in _ALLOWED:
                continue
            if a.get(k) != b.get(k):
                rec_moved.append((a.get('id'), k))
    ck('4c2 索引每条记录里只有那 5 个字段变', not rec_moved,
       '变了=%r' % (rec_moved[:5],))
    n_bad_rec = 0
    for r2 in idx2['personas']:
        p = os.path.join(NPC, r2['file'])
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        tail = txt[txt.find(MARK):]
        if not (tail == NEW_TAIL + '\n'
                and r2['chars'] == len(txt) and r2['bytes'] == len(raw)
                and r2['sha256'] == sha(raw)
                and r2['sha256_lf'] == sha(raw.replace(b'\r\n', b'\n'))):
            n_bad_rec += 1
    ck('4d 76 份文件：尾块 == NEW_TAIL 且 四个哈希/计数全部重算命中',
       n_bad_rec == 0, '不符=%d' % n_bad_rec)
    ck('4e 索引仍可被 json 解析、count 未变',
       idx2.get('count') == idx.get('count'))
    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (S['n'], S['f']))
    return 0 if S['f'] == 0 else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            ev = os.path.join(ROUND, '_evidence')
            with io.open(os.path.join(ev, 'apply115_npc_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
