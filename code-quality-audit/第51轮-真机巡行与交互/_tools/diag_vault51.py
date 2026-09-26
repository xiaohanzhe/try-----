# -*- coding: utf-8 -*-
"""vault（E:\\RalseiMemory）写入失败诊断 —— WinError 5 根因取证。

背景：真机日志里 `config_manager._save_config` 报
  `[WinError 5] 拒绝访问。: 'E:\\RalseiMemory\\config.json.tmp' -> 'E:\\RalseiMemory\\config.json'`
并且用户级记忆里也躺着一条同症状的悬案（`memory.json.tmp -> memory.json`）。
这不止影响托盘提示——**任何 `config_manager.set()` 都写不进去**（用户改设置会静默失效）。

只做只读勘察 + 一次可回滚的写入探针（测完删探针文件，不留垃圾）。
"""
import os
import sys
import io
import json
import stat
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VAULT = r'E:\RalseiMemory'
PROBE = os.path.join(VAULT, '_probe51.tmp')
TARGET = os.path.join(VAULT, '_probe51_target.json')


def describe(path):
    try:
        st = os.stat(path)
    except Exception as e:
        return 'stat 失败 %s' % e
    mode = st.st_mode
    return ('size=%-8d mtime=%s  readonly=%s  hidden=%s  dir=%s'
            % (st.st_size,
               time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
               bool(mode & stat.S_IREAD) and not bool(mode & stat.S_IWRITE),
               bool(getattr(st, 'st_file_attributes', 0) & 2),
               stat.S_ISDIR(mode)))


def main():
    print('=' * 70)
    print('vault 诊断:', VAULT)
    print('=' * 70)
    print('存在:', os.path.isdir(VAULT))

    # 1) 卷信息
    try:
        import ctypes
        vol = ctypes.create_unicode_buffer(64)
        fs = ctypes.create_unicode_buffer(64)
        serial = ctypes.c_ulong()
        maxlen = ctypes.c_ulong()
        flags = ctypes.c_ulong()
        root = os.path.splitdrive(VAULT)[0] + '\\'
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            root, vol, 64, ctypes.byref(serial), ctypes.byref(maxlen),
            ctypes.byref(flags), fs, 64)
        print('GetVolumeInformation ok=%s  卷标=%r  文件系统=%r  flags=0x%x'
              % (ok, vol.value, fs.value, flags.value))
    except Exception as e:
        print('卷信息失败:', e)

    # 2) 列目录 + 属性
    print('\n--- 目录内容 ---')
    try:
        for f in sorted(os.listdir(VAULT)):
            fp = os.path.join(VAULT, f)
            print('  %-34s %s' % (f, describe(fp)))
    except Exception as e:
        print('  列目录失败:', e)

    # 3) 读运行时 config（真正的运行时配置在这里，不是 ralsei_pet/config.json）
    cfg = os.path.join(VAULT, 'config.json')
    print('\n--- 运行时 config.json ---')
    if os.path.exists(cfg):
        print('  属性:', describe(cfg))
        try:
            d = json.load(open(cfg, encoding='utf-8'))
            print('  movement =', json.dumps(d.get('movement'), ensure_ascii=False))
            print('  ui       =', json.dumps(d.get('ui'), ensure_ascii=False))
            print('  顶层键   =', sorted(d.keys())[:40])
        except Exception as e:
            print('  读取失败:', type(e).__name__, e)
    else:
        print('  不存在（⇒ 产品一直用 defaults，且每次写盘都失败）')

    # 4) 写入探针：tmp -> replace
    print('\n--- 写入探针（tmp -> os.replace）---')
    for p in (PROBE, TARGET):
        try:
            if os.path.exists(p):
                os.remove(p); print('  清理旧探针', p)
        except Exception as e:
            print('  清理失败', p, e)
    try:
        with open(PROBE, 'w', encoding='utf-8') as f:
            f.write('{"probe":1}')
        print('  ① open(tmp,"w") 成功 ->', describe(PROBE))
    except Exception as e:
        print('  ① open(tmp,"w") 失败:', type(e).__name__, e)
    try:
        open(TARGET, 'w', encoding='utf-8').write('old')
        print('  ② 建目标文件成功 ->', describe(TARGET))
    except Exception as e:
        print('  ② 建目标文件失败:', type(e).__name__, e)
    try:
        os.replace(PROBE, TARGET)
        print('  ③ os.replace 成功 ✅')
    except Exception as e:
        print('  ③ os.replace 失败 ❌', type(e).__name__, e)
        # 4b) 换用 remove+rename 试试
        try:
            os.remove(TARGET)
            os.rename(PROBE, TARGET)
            print('  ③b remove+rename 成功 ✅（说明是"目标存在"引发的 replace 失败）')
        except Exception as e2:
            print('  ③b remove+rename 也失败 ❌', type(e2).__name__, e2)

    # 5) 直接覆盖写（不用 tmp）
    print('\n--- 直接覆盖写（无 tmp）---')
    try:
        with open(TARGET, 'w', encoding='utf-8') as f:
            f.write('{"probe":2}')
        print('  直接覆盖写成功 ✅')
    except Exception as e:
        print('  直接覆盖写失败 ❌', type(e).__name__, e)

    # 6) 清理
    for p in (PROBE, TARGET):
        try:
            if os.path.exists(p):
                os.remove(p); print('  已清理', p)
        except Exception as e:
            print('  清理失败', p, e)

    # 7) 是否有进程握着 config.json / memory.json
    print('\n--- 可能持有该目录句柄的进程 ---')
    try:
        import psutil
        me = os.getpid()
        hits = []
        for p in psutil.process_iter(['pid', 'name']):
            if p.info['pid'] == me:
                continue
            try:
                for f in p.open_files():
                    if 'RalseiMemory' in f.path:
                        hits.append((p.info['pid'], p.info['name'], f.path))
            except Exception:
                continue
        if hits:
            for h in hits:
                print('  ', h)
        else:
            print('   无（正常）')
    except Exception as e:
        print('   检查失败:', e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
