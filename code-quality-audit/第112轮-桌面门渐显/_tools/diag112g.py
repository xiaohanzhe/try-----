# -*- coding: utf-8 -*-
"""诊断：画布抓图里 4 扇门区域到底有没有像素。"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules')); sys.path.insert(0, os.path.join(PKG, 'src'))
os.environ.setdefault('RALSEI_TEST_MODE', '1')
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)
def poll(ms):
    t=time.time()*1000.0+ms
    while time.time()*1000.0<t:
        try: _app.processEvents()
        except Exception: pass
        time.sleep(0.01)
import main as _M
pet=_M.RalseiPet(); pet.show(); poll(2500)
sc=pet.__dict__.get('scene_canvas')
sds=list(getattr(sc,'_screen_doors',[]) or [])
print('screen_doors=', len(sds))
for rep in range(4):
    poll(500)
    img=sc.grab().toImage()
    # 强制重绘后再抓
    sc.update(); _app.processEvents(); poll(120)
    img2=sc.grab().toImage()
    print('--- rep%d  size=%dx%d  last_drawn=%s' % (rep, img2.width(), img2.height(), sc.last_drawn))
    for sid,(x,y,w,h) in sds:
        # 门区域非透明像素数
        n=0; tot=0
        for yy in range(y+2, y+h-2, max(1,(h-4)//8)):
            for xx in range(x+2, x+w-2, max(1,(w-4)//8)):
                if 0<=xx<img2.width() and 0<=yy<img2.height():
                    tot+=1
                    if img2.pixelColor(xx,yy).alpha()>8: n+=1
        print('   %-34s rect=%r  opaque=%d/%d' % (os.path.basename(sid), (x,y,w,h), n, tot))
