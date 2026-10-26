# -*- coding: utf-8 -*-
"""第113轮k-e：同一个区里的**同一类地方**只留一个候选。

问题（端到端实测）：
    【这会儿能张罗的事】要去办点事，你们这儿真有的地方：
      家乡 · hospital hallway（医院）、家乡 · hospital lobby（医院）、家乡 · hospital …
四项里三条是**同一家医院的走廊/大厅/病房** —— 用户要的是「那要不去 XXX」，
给他三间同院房间只会挑花眼。原作里家乡真有的办事地点其实是
**医院 / 学校 / 图书馆**三类，去重后正好说出来。

★ 去重键 = `(区名, 中文类型名)`：
  · 同一家医院的四个房间 ⇒ 合成一条；
  · `我的城堡镇` 的餐馆 与 `我的城堡镇` 的咖啡店 ⇒ 类型不同，**两条都留**；
  · 保留 `sid` 升序里的**第一条**（确定性：同一句话每次同样的结果）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
NL = '\r\n'


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(t)


OLD = '''        out = []
        try:
            for sid, info in self._scene_label_map().items():
                sid_s = str(sid)
                if not sid_s.startswith(chapter + '.'):
                    continue
                _ch, _area, _name, _derived, _raw = info
                parts = sid_s.split('.')
                area_id = parts[1] if len(parts) >= 3 else ''
                core = npc_life_mod.room_word(_raw)
                if area_id and core.startswith(area_id + ' '):
                    core = core[len(area_id) + 1:]
                # 强信号文本：剥过前缀/区段名的原作名 +（非推导时）场景名
                text = '%s %s' % (core, '' if _derived else _name)
                hits = npc_life_mod.place_matches(text, kind)
                if not hits:
                    continue
                lbl = self._activity_label(sid_s, core, hits)
                if lbl:
                    out.append((sid_s, lbl))
        except Exception as e:
            _log.debug('活动候选筛选失败（按无候选处理）: %s', e)
            out = []

        out.sort(key=lambda pair: pair[0])   # 确定性顺序 ⇒ 同一句话每次同样结果
        cache[key] = out
        return out'''

NEW = '''        rows = []       # (sid, 标签, 去重键)
        try:
            for sid, info in self._scene_label_map().items():
                sid_s = str(sid)
                if not sid_s.startswith(chapter + '.'):
                    continue
                _ch, _area, _name, _derived, _raw = info
                parts = sid_s.split('.')
                area_id = parts[1] if len(parts) >= 3 else ''
                core = npc_life_mod.room_word(_raw)
                if area_id and core.startswith(area_id + ' '):
                    core = core[len(area_id) + 1:]
                # 强信号文本：剥过前缀/区段名的原作名 +（非推导时）场景名
                text = '%s %s' % (core, '' if _derived else _name)
                hits = npc_life_mod.place_matches(text, kind)
                if not hits:
                    continue
                lbl = self._activity_label(sid_s, core, hits)
                if not lbl:
                    continue
                # ★ 去重键 =（区名, 中文类型名）。同一家医院的走廊/大厅/病房
                #   合成一条；不同区或不同类型**不合并**（餐馆 ≠ 咖啡店）。
                area_k = '' if npc_life_mod.place_container(_area) else str(_area or '')
                rows.append((sid_s, lbl, (area_k, npc_life_mod.place_type_name(hits[0]))))
        except Exception as e:
            _log.debug('活动候选筛选失败（按无候选处理）: %s', e)
            rows = []

        rows.sort(key=lambda t: t[0])    # 确定性顺序 ⇒ 同一句话每次同样结果
        out = []
        seen = set()
        for sid_s, lbl, dkey in rows:
            if dkey in seen:
                continue
            seen.add(dkey)
            out.append((sid_s, lbl))
        cache[key] = out
        return out'''


def main():
    t = read(MAIN)
    old = OLD.replace('\n', NL)
    new = NEW.replace('\n', NL)
    if old not in t:
        if 'rows.sort(key=lambda t: t[0])' in t:
            print('[SKIP] 已是去重版')
            return 0
        print('[FAIL] 锚点没命中')
        return 1
    t = t.replace(old, new, 1)
    write(MAIN, t)
    print('[ OK ] _activity_places 加去重')

    import ast
    src = read(MAIN)
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1
    n = src.count('\n')
    crlf = src.count('\r\n')
    print('行=%d CRLF=%d gap=%d' % (n, crlf, n - crlf))
    return 0


if __name__ == '__main__':
    sys.exit(main())
