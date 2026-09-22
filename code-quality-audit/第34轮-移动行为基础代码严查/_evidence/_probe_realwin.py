# -*- coding: utf-8 -*-
"""第34轮续 真机探针：读 RalseiPet 真实窗口尺寸与缩放因子（验证 F34-3 量级）

为什么必须真机：`assets/sprites/` 在仓库里是空的（精灵图属用户本地资源），
原始帧宽高只能由 sprite_loader 在运行时从 PNG 读出 ⇒ 离线无从得知。

做法（不跑 app.exec_ 长驻）：
  · 只 import main 模块（不触发 __main__ 块 → 不跑 check_single_instance）
  · 建 QApplication + 实例化 RalseiPet + show()
  · QTimer.singleShot 延时 1500ms 读属性 → 落盘 → app.quit()
  · 全程只读，不改任何状态
"""
import io
import os
import sys

OUT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence\29_真机窗口尺寸.txt'
SRC = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src'

buf = []


def emit(s):
    buf.append(s)
    print(s)


emit('== 真机取尺寸 ==')
emit('python: %s' % sys.version.split()[0])
emit('cwd: %s' % os.getcwd())

sys.path.insert(0, SRC)
os.chdir(SRC)

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
    import importlib
    m = importlib.import_module('main')
    emit('main 模块导入成功')
except Exception as e:
    import traceback
    emit('main 导入失败: %r' % e)
    emit(traceback.format_exc())
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(buf))
    sys.exit(1)

app = QApplication(sys.argv)

try:
    pet = m.RalseiPet()
    pet.show()
    emit('RalseiPet 实例化 + show() 成功')
except Exception as e:
    import traceback
    emit('RalseiPet 实例化失败: %r' % e)
    emit(traceback.format_exc())
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(buf))
    sys.exit(1)


def probe():
    try:
        emit('')
        emit('== 读到的事实 ==')
        emit('self.width()  = %s' % repr(pet.width()))
        emit('self.height() = %s' % repr(pet.height()))
        emit('_cached_scale_factor (getattr 默认 2.0) = %s'
             % repr(getattr(pet, '_cached_scale_factor', '<未设置>')))
        emit('_anim_container_size = %s' % repr(getattr(pet, '_anim_container_size', None)))
        emit('_anim_container_key = %s' % repr(getattr(pet, '_anim_container_key', None)))
        emit('current_animation = %s' % repr(getattr(pet, 'current_animation', None)))

        # sprite_loader 的 frame_container_size（Phase2 口径）
        sl = getattr(pet, 'sprite_loader', None)
        if sl is not None:
            emit('sprite_loader.frame_container_size = %s'
                 % repr(getattr(sl, 'frame_container_size', None)))
            _sp = getattr(sl, 'sprites', None)
            if isinstance(_sp, dict):
                emit('sprite_loader.sprites 组数 = %d' % len(_sp))
                _idle = _sp.get('idle')
                if _idle:
                    _szs = [(f.width(), f.height()) for f in _idle
                            if f is not None and not f.isNull()]
                    emit('idle 帧原始尺寸 = %s' % repr(_szs))
                # 找一个含最宽帧的动画，用于说明 138 从何而来
                _best = None
                for _k, _fr in _sp.items():
                    for _f in _fr:
                        if _f is None or _f.isNull():
                            continue
                        if _best is None or _f.width() > _best[1]:
                            _best = (_k, _f.width(), _f.height())
                emit('全库最宽帧 = %s' % repr(_best))
                _tall = None
                for _k, _fr in _sp.items():
                    for _f in _fr:
                        if _f is None or _f.isNull():
                            continue
                        if _tall is None or _f.height() > _tall[2]:
                            _tall = (_k, _f.width(), _f.height())
                emit('全库最高帧 = %s' % repr(_tall))

        # 关键：与 generate_new_move_target 里 `sprite_size = int(50*2.0) = 100` 比对
        w, h = pet.width(), pet.height()
        emit('')
        emit('== 与硬编码 sprite_size=100 的比对 ==')
        emit('sprite_size(硬编码) = 100')
        emit('实际窗口 = %d x %d' % (w, h))
        emit('宽是否等于 100 => %s' % (w == 100))
        emit('高是否等于 100 => %s' % (h == 100))
        emit('是否正方形 => %s（正方形时单标量用法无害）' % (w == h))
        emit('X 边界偏差 = 实际宽 - 100 = %d px' % (w - 100))
        emit('Y 边界偏差 = 实际高 - 100 = %d px' % (h - 100))
        emit('')
        emit('== 与产品夹取口径（self.width()/self.height()）的比对 ==')
        emit('产品 L2009/L2155 用 self.width()/self.height() = %d/%d' % (w, h))
        emit('generate_new_move_target L1612/1620/1635/1636 用 sprite_size = 100')
        emit('⇒ 两套口径相差 %d px（X）/ %d px（Y）' % (abs(w - 100), abs(h - 100)))
    except Exception as e:
        import traceback
        emit('probe 异常: %r' % e)
        emit(traceback.format_exc())
    finally:
        with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(buf))
        app.quit()


QTimer.singleShot(1500, probe)
app.exec_()

# 收尾：把窗口关掉，避免残留
try:
    pet.close()
except Exception:
    pass
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(buf))
print('DONE -> %s' % OUT)
