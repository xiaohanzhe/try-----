# 第85轮 · 原作锚点表（I1/I2/I4/I5/I10）
> 本表由 `_tools/distill85.py` 从 `_evidence/dr85_code.json` 机械抽取，**每条都可回原 json `in` 一次**。
> 抽不到的一律写 `<NOT-FOUND>`，不编造。

- 产物：`dr85_code.json` code=70（nonempty=70 / gml_ok=50），`dr85_globals.json` global=258，`dr85_strings.json` str=7

## A. 光/暗世界基准速度（`bwspeed`）与跑动三段（I1/I2）
来源：`gml_Object_obj_mainchara_Create_0`（3295 chars）
```gml
  17 | darkmode = global.darkzone;
  18 | if (darkmode == 1)
  32 | wspeed = 3;
  33 | bwspeed = 3;
  34 | if (darkmode == 1)
  36 |     bwspeed = 4;
  37 |     wspeed = 4;
```
来源：`gml_Object_obj_mainchara_Step_0`（15950 chars）— `if (run == 1)` 整段（起始行 70）
```gml
    if (run == 1)
    {
        if (darkmode == 0)
        {
            wspeed = bwspeed + 1;
            if (runtimer > 10)
            {
                wspeed = bwspeed + 2;
            }
            if (runtimer > 60)
            {
                wspeed = bwspeed + 3;
            }
        }
        if (darkmode == 1)
        {
            wspeed = bwspeed + 2;
            if (runtimer > 10)
            {
                wspeed = bwspeed + 4;
            }
            if (runtimer > 60)
            {
                wspeed = bwspeed + 5;
            }
        }
    }
```
松键回落段（起始行 97）：
```gml
    if (run == 0)
    {
        wspeed = bwspeed;
    }
```

## B. 跑表 `runtimer` 的推进与清零（I1 核心）
起始行 350
```gml
    runmove = 0;
    if (run == 1 && xmeet == 0 && ymeet == 0 && xymeet == 0)
```
`autorun` 起点（`runtimer = 200 / 50`）：
```gml
  62 |             runtimer = 200;
  67 |             runtimer = 50;
```

## C. 按键判定（`button1_p` 确认 / `button2_h` 跑 / `button3_p` 菜单）
跑键（含 `global.flag\[11\]` 反转那条） —— `button2_h\(\)`（起始行 40）：
```gml
        if (button2_h() && twobuffer < 0)
        {
            run = 0;
        }
```
菜单键 —— `button3_p\(\)`（起始行 19）：
```gml
    if (button3_p() && threebuffer < 0)
    {
        if (global.flag[7] == 0 && battlemode == 0)
        {
            with (obj_darkcontroller)
            {
                threebuffer = 2;
            }
            with (obj_overworldc)
            {
                movenoise = 1;
                threebuffer = 2;
            }
            global.menuno = 0;
            global.interact = 5;
            threebuffer = 2;
            twobuffer = 2;
        }
    }
```
确认键 —— `button1_p\(\)`（起始行 478）：
```gml
        if (button1_p())
        {
            thisinteract = 0;
            d = global.darkzone + 1;
            if (global.facing == 1)
            {
                if (collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x + sprite_width + (13 * d), y + sprite_height, obj_interactable, false, true))
                {
                    thisinteract = 1;
                }
                if (collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x + sprite_width + (13 * d), y + sprite_height, obj_interactablesolid, false, true))
                {
                    thisinteract = 2;
                }
            }
            if (thisinteract > 0)
            {
                if (thisinteract == 1)
                {
                    interactedobject = collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x + sprite_width + (13 * d), y + sprite_height, obj_interactable, false, true);
                }
                if (thisinteract == 2)
                {
                    interactedobject = collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x + sprite_width + (13 * d), y + sprite_height, obj_interactablesolid, false, true);
                }
                if (interactedobject != -4)
                {
                    with (interactedobject)
                    {
                        facing = 3;
                    }
                    with (interactedobject)
                    {
                        scr_interact();
                    }
                }
            }
            thisinteract = 0;
            if (global.facing == 3)
            {
                if (collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x - (13 * d), y + sprite_height, obj_interactable, false, true))
                {
                    thisinteract = 1;
                }
                if (collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x - (13 * d), y + sprite_height, obj_interactablesolid, false, true))
                {
                    thisinteract = 2;
                }
            }
            if (thisinteract > 0)
            {
                if (thisinteract == 1)
                {
                    interactedobject = collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x - (13 * d), y + sprite_height, obj_interactable, false, true);
                }
                if (thisinteract == 2)
                {
                    interactedobject = collision_rectangle(x + (sprite_width / 2), y + (6 * d) + (sprite_height / 2), x - (13 * d), y + sprite_height, obj_interactablesolid, false, true);
                }
                if (interactedobject != -4)
                {
                    with (interactedobject)
                    {
                        facing = 1;
                    }
                    with (interactedobject)
                    {
                        scr_interact();
                    }
                }
            }
            thisinteract = 0;
            if (global.facing == 0)
            {
                if (collision_rectangle(x + (4 * d), y + (28 * d), (x + sprite_width) - (4 * d), y + sprite_height + (15 * d), obj_interactable, false, true))
                {
                    thisinteract = 1;
                }
                if (collision_rectangle(x + (4 * d), y + (28 * d), (x + sprite_width) - (4 * d), y + sprite_height + (15 * d), obj_interactablesolid, false, true))
                {
                    thisinteract = 2;
                }
            }
            if (thisinteract > 0)
            {
                if (thisinteract == 1)
                {
                    interactedobject = collision_rectangle(x + (4 * d), y + (28 * d), (x + sprite_width) - (4 * d), y + sprite_height + (15 * d), obj_interactable, false, true);
                }
                if (thisinteract == 2)
                {
                    interactedobject = collision_rectangle(x + (4 * d), y + (28 * d), (x + sprite_width) - (4 * d), y + sprite_height + (15 * d), obj_interactablesolid, false, true);
                }
                if (interactedobject != -4)
                {
                    with (interactedobject)
                    {
                        facing = 2;
                    }
                    with (interactedobject)
                    {
                        scr_interact();
                    }
                }
            }
            thisinteract = 0;
            if (global.facing == 2)
            {
                if (collision_rectangle(x + 3, (y + sprite_height) - (5 * d), (x + sprite_width) - (5 * d), y + (5 * d), obj_interactable, false, true))
                {
                    thisinteract = 1;
                }
                if (collision_rectangle(x + 3, (y + sprite_height) - (5 * d), (x + sprite_width) - (5 * d), y + (5 * d), obj_interactablesolid, false, true))
                {
                    thisinteract = 2;
                }
            }
            if (thisinteract > 0)
            {
                if (thisinteract == 1)
                {
                    interactedobject = collision_rectangle(x + (3 * d), (y + sprite_height) - (5 * d), (x + sprite_width) - (5 * d), y + (5 * d), obj_interactable, false, true);
                }
                if (thisinteract == 2)
                {
                    interactedobject = collision_rectangle(x + (3 * d), (y + sprite_height) - (5 * d), (x + sprite_width) - (5 * d), y + (5 * d), obj_interactablesolid, false, true);
                }
                if (interactedobject != -4)
                {
                    with (interactedobject)
                    {
                        facing = 0;
                    }
                    with (interactedobject)
                    {
                        scr_interact();
                    }
                }
            }
        }
```

## D. `global.interact` 全局闸 与 输入缓冲（I4/I5）
`obj_mainchara_Step_0` 起始行 17：
```gml
if (global.interact == 0)
{
    if (button3_p() && threebuffer < 0)
    {
        if (global.flag[7] == 0 && battlemode == 0)
        {
            with (obj_darkcontroller)
            {
                threebuffer = 2;
            }
            with (obj_overworldc)
            {
                movenoise = 1;
                threebuffer = 2;
            }
            global.menuno = 0;
            global.interact = 5;
            threebuffer = 2;
            twobuffer = 2;
        }
    }
    if (global.flag[11] == 1)
    {
        if (button2_h() && twobuffer < 0)
        {
            run = 0;
        }
        else
        {
            run = 1;
        }
    }
    else if (button2_h() && twobuffer < 0)
    {
        run = 1;
    }
    else
    {
        run = 0;
    }
    if (autorun > 0)
    {
        if (autorun == 1)
        {
            run = 1;
            runtimer = 200;
        }
        if (autorun == 2)
        {
            run = 1;
            runtimer = 50;
        }
    }
    if (run == 1)
    {
        if (darkmode == 0)
        {
            wspeed = bwspeed + 1;
            if (runtimer > 10)
            {
                wspeed = bwspeed + 2;
            }
            if (runtimer > 60)
            {
                wspeed = bwspeed + 3;
            }
        }
        if (darkmode == 1)
        {
            wspeed = bwspeed + 2;
            if (runtimer > 10)
            {
                wspeed = bwspeed + 4;
            }
            if (runtimer > 60)
            {
                wspeed = bwspeed + 5;
            }
        }
    }
    if (run == 0)
    {
        wspeed = bwspeed;
    }
    if (left_h())
    {
        press_l = 1;
    }
    if (right_h())
    {
        press_r = 1;
    }
    if (up_h())
    {
        press_u = 1;
    }
    if (down_h())
    {
        press_d = 1;
    }
    px = 0;
    py = 0;
    pressdir = -1;
    if (press_r == 1)
    {
        px = wspeed;
        pressdir = 1;
    }
    if (press_l == 1)
    {
        px = -wspeed;
        pressdir = 3;
    }
    if (press_d == 1)
    {
        py = wspeed;
        pressdir = 0;
    }
    if (press_u == 1)
    {
        py = -wspeed;
        pressdir = 2;
    }
    if (nopress == 1 && pressdir != -1)
    {
        global.facing = pressdir;
    }
    if (global.facing == 2)
    {
        if (press_d == 1)
        {
            global.facing = 0;
        }
        if (press_u == 0 && pressdir != -1)
        {
            global.facing = pressdir;
        }
    }
    if (global.facing == 0)
    {
        if (press_u == 1)
        {
            global.facing = 2;
        }
        if (press_d == 0 && pressdir != -1)
        {
            global.facing = pressdir;
        }
    }
    if (global.facing == 3)
    {
        if (press_r == 1)
        {
            global.facing = 1;
        }
        if (press_l == 0 && pressdir != -1)
        {
            global.facing = pressdir;
        }
    }
    if (global.facing == 1)
    {
        if (press_l == 1)
        {
            global.facing = 3;
        }
        if (press_r == 0 && pressdir != -1)
        {
            global.facing = pressdir;
        }
    }
    nopress = 0;
    xmeet = 0;
    ymeet = 0;
    xymeet = 0;
    if (place_meeting(x + px, y, obj_solidblock))
    {
        for (var g = wspeed; g > 0; g -= 1)
        {
            var mvd = 0;
            if (press_d == 0 && !place_meeting(x + px, y - g, obj_solidblock))
            {
                y -= g;
                py = 0;
                break;
            }
            else
            {
                mvd = 1;
            }
            if (press_u == 0 && mvd == 0 && !place_meeting(x + px, y + g, obj_solidblock))
            {
                y += g;
                py = 0;
                break;
            }
        }
        xmeet = 1;
        bkx = 0;
        if (px > 0)
```
`*buffer` 变量在本 code 里的每次出现：
```gml
  19 |     if (button3_p() && threebuffer < 0)
  25 |                 threebuffer = 2;
  30 |                 threebuffer = 2;
  34 |             threebuffer = 2;
  35 |             twobuffer = 2;
  40 |         if (button2_h() && twobuffer < 0)
  49 |     else if (button2_h() && twobuffer < 0)
 381 |     walkbuffer = 6;
 383 | if (walkbuffer > 3 && fun == 0)
 411 | else if (walkbuffer <= 0 && fun == 0)
 431 | walkbuffer -= 0.75;
 474 | if (onebuffer < 0)
 620 | onebuffer -= 1;
 621 | twobuffer -= 1;
 622 | threebuffer -= 1;
```

## E. 被交互者 `obj_interactablesolid` 的 `myinteract` 三态 + `onebuffer`
来源：`gml_Object_obj_interactablesolid_Step_0`（213 chars）
```gml
if (myinteract == 3)
{
    if (instance_exists(mydialoguer) == false)
    {
        global.interact = 0;
        myinteract = 0;
        with (obj_mainchara)
        {
            onebuffer = 5;
        }
    }
}

```
来源：`gml_Object_obj_interactablesolid_Create_0`（46 chars）
```gml
myinteract = 0;
image_speed = 0;
scr_depth();

```
来源：`gml_Object_obj_interactablesolid_Other_10`（241 chars）
```gml
global.msg[0] = scr_84_get_lang_string("obj_interactablesolid_slash_Other_10_gml_2_0");
myinteract = 3;
global.msc = 0;
global.typer = 5;
global.fc = 0;
global.fc = 0;
global.interact = 1;
mydialoguer = instance_create(0, 0, obj_dialoguer);

```

本产物里名字含 `interactable` 的 code（3 条）—— ★ 先探名再引用：
- `gml_Object_obj_interactablesolid_Create_0`（46 chars）
- `gml_Object_obj_interactablesolid_Other_10`（241 chars）
- `gml_Object_obj_interactablesolid_Step_0`（213 chars）

## F. 剧情进度计数器 `global.plot`（I10 的唯一真源）
名字含 `plot` 的 code：无

全产物里 `global.plot` 被**比较**的每一处（5 处）：
```text
gml_Object_obj_doorX_Alarm_2 :   72 | if (global.plot < 120)
gml_Object_obj_doorX_Alarm_2 :   96 | if (global.plot < 150)
gml_Object_obj_doorX_Alarm_2 :  107 | if (global.plot < 150)
gml_Object_obj_mainchara_Step_2 :   26 | if (global.darkzone == 0 && global.plot >= 245)
gml_Object_obj_npc_susiedark_Create_0 :   12 | if (global.plot >= 30)
```

全局变量表里 `plot` 的登记：
```json
[
  {
    "name": "plot",
    "instance": "Local"
  },
  {
    "name": "plot",
    "instance": "Self"
  },
  {
    "name": "plot",
    "instance": "Global"
  }
]
```

同表里 `interact` / `darkzone` / `menuno` 的登记：
```json
[
  {
    "name": "darkzone",
    "instance": "Global"
  },
  {
    "name": "facing",
    "instance": "Self"
  },
  {
    "name": "facing",
    "instance": "Global"
  },
  {
    "name": "interact",
    "instance": "Global"
  },
  {
    "name": "menuno",
    "instance": "Global"
  },
  {
    "name": "sp",
    "instance": "Global"
  },
  {
    "name": "interact",
    "instance": "Self"
  }
]
```

## G. 回验（锚点 → 原 json `in`）
```text
[OK] bwspeed = 3;
[OK] bwspeed = 4;
[OK] wspeed = bwspeed + 1;
[OK] wspeed = bwspeed + 2;
[OK] wspeed = bwspeed + 3;
[OK] wspeed = bwspeed + 4;
[OK] wspeed = bwspeed + 5;
[OK] runtimer += 1;
[OK] if (runtimer > 10)
[OK] if (runtimer > 60)
[OK] runmove = 0;
[OK] global.interact == 0
[OK] button2_h()
[OK] button3_p()
[OK] global.plot
[OK] onebuffer
[OK] myinteract
```

回验结果：**17/17**
