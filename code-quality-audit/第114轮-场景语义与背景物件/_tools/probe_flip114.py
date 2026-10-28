# -*- coding: utf-8 -*-
"""证据脚本：tmx 的 gid 翻转位到底用不用？（结论：**一次都没用**）

★ 为什么要问：`gid_to()` 里 `gid & 0x1FFFFFFF` 掩掉了高位。
  如果原作真用翻转位（H_FLIP=0x80000000 / V_FLIP=0x40000000 / D_FLIP=0x20000000），
  那渲染出来的图和实物就是**镜像不一致**的，物件裁剪图也会误导人；
  更糟的是 `objects_name114.py` 按局部 id 合并「图案签名」时会把镜像件错并。

★ 这不是一次性 temp：换游戏版本后要**重跑**。哪天报出非零，就说明
  ① `render_room.py` 必须支持镜像；② 图案签名要带上翻转位（类数会变多，清单要重出）。
"""
import os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T

H, V, D = 0x80000000, 0x40000000, 0x20000000


def main():
    flag = collections.Counter()
    per_map = collections.Counter()
    for n in range(1, 264):
        try:
            m = T.load_map(n)
        except Exception as e:
            flag['loadfail'] += 1
            continue
        for li, ly in enumerate(m['layers']):
            for g in ly['data']:
                if not g:
                    continue
                if g & H:
                    flag['H'] += 1
                if g & V:
                    flag['V'] += 1
                if g & D:
                    flag['D'] += 1
                if g & (H | V | D):
                    per_map[n] += 1
    print('翻转位统计: %s' % dict(flag))
    if per_map:
        print('用到翻转的图 %d 张，最多的: %s' %
              (len(per_map), per_map.most_common(8)))
    else:
        print('⇒ 263 间房没有任何一格使用翻转位：渲染不做镜像是**正确**的')


if __name__ == '__main__':
    main()
