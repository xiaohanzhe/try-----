# -*- coding: utf-8 -*-
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PY = r'C:\Python311\python.exe'
r = subprocess.run([PY, os.path.join(HERE, 'measure141b_lang.py')],
                   capture_output=True)
sys.stdout.write(r.stdout.decode('utf-8', 'replace'))
sys.stderr.write(r.stderr.decode('utf-8', 'replace'))
print('\n[exit]', r.returncode)
