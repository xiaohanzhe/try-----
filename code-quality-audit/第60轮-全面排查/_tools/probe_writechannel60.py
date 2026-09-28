#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 探针 F：判定「写 E:\\RalseiMemory 被拒」到底是**谁**在拒。

现象：
  · 真机跑 App 时，`config.json` / `memory.json` / `logs/ralsei_pet.log` 的写入
    连续报 `[WinError 5] 拒绝访问` / `[Errno 13] Permission denied`（两次运行均复现）；
  · 而**同一分钟**里本探针用新建文件写同一个目录**完全正常**；
  · ACL / 只读属性都正常。

待验假设（来自本项目既有经验行）：
  「**新建文件 OK；覆写/改名到**已存在**的目标被拒**」——
  若是，则 App 的失败与 E 盘无关、与 App 也无关，而是**宿主写入通道**的瞬时状态；
  若否，则要看是不是 E 盘**特定目录**的问题。

设计（每步独立、逐个报结果，绝不合并成一句"都失败"）：
  A. 新建文件            （两侧：E 盘 / 工作区）
  B. **覆写**刚建的同一个文件
  C. 新建 tmp → `os.replace` 到**已存在**的目标
  D. 新建 tmp → `os.replace` 到**不存在**的目标
  E. 以 append 模式打开**已存在**文件
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)

WORK = tempfile.mkdtemp(prefix='wchk60_')
TARGETS = [
    ('E盘_临时区', r'E:\Download\_tmp'),
    ('E盘_vault', r'E:\RalseiMemory'),
    ('工作区', os.path.join(REPO, 'code-quality-audit', '第60轮-全面排查', '_evidence')),
    ('系统TEMP', tempfile.gettempdir()),
]


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


def probe(label, d):
    res = {}
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        return {'label': label, 'dir': d, 'fatal': '%s: %s' % (type(e).__name__, e)}
    base = os.path.join(d, '_wchk60')

    def w(path, text, mode='w'):
        try:
            with io.open(path, mode, encoding='utf-8') as f:
                f.write(text)
            return 'OK'
        except OSError as e:
            return '%s: %s' % (type(e).__name__, e)

    # A 新建
    res['A_新建'] = w(base + '_a.txt', 'a1')
    # B 覆写刚建的同一个文件
    res['B_覆写已有'] = w(base + '_a.txt', 'a2')
    # ★★ 夹具修正（v1 在这里是**假的**）：C 步必须**先把目标建出来**，
    #    否则 `_rep` 只是"replace 到一个不存在的目标"，根本没测到"已有目标"这一路。
    #    v1 正是靠这个假夹具得出"全部 OK"的结论 —— 与本项目铁律
    #    "报红先问夹具真把破坏写进去了吗" 是同一类错误的反向版本。
    w(base + '_c.txt', 'pre-existing')          # 先建出"已存在"的目标
    res['_C_目标确已存在'] = 'YES' if os.path.exists(base + '_c.txt') else 'NO'
    # C 新建 tmp → replace 到**已存在**目标
    w(base + '_c.tmp', 'c')
    res['C_replace到已有'] = _rep(base + '_c.tmp', base + '_c.txt')
    # D 新建 tmp → replace 到不存在目标
    w(base + '_d.tmp', 'd')
    res['D_replace到新建'] = _rep(base + '_d.tmp', base + '_d_target.txt')
    # E append 打开已存在文件
    res['E_append已有'] = w(base + '_a.txt', 'a3', 'a')
    # ★ F 目标被**别人持有读句柄**时再 replace（模拟 App 自己开着 config.json）
    w(base + '_f.txt', 'pre')
    w(base + '_f.tmp', 'new')
    try:
        hold = io.open(base + '_f.txt', 'r', encoding='utf-8')
        try:
            res['F_replace_目标被持有'] = _rep(base + '_f.tmp', base + '_f.txt')
        finally:
            hold.close()
    except OSError as e:
        res['F_replace_目标被持有'] = '开句柄就失败: %s' % e
    res['label'] = label
    res['dir'] = d
    return res


def _rep(src, dst):
    try:
        os.replace(src, dst)
        return 'OK'
    except OSError as e:
        return '%s: %s' % (type(e).__name__, e)


def main():
    print('=' * 72)
    print('探针 F —— 写入通道逐项体检（新建 / 覆写 / replace / append）')
    print('=' * 72)
    rows = []
    for label, d in TARGETS:
        r = probe(label, d)
        rows.append(r)
        print()
        print('【%s】%s' % (label, d))
        if r.get('fatal'):
            print('      目录不可用：%s' % r['fatal'])
            continue
        for k in ('A_新建', 'B_覆写已有', '_C_目标确已存在', 'C_replace到已有',
                  'D_replace到新建', 'E_append已有', 'F_replace_目标被持有'):
            if k not in r:
                continue
            v = r.get(k, '-')
            mark = '  ' if v in ('OK', 'YES') else '!!'
            print('      %s %-18s %s' % (mark, k, v[:110]))
    print()
    print('-' * 72)
    ok = True
    # 判据：三个"新目标"操作必须成功（否则是通道整体坏）；据此判断"已有目标"是否被单独拒
    for r in rows:
        if r.get('fatal'):
            continue
        ok &= check(r.get('A_新建') == 'OK', '%s：新建文件必须成功' % r['label'])
    new_ok = all(r.get('A_新建') == 'OK' for r in rows if not r.get('fatal'))
    exist_fail = [r['label'] for r in rows
                  if not r.get('fatal') and r.get('B_覆写已有') != 'OK']
    print()
    print('  结论性事实：新建=%s；覆写已有被拒的目标=%s'
          % ('全 OK' if new_ok else '有失败', exist_fail or '无'))
    print('  ⇒ %s' % ('符合"新建 OK、覆写/改名到已存在目标被拒"的通道特征'
                      if (new_ok and exist_fail) else '不符合该假设，需另找原因'))
    print('=' * 72)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
