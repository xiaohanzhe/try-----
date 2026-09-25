function scr_keyitemget(arg0)
{
    i = 0;
    loop = 0;
    noroom = 1;
    global.item[12] = 999;
    for (i = 0; i < 12; i++)
    {
        if (global.keyitem[i] == 0)
        {
            global.keyitem[i] = arg0;
            noroom = 0;
            break;
        }
    }
    script_execute(scr_keyiteminfo_all);
}
