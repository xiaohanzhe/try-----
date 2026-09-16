# -*- coding: utf-8 -*-
"""第十二轮侦察 5（E 盘接回后的真机确认）：vault 分支 + 中转站回迁。

第十二轮施工时 E 盘离线，vault 分支只做了环境变量模拟验证。本探针在
**E 盘真实在线**的前提下，验证：

  A. data_root() 确实选中 vault（E:\\RalseiMemory），而不是本地中转站；
  B. migrate_from_staging() 把中转站里的文件搬到 vault，源被清掉、长度一致；
  C. 七类产物解析出的路径全部落在 vault 内；
  D. memory_store 的记忆文件同样落在 vault；
  E. 迁移后文件内容完好（config/customization 仍是合法 JSON）。

运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_vault_real.py
输出：code-quality-audit/第十二轮/_evidence/round12_vault_real.txt
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MODS)

LINES = []
FAILS = []
CHECKS = [0]


def P(s=''):
    LINES.append(str(s))


def check(name, ok, detail=''):
    CHECKS[0] += 1
    mark = 'PASS' if ok else 'FAIL'
    if not ok:
        FAILS.append('%s :: %s' % (name, detail))
    P('  [%s] %-52s %s' % (mark, name, detail))


def snap(root):
    """{相对路径: 字节数}。"""
    out = {}
    if not root or not os.path.isdir(root):
        return out
    for dp, _dirs, files in os.walk(root):
        for n in files:
            fp = os.path.join(dp, n)
            try:
                out[os.path.relpath(fp, root).replace('\\', '/')] = os.path.getsize(fp)
            except OSError:
                pass
    return out


P('=' * 78)
P('【E 盘接回后的 vault 真机确认】')
P('=' * 78)

import data_store  # noqa: E402

before = data_store.describe()
P('')
P('--- 迁移前 describe() ---')
for k, v in sorted(before.items()):
    P('    %-18s = %s' % (k, v))

VAULT = before['vault_dir']
STAGING = before['staging_dir']

# ---------------------------------------------------------------- A. vault 命中
P('')
P('--- A. vault 分支 ---')
check('vault 在线（E 盘被识别）', bool(VAULT), 'vault_dir=%s' % VAULT)
check('vault 路径以 RalseiMemory 结尾',
      bool(VAULT) and os.path.basename(str(VAULT).rstrip('\\/')) == 'RalseiMemory',
      str(VAULT))
check('active_kind == vault', before['active_kind'] == 'vault', before['active_kind'])
check('vault 与 staging 不是同一目录',
      os.path.abspath(VAULT or '') != os.path.abspath(STAGING or ''),
      '%s vs %s' % (VAULT, STAGING))

# ---------------------------------------------------------------- B. 回迁
P('')
P('--- B. 中转站回迁 migrate_from_staging() ---')
st_before = snap(STAGING)
vault_before = snap(VAULT)
P('    迁移前 staging 文件数 = %d：%s' % (len(st_before), sorted(st_before)))
P('    迁移前 vault   文件数 = %d：%s' % (len(vault_before), sorted(vault_before)))

res = data_store.migrate_from_staging()
P('')
P('    migrate_from_staging() 返回：')
P('        moved   = %s' % res.get('moved'))
P('        skipped = %s' % res.get('skipped'))
P('        errors  = %s' % res.get('errors'))

st_after = snap(STAGING)
vault_after = snap(VAULT)
P('')
P('    迁移后 staging 文件数 = %d：%s' % (len(st_after), sorted(st_after)))
P('    迁移后 vault   文件数 = %d：%s' % (len(vault_after), sorted(vault_after)))

check('无迁移错误', not res.get('errors'), str(res.get('errors')))
check('中转站已清空', len(st_after) == 0, '剩余=%s' % sorted(st_after))
for rel, size in sorted(st_before.items()):
    # vault 里可能**同时**存在它自己的同名文件（更新）与一份 `.old` 留档，
    # 所以按**字节数**匹配，才能确定中转站那份到底落在哪。
    hit = None
    for key in (rel, rel + '.old'):
        if key in vault_after and vault_after[key] == size:
            hit = key
            break
    if hit is None:
        check('文件已落到 vault：%s' % rel, False,
              'staging=%d vault=%s vault.old=%s'
              % (size, vault_after.get(rel), vault_after.get(rel + '.old')))
    else:
        check('文件已落到 vault：%s%s' % (rel, '（落选者 .old 留档）' if hit.endswith('.old') else ''),
              True, 'size=%d' % size)

# ---------------------------------------------------------------- C. 七类产物
P('')
P('--- C. 七类产物路径解析 ---')
root, kind = data_store.data_root(create=False)
P('    当前数据根 = %s (%s)' % (root, kind))
P('')


def inside(p):
    try:
        return os.path.abspath(str(p)).lower().startswith(os.path.abspath(str(root)).lower())
    except Exception:
        return False


ARTS = [
    ('logs/ralsei_pet.log', 'logs/ralsei_pet.log'),
    ('logs/crash.log', 'logs/crash.log'),
    ('config.json', 'config.json'),
    ('customization_config.json', 'customization_config.json'),
    ('entertainment_data.json', 'entertainment_data.json'),
    ('growth_data.json', 'growth_data.json'),
    ('cache/jieba.cache', 'cache/jieba.cache'),
]
for name, rel in ARTS:
    p = data_store.artifact_path(rel, ensure_dir=False)
    ok = inside(p)
    check('产物在 vault 内：%s' % name, ok, p)

# 子系统真实路径（与 probe_paths 一致的口径）
import types as _types  # noqa: E402
stub = _types.SimpleNamespace()
subsys = []
try:
    from config_manager import ConfigManager
    subsys.append(('config.json', ConfigManager().config_file))
except Exception as e:
    subsys.append(('config.json', 'ERR %s' % e))
try:
    from customization_system import CustomizationSystem
    subsys.append(('customization_config.json', CustomizationSystem(stub).config_path))
except Exception as e:
    subsys.append(('customization_config.json', 'ERR %s' % e))
try:
    from entertainment_system import EntertainmentSystem
    subsys.append(('entertainment_data.json', EntertainmentSystem(stub).entertainment_data_path))
except Exception as e:
    subsys.append(('entertainment_data.json', 'ERR %s' % e))
try:
    from social_growth_system import SocialGrowthSystem
    subsys.append(('growth_data.json', SocialGrowthSystem(stub).growth_data_path))
except Exception as e:
    subsys.append(('growth_data.json', 'ERR %s' % e))
try:
    import logger_utils
    subsys.append(('logs/', logger_utils.get_log_dir()))
except Exception as e:
    subsys.append(('logs/', 'ERR %s' % e))
try:
    import text_segmenter
    subsys.append(('jieba 缓存', text_segmenter.default_cache_path()))
except Exception as e:
    subsys.append(('jieba 缓存', 'ERR %s' % e))

P('')
P('    子系统上报的真实路径：')
for nm, p in subsys:
    P('        %-26s %s   %s' % (nm, p, '[OK]' if inside(p) else '[!! 不在数据根]'))
    check('子系统路径在 vault 内：%s' % nm, inside(p), str(p))

# ---------------------------------------------------------------- D. memory_store
P('')
P('--- D. memory_store 记忆文件 ---')
try:
    import memory_store
    mdir, is_dev, dev = memory_store.default_memory_dir()
    mf = memory_store.memory_file_in(mdir)
    P('    default_memory_dir() = %s  (is_device=%s, dev=%s)' % (mdir, is_dev, dev))
    P('    memory_file          = %s' % mf)
    check('记忆目录即 vault', os.path.abspath(str(mdir)) == os.path.abspath(str(VAULT or '')),
          '%s vs %s' % (mdir, VAULT))
    check('记忆文件落在 vault 内', inside(mf), str(mf))
    check('设备发现目录 = vault',
          os.path.abspath(str(dev or '')) == os.path.abspath(str(VAULT or '')),
          '%s vs %s' % (dev, VAULT))
except Exception as e:
    check('memory_store 可用', False, str(e))

# ---------------------------------------------------------------- E. 内容完好
P('')
P('--- E. 迁移后内容完好性 ---')
for fn in ('config.json', 'customization_config.json'):
    p = os.path.join(str(root), fn)
    if os.path.exists(p):
        try:
            with io.open(p, 'r', encoding='utf-8') as f:
                json.load(f)
            check('JSON 仍合法：%s' % fn, True, p)
        except Exception as e:
            check('JSON 仍合法：%s' % fn, False, '%s: %s' % (p, e))
    else:
        P('    （%s 不存在，跳过）' % fn)

logp = os.path.join(str(root), 'logs', 'ralsei_pet.log')
if os.path.exists(logp):
    check('日志文件非空', os.path.getsize(logp) > 0, '%d 字节' % os.path.getsize(logp))

cached = os.path.join(str(root), 'cache', 'jieba.cache')
if os.path.exists(cached):
    check('jieba 缓存已随迁', os.path.getsize(cached) > 1000, '%d 字节' % os.path.getsize(cached))

# ---------------------------------------------------------------- 汇总
P('')
P('=' * 78)
P('汇总：%d 项检查，%d FAIL' % (CHECKS[0], len(FAILS)))
for f in FAILS:
    P('    !! ' + f)
P('=' * 78)

OUT = os.path.join(HERE, '_evidence', 'round12_vault_real.txt')
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s  (%d checks / %d fail)' % (OUT, CHECKS[0], len(FAILS)))
