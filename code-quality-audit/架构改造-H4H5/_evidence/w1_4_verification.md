# W1-4 证据 · 抽出 VideoController（只搬方法不搬状态）

日期：2026-09-20（系统实测时间）
提交前状态：local uncommitted（HEAD = 747470b，父版本 = d8e2878）

## 0. 父版本 / 当前版本指纹

HEAD = 747470bb30807ef9050e50321b8f52478cf5e154

父版本 main.py  md5 = 79f23e762c2c298fc355845a5b367799  (546433 bytes)
当前   main.py  md5 = 202839c0ac8810050b65f1b7441f50ee  (542739 bytes)
行数：父 10278 → 当前 9991（−287）

A ≠ B 闸门：通过（md5 不同，探针未退化）

## 1. 四维验证

| 维度 | 探针 | 结果 |
|---|---|---|
| A 逐字等价 | verify_w1_4_unit.py | 51 PASS / 0 FAIL |
| B 行为等价 | verify_w1_4_e2e.py | 59 PASS / 0 FAIL |
| C A/B 对照 | verify_w1_4_ab.py | 7 PASS / 0 FAIL |
| D 全量回归 | code-quality-audit/regress/run_all.py | 24 套件全 IDENTICAL · 1161 PASS / 0 FAIL |

## 2. 现场重跑输出（原样）

### verify_w1_4_unit.py  exit=0
```
  PASS  ⑥ 注入后方法体内 _log_() 计数 +1
  PASS  ⑦ 注入体不被计数断言放过（原断言会 FAIL）
结果：PASS 51 / FAIL 0
```

### verify_w1_4_e2e.py  exit=0
```
  PASS  _log_() 返回宿主模块的 logger 对象
  PASS  宿主模块无 _log 时退回自身 logger
结果：PASS 59 / FAIL 0
```

### verify_w1_4_ab.py  exit=0
```
  PASS  场景 s5_err 行为一致
  PASS  场景 s6 行为一致
结果：PASS 7 / FAIL 0
```
