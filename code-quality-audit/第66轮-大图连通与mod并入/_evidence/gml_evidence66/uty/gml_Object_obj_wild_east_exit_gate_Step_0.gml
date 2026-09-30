if (global.dunes_flag[20] < 9 && scr_interact() && keyboard_multicheck_pressed(0))
{
    scr_text();
    with (msg)
    {
        message[0] = "*  （ 一 个 巨 大 的 锁 拦 住 了 你 的 去 路 。）";
        message[1] = "*  （ 有 点 夸 张 了 。）";
    }
}
