# -*- coding: utf-8 -*-
"""决定性测试：在**真正的老文件**上，逐模式验证写入能力。

背景纠错（重要）：
  上一轮 `probe_write51` 用的是 `os.open(..., O_WRONLY|O_APPEND)` —— 这是**追加**语义，
  与产品 `_save_config` 的 `open(tmp,'w') + os.replace` **不是同一种操作**。
  判据与故障模式不一致，本身就是"判据太窄"的隐患 ⇒ 本轮改为**逐模式对齐**。

被否证的假设：READONLY 属性（实测 `GetFileAttributesW` 全为 RO=0）。
剩余候选：
  H-a 「老文件被某进程独占」
  H-b 「`O_APPEND` 特有」            ⇒ 产品不用 append，若是此因则产品无关紧要
  H-c 「替换/截断既有文件被拒」      ⇒ 直接命中产品 `os.replace` 的失败路径

用**我自己的临时垃圾文件**做被测对象（`E:\\Download\\_tmp` 下 45 轮以来的废弃脚本），
破坏无副作用。逐模式独立测试，每步留痕。
"""
import os
import sys
import io
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

D = r'E:\Download\_tmp'
CAND = ['_detappend4.py', '_detappend3.py', '_chk.py', '_attrib.py', '_utf8chk.py']


def pick():
    for c in CAND:
        p = os.path.join(D, c)
        if os.path.exists(p):
            return p
    g = sorted(glob.glob(os.path.join(D, '_*.py')))
    return g[0] if g else None


def t(label, fn):
    try:
        fn()
        print('  [OK  ] %s' % label)
        return True
    except Exception as e:
        print('  [FAIL] %s  -> %s: %s' % (label, type(e).__name__, e))
        return False


def main():
    p = pick()
    if not p:
        print('找不到被测老文件'); return 1
    print('被测老文件:', p, os.path.getsize(p), 'bytes')
    orig = open(p, 'rb').read()
    print('原内容长度:', len(orig))

    print('\n--- 逐模式 ---')

    def m_read():
        f = open(p, 'r', encoding='utf-8', errors='replace'); f.close()
    t('① open(r)      只读', m_read)

    def m_rplus():
        f = open(p, 'r+'); f.close()
    t('② open(r+)     读写(不截断)', m_rplus)

    def m_append():
        f = open(p, 'a'); f.close()
    t('③ open(a)      追加', m_append)

    def m_osappend():
        fd = os.open(p, os.O_WRONLY | os.O_APPEND); os.close(fd)
    t('④ os.open(O_WRONLY|O_APPEND)', m_osappend)

    def m_bin_rplus():
        f = open(p, 'rb+'); f.close()
    t('⑤ open(rb+)    二进制读写', m_bin_rplus)

    def m_w():
        f = open(p, 'w'); f.close()
    oki_w = t('⑥ open(w)      截断写(★会清空)', m_w)

    # 恢复内容（若被清空）
    if oki_w:
        try:
            with open(p, 'wb') as f:
                f.write(orig)
            print('      -> 已恢复原内容')
        except Exception as e:
            print('      !! 恢复失败:', e)

    print('\n--- 产品写法复现：tmp -> os.replace 覆盖这个老文件 ---')
    tmp = os.path.join(D, 'zz_repl51.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write('{"new":1}')
        print('  [OK  ] 建 tmp')
    except Exception as e:
        print('  [FAIL] 建 tmp ->', type(e).__name__, e)
    t('⑦ os.replace(tmp, 老文件)', lambda: os.replace(tmp, p))

    print('\n--- 收尾 ---')
    for q in (tmp,):
        try:
            if os.path.exists(q):
                os.remove(q); print('  已清理', q)
        except Exception as e:
            print('  ★ 清理失败', q, e)
    try:
        now = open(p, 'rb').read()
        print('  被测文件现在 %d bytes（原 %d）%s' % (len(now), len(orig),
              '（未被破坏）' if len(now) == len(orig) else '（已变更，属预期/被测对象为垃圾文件）'))
    except Exception as e:
        print('  读取失败:', e)

    print('\n===== 判读 =====')
    print('  ② 失败 + ③④ 失败 ⇒ H-a/H-c（既有文件整体不可写）')
    print('  ③④ 失败而 ② 成功 ⇒ H-b（仅 O_APPEND 特有，产品不受影响）')
    print('  ⑦ 成功 ⇒ A/ B 两组失败与产品的 replace 失败**不同源**，需重找判据')
    return 0


if __name__ == '__main__':
    sys.exit(main())
