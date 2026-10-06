#include <stdint.h>
#include <stddef.h>
#include "noise_timer.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "driver/soc.h"
#include "rom/ets_sys.h"

#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
/* Link-time aliases in build-local copies of the original SDK objects. */
extern os_timer_t * volatile app_ets_timer_head;
extern os_timer_t app_noise_timer;
extern uint16_t NoiseTimerInterval;
extern void pp_noise_test(void *arg);
extern void pp_disable_noise_timer(void);
extern void reset_noise_timer(uint16_t interval);
extern void __real_os_timer_arm(os_timer_t *timer, uint32_t ms, bool repeat);
extern void __real_os_timer_arm_us(os_timer_t *timer, uint32_t us, bool repeat);

static volatile bool noise_paused;
static volatile uint32_t blocked_arms;

static bool block_noise_arm(os_timer_t *timer)
{
    esp_irqflag_t flags = soc_save_local_irq();
    bool blocked = noise_paused && timer == &app_noise_timer;
    if (blocked) blocked_arms++;
    soc_restore_local_irq(flags);
    return blocked;
}

void __wrap_os_timer_arm(os_timer_t *timer, uint32_t ms, bool repeat)
{
    if (block_noise_arm(timer)) return;
    __real_os_timer_arm(timer, ms, repeat);
}

void __wrap_os_timer_arm_us(os_timer_t *timer, uint32_t us, bool repeat)
{
    if (block_noise_arm(timer)) return;
    __real_os_timer_arm_us(timer, us, repeat);
}
#endif

int IRAM_ATTR app_os_timer_pending(void)
{
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    return app_ets_timer_head != NULL;
#else
    return 1;
#endif
}

esp_err_t noise_timer_set_active(bool active)
{
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    if (app_noise_timer.timer_func != pp_noise_test || !NoiseTimerInterval) {
        ESP_LOGE("noise_timer", "SDK noise timer not initialized");
        return ESP_ERR_INVALID_STATE;
    }
    esp_irqflag_t flags = soc_save_local_irq();
    bool changed = noise_paused == active;
    noise_paused = !active;
    soc_restore_local_irq(flags);
    if (active) {
        if (changed) reset_noise_timer(NoiseTimerInterval);
    } else {
        /* Set the guard first: a pending callback cannot rearm after this. */
        pp_disable_noise_timer();
    }
    flags = soc_save_local_irq();
    bool found = false;
    os_timer_t *timer;
    for (timer = app_ets_timer_head; timer; timer = timer->timer_next) {
        if (timer == &app_noise_timer) found = true;
    }
    uint32_t blocked = blocked_arms;
    void *head_cb = app_ets_timer_head ? (void *)app_ets_timer_head->timer_func : NULL;
    soc_restore_local_irq(flags);
    if (found != active) {
        if (active) {
            flags = soc_save_local_irq();
            noise_paused = true;
            soc_restore_local_irq(flags);
            pp_disable_noise_timer();
        }
        ESP_LOGE("noise_timer", "noise timer %s verification failed", active ? "resume" : "pause");
        return ESP_FAIL;
    }
    if (changed) ESP_LOGI("noise_timer", "%s: interval_ms=%u os_pending=%u head_cb=%p blocked_arms=%u",
                         active ? "resumed" : "paused", (unsigned)NoiseTimerInterval,
                         (unsigned)app_os_timer_pending(), head_cb, (unsigned)blocked);
#else
    (void)active;
#endif
    return ESP_OK;
}
