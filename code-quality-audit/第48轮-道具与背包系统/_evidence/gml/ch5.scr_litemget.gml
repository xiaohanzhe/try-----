function scr_litemget(arg0)
{
    i = 0;
    loop = 0;
    noroom = 1;
    global.litem[8] = 999;
    for (i = 0; i < 8; i++)
    {
        if (global.litem[i] == 0)
        {
            global.litem[i] = arg0;
            noroom = 0;
            break;
        }
    }
    scr_litemname();
}
