event_inherited();
if (interact)
{
    scr_text();
    is_talking = 1;
    with (msg)
    {
        sndfnt_array[0] = 391;
        message[0] = "*  （ 门 从 另 一 侧 锁 起 来 了 。）";
        if (other.npc_flag == 0 && global.party_member != -4)
        {
            sndfnt_array[1] = 102;
            message[1] = "*  锁 着 ，嗯 ? 奇 了 怪 了 . . .";
            message[2] = "*  那 我 想 艾 德 和 星 达#     应 该 是 走 了 别 的 路 。";
            prt[1] = 311;
            prt[2] = 324;
        }
    }
    npc_flag = 1;
}
