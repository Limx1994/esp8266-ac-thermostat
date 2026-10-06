/* Called only from the TCP/IP thread; one-shot timeouts remain untouched. */
static int app_timer_queued(sys_timeout_handler handler, void *arg)
{
    struct sys_timeo *timer;
    for (timer = next_timeout; timer; timer = timer->next) {
        if (timer->h == handler && timer->arg == arg) return 1;
    }
    return 0;
}

err_t app_lwip_timers_set(int active, unsigned counts[3])
{
    size_t i;
    struct sys_timeo *timer;
    err_t err = ERR_OK;
    counts[0] = counts[1] = counts[2] = 0;
    LWIP_ASSERT_CORE_LOCKED();
    if (active && app_timers_paused) {
        app_timers_paused = 0;
        sys_timeouts_init();
        for (i = (LWIP_TCP ? 1 : 0); i < LWIP_ARRAYSIZE(lwip_cyclic_timers); i++) {
            if (!app_timer_queued(lwip_cyclic_timer, (void *)&lwip_cyclic_timers[i])) {
                err = ERR_MEM;
                break;
            }
            counts[0]++;
        }
#if LWIP_TCP
        tcp_timer_needed();
        counts[1] = app_timer_queued(tcpip_tcp_timer, NULL);
        if ((tcp_active_pcbs || tcp_tw_pcbs) && !counts[1]) err = ERR_MEM;
#endif
        /* A partial restore must not leave a partially active timer group. */
        if (err != ERR_OK) {
            unsigned rollback[3];
            app_lwip_timers_set(0, rollback);
            counts[0] = counts[1] = 0;
        }
    } else if (!active && !app_timers_paused) {
        app_timers_paused = 1;
        for (i = (LWIP_TCP ? 1 : 0); i < LWIP_ARRAYSIZE(lwip_cyclic_timers); i++) {
            void *arg = (void *)&lwip_cyclic_timers[i];
            counts[0] += app_timer_queued(lwip_cyclic_timer, arg);
            sys_untimeout(lwip_cyclic_timer, arg);
        }
#if LWIP_TCP
        counts[1] = app_timer_queued(tcpip_tcp_timer, NULL);
        sys_untimeout(tcpip_tcp_timer, NULL);
        tcpip_tcp_timer_active = 0;
#endif
    }
    for (timer = next_timeout; timer; timer = timer->next) counts[2]++;
    return err;
}
