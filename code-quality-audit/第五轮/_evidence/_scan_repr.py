import io
targets = {
 r"ralsei_pet\src\main.py": [(3752,3778)],
 r"ralsei_pet\modules\desktop_interaction.py": [(1062,1068),(2436,2450)],
 r"ralsei_pet\modules\entertainment_system.py": [(512,519),(198,208),(218,223),(335,340)],
}
out=[]
import os
base=r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
for rel,ranges in targets.items():
    p=os.path.join(base,rel)
    L=io.open(p,encoding="utf-8").read().split("\n")
    out.append("### "+rel)
    for a,b in ranges:
        out.append("--- lines %d-%d ---"%(a,b))
        for i in range(a-1,b):
            out.append("%d|%s"%(i+1,repr(L[i])))
io.open(os.path.join(base,"_scan_repr.txt"),"w",encoding="utf-8").write("\n".join(out))
print("ok")
