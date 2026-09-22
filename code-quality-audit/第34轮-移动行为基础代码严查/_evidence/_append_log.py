import io, os

base = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory'
log = os.path.join(base, '2026-09-22.md')
add = os.path.join(base, '_r34_append.md')

s = io.open(log, encoding='utf-8').read()
a = io.open(add, encoding='utf-8').read()
io.open(log, 'w', encoding='utf-8', newline='').write(s + a)
os.remove(add)
new = io.open(log, encoding='utf-8').read()
print('OK: log bytes =', len(new.encode('utf-8')), 'chars =', len(new))
