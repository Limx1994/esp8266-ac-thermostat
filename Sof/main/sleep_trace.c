#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/soc.h"
#include "driver/rtc.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sleep_trace.h"
#include "noise_timer.h"

extern void __real_esp_sleep_start(void);
extern uint32_t __real_pm_rtc_clock_cali_proc(void);
extern uint32_t __real_rtc_light_sleep_start(uint32_t wakeup_opt, uint32_t reject_opt);
extern TickType_t __real_prvGetExpectedIdleTime(void);
extern void __real_pm_set_sleep_cycles(uint32_t rtc_cycles);
extern void __real_vTaskDelay(TickType_t ticks);
extern uint32_t __real_ulTaskNotifyTake(BaseType_t clear, TickType_t ticks);
extern BaseType_t __real_xQueueReceive(QueueHandle_t queue, void *buffer, TickType_t ticks);
extern void __real_vTaskPlaceOnEventList(List_t *list, TickType_t ticks);
extern void __real_vTaskPlaceOnEventListRestricted(List_t *list, TickType_t ticks, BaseType_t forever);

#define TRACE_FRC2_COUNT 0x60000624U
#define TRACE_FRC2_CTL 0x60000628U
#define TRACE_FRC2_ALARM 0x60000630U
#define TRACE_RECENT 4U
#define TRACE_WAIT_SLOTS 16U

enum { WAIT_DELAY, WAIT_NOTIFY, WAIT_QUEUE, WAIT_EVENT, WAIT_TIMER };

typedef struct {
    TaskHandle_t task;
    uintptr_t caller, object;
    char name[configMAX_TASK_NAME_LEN];
    uint32_t kind, calls, half_second, min_ticks, max_ticks, last_ticks, last_at;
} wait_sample_t;

static volatile wait_sample_t wait_rows[TRACE_WAIT_SLOTS];
static wait_sample_t wait_snapshot[TRACE_WAIT_SLOTS];
static uint64_t wait_zero, wait_long, wait_full;

/* 只记录有限的 1 秒内等待；不分配内存、不输出日志、不触碰等待对象。
 * event/timer 代表进入等待列表，其余代表 API 调用意图，不证明超时返回。
 */
static void record_wait(TickType_t ticks, unsigned kind, uintptr_t caller,
                        uintptr_t object, bool forever)
{
    esp_irqflag_t flags = soc_save_local_irq();
    if (forever || ticks == portMAX_DELAY) wait_long++;
    else if (!ticks) wait_zero++;
    else if (ticks > pdMS_TO_TICKS(1000)) wait_long++;
    else {
        TaskHandle_t task = xTaskGetCurrentTaskHandle();
        unsigned slot = TRACE_WAIT_SLOTS, empty = TRACE_WAIT_SLOTS;
        for (unsigned i = 0; i < TRACE_WAIT_SLOTS; i++) {
            if (!wait_rows[i].calls) { if (empty == TRACE_WAIT_SLOTS) empty = i; }
            else if (wait_rows[i].task == task && wait_rows[i].kind == kind &&
                     wait_rows[i].caller == caller && wait_rows[i].object == object) {
                slot = i;
                break;
            }
        }
        if (slot == TRACE_WAIT_SLOTS) slot = empty;
        if (slot == TRACE_WAIT_SLOTS) wait_full++;
        else {
            volatile wait_sample_t *row = &wait_rows[slot];
            if (!row->calls) {
                row->task = task;
                row->kind = kind;
                row->caller = caller;
                row->object = object;
                row->min_ticks = row->max_ticks = ticks;
                row->half_second = 0;
                const char *name = pcTaskGetName(task);
                unsigned i = 0;
                if (name) {
                    for (; i + 1 < sizeof(row->name) && name[i]; i++) row->name[i] = name[i];
                }
                row->name[i] = '\0';
            }
            row->calls++;
            if (ticks == pdMS_TO_TICKS(500)) row->half_second++;
            if (ticks < row->min_ticks) row->min_ticks = ticks;
            if (ticks > row->max_ticks) row->max_ticks = ticks;
            row->last_ticks = ticks;
            row->last_at = xTaskGetTickCount();
        }
    }
    soc_restore_local_irq(flags);
}

void __wrap_vTaskDelay(TickType_t ticks)
{
    record_wait(ticks, WAIT_DELAY, (uintptr_t)__builtin_return_address(0), 0, false);
    __real_vTaskDelay(ticks);
}

uint32_t __wrap_ulTaskNotifyTake(BaseType_t clear, TickType_t ticks)
{
    record_wait(ticks, WAIT_NOTIFY, (uintptr_t)__builtin_return_address(0), 0, false);
    return __real_ulTaskNotifyTake(clear, ticks);
}

BaseType_t __wrap_xQueueReceive(QueueHandle_t queue, void *buffer, TickType_t ticks)
{
    record_wait(ticks, WAIT_QUEUE, (uintptr_t)__builtin_return_address(0), (uintptr_t)queue, false);
    return __real_xQueueReceive(queue, buffer, ticks);
}

void __wrap_vTaskPlaceOnEventList(List_t *list, TickType_t ticks)
{
    record_wait(ticks, WAIT_EVENT, (uintptr_t)__builtin_return_address(0), (uintptr_t)list, false);
    __real_vTaskPlaceOnEventList(list, ticks);
}

void __wrap_vTaskPlaceOnEventListRestricted(List_t *list, TickType_t ticks, BaseType_t forever)
{
    record_wait(ticks, WAIT_TIMER, (uintptr_t)__builtin_return_address(0), (uintptr_t)list, forever != pdFALSE);
    __real_vTaskPlaceOnEventListRestricted(list, ticks, forever);
}

typedef struct {
    uint64_t seq;
    uint32_t idle_ticks, os_us, frc_us, programmed, period, elapsed_ticks;
    uint32_t result, wakeup_opt;
    bool deadline_valid, frc_enabled, frc_pending, program_valid;
} sleep_sample_t;

typedef struct {
    uint64_t auto_calls, auto_no_hw;
    uint64_t hw_calls, hw_ok, hw_reject;
    uint64_t bad_cal, zero_rtc;
    uint64_t rtc_units, max_rtc_units; /* 1/4096 微秒，按每次校准值加权。 */
    uint32_t last_reject;
    uint64_t measured, min_units_win, max_units_win;
    uint64_t os_limits, frc_limits, equal_limits, unknown_limits;
} sleep_stats_t;

static volatile sleep_stats_t totals;
static volatile uint32_t cal_period;
static sleep_stats_t previous;
static int64_t report_at;
static volatile sleep_sample_t pending;
static volatile sleep_sample_t recent[TRACE_RECENT];
static unsigned recent_next;

/* 只观察 SDK 返回值和当前期限，不修改调度结果。
 * 读寄存器晚于 SDK 的 save_soc_clk，期限是相邻时刻估算，不是精确原值。
 */
TickType_t IRAM_ATTR __wrap_prvGetExpectedIdleTime(void)
{
    TickType_t ticks = __real_prvGetExpectedIdleTime();
    esp_irqflag_t flags = soc_save_local_irq();
    uint32_t ccount = soc_get_ccount();
    uint32_t ticks_per_us = g_esp_ticks_per_us;
    pending.idle_ticks = ticks;
    pending.deadline_valid = ticks_per_us != 0;
    if (ticks_per_us) {
        int32_t delta = (int32_t)(soc_get_ccompare() - ccount);
        int64_t us = delta / (int32_t)ticks_per_us +
            (int64_t)(ticks ? ticks - 1 : 0) * portTICK_PERIOD_MS * 1000;
        pending.os_us = us <= 0 ? 0 : us > UINT32_MAX ? UINT32_MAX : (uint32_t)us;
    }
    pending.frc_enabled = (REG_READ(TRACE_FRC2_CTL) & (1U << 7)) != 0;
    pending.frc_pending = pending.frc_enabled;
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    pending.frc_pending = pending.frc_pending && app_os_timer_pending();
#endif
    pending.frc_us = 0;
    if (pending.frc_pending) {
        uint32_t delta = REG_READ(TRACE_FRC2_ALARM) - REG_READ(TRACE_FRC2_COUNT);
        pending.frc_us = delta < UINT32_MAX / 4U ? delta / 5U : 0;
    }
    soc_restore_local_irq(flags);
    return ticks;
}

void IRAM_ATTR __wrap_pm_set_sleep_cycles(uint32_t rtc_cycles)
{
    esp_irqflag_t flags = soc_save_local_irq();
    pending.programmed = rtc_cycles;
    pending.program_valid = true;
    soc_restore_local_irq(flags);
    __real_pm_set_sleep_cycles(rtc_cycles);
}

/* 不持有额外休眠锁，也不在入口输出日志；保存并恢复调用方的中断状态。 */
void IRAM_ATTR __wrap_esp_sleep_start(void)
{
    esp_irqflag_t flags = soc_save_local_irq();
    totals.auto_calls++;
    uint64_t before = totals.hw_calls;
    cal_period = 0;
    pending.deadline_valid = false;
    pending.program_valid = false;
    pending.idle_ticks = pending.os_us = pending.frc_us = 0;
    pending.frc_enabled = false;
    pending.frc_pending = false;
    soc_restore_local_irq(flags);

    __real_esp_sleep_start();

    flags = soc_save_local_irq();
    if (totals.hw_calls == before) totals.auto_no_hw++;
    soc_restore_local_irq(flags);
}

/* 复用 SDK 本次休眠已有的校准，不增加一次 RTC 校准。 */
uint32_t IRAM_ATTR __wrap_pm_rtc_clock_cali_proc(void)
{
    uint32_t period = __real_pm_rtc_clock_cali_proc();
    esp_irqflag_t flags = soc_save_local_irq();
    cal_period = period;
    soc_restore_local_irq(flags);
    return period;
}

uint32_t IRAM_ATTR __wrap_rtc_light_sleep_start(uint32_t wakeup_opt, uint32_t reject_opt)
{
    esp_irqflag_t flags = soc_save_local_irq();
    uint32_t period = cal_period;
    cal_period = 0; /* 一次校准只用于随后的低层调用，避免重复使用旧值。 */
    totals.hw_calls++;
    sleep_sample_t sample = pending;
    sample.seq = totals.hw_calls;
    sample.period = period;
    sample.wakeup_opt = wakeup_opt;
    pending.deadline_valid = false;
    pending.program_valid = false;
    soc_restore_local_irq(flags);

    uint32_t before = REG_READ(RTC_SLP_CNT_VAL);
    uint32_t result = __real_rtc_light_sleep_start(wakeup_opt, reject_opt);
    uint32_t ticks = REG_READ(RTC_SLP_CNT_VAL) - before;

    flags = soc_save_local_irq();
    sample.elapsed_ticks = ticks;
    sample.result = result;
    recent[recent_next] = sample;
    recent_next = (recent_next + 1U) % TRACE_RECENT;
    if (!sample.deadline_valid) totals.unknown_limits++;
    else if (!sample.frc_pending || sample.os_us < sample.frc_us) totals.os_limits++;
    else if (sample.os_us > sample.frc_us) totals.frc_limits++;
    else totals.equal_limits++;
    if (result) {
        totals.hw_reject++;
        totals.last_reject = result;
    } else {
        totals.hw_ok++; /* 仅表示硬件未报告拒绝，不证明完整睡眠时长。 */
        if (!period) totals.bad_cal++;
        else if (!ticks) totals.zero_rtc++;
        else {
            uint64_t units = (uint64_t)ticks * period;
            totals.rtc_units += units;
            totals.measured++;
            if (!totals.min_units_win || units < totals.min_units_win) totals.min_units_win = units;
            if (units > totals.max_units_win) totals.max_units_win = units;
            if (units > totals.max_rtc_units) totals.max_rtc_units = units;
        }
    }
    soc_restore_local_irq(flags);
    return result;
}

/* nano printf 不支持 %llu；汇总阶段转换为十进制，保留全部 64 位。 */
static const char *trace_number(char buffer[21], uint64_t value)
{
    char *next = buffer + 20;
    *next = '\0';
    do {
        *--next = '0' + value % 10U;
        value /= 10U;
    } while (value);
    return next;
}

void sleep_trace_report(void)
{
    int64_t now = esp_timer_get_time();
    if (now - report_at < 30000000) return;

    esp_irqflag_t flags = soc_save_local_irq();
    sleep_stats_t snapshot = totals;
    sleep_sample_t samples[TRACE_RECENT];
    unsigned next = recent_next;
    for (unsigned i = 0; i < TRACE_RECENT; i++) samples[i] = recent[i];
    for (unsigned i = 0; i < TRACE_WAIT_SLOTS; i++) {
        wait_snapshot[i] = wait_rows[i];
        wait_rows[i].calls = 0;
    }
    uint64_t zero = wait_zero, long_waits = wait_long, full = wait_full;
    wait_zero = wait_long = wait_full = 0;
    totals.min_units_win = totals.max_units_win = 0;
    soc_restore_local_irq(flags);

    char numbers[6][21];
    ESP_LOGI("sleep_trace", "window_ms=%s auto=%s auto_no_hw=%s hw=%s hw_ok=%s hw_reject=%s",
             trace_number(numbers[0], (now - report_at) / 1000),
             trace_number(numbers[1], snapshot.auto_calls - previous.auto_calls),
             trace_number(numbers[2], snapshot.auto_no_hw - previous.auto_no_hw),
             trace_number(numbers[3], snapshot.hw_calls - previous.hw_calls),
             trace_number(numbers[4], snapshot.hw_ok - previous.hw_ok),
             trace_number(numbers[5], snapshot.hw_reject - previous.hw_reject));
    ESP_LOGI("sleep_trace", "rtc_call_est_ms=%s max_est_ms_total=%s bad_cal=%s zero_rtc=%s last_reject=0x%08x reasons=unavailable",
             trace_number(numbers[0], (snapshot.rtc_units - previous.rtc_units) / 4096000U),
             trace_number(numbers[1], snapshot.max_rtc_units / 4096000U),
             trace_number(numbers[2], snapshot.bad_cal - previous.bad_cal),
             trace_number(numbers[3], snapshot.zero_rtc - previous.zero_rtc),
             (unsigned)snapshot.last_reject);
    uint64_t count = snapshot.measured - previous.measured;
    uint64_t units = snapshot.rtc_units - previous.rtc_units;
    ESP_LOGI("sleep_trace", "rtc_window: measured=%s avg_est_us=%s min_est_us=%s max_est_us=%s",
             trace_number(numbers[0], count),
             trace_number(numbers[1], count ? units / count / 4096U : 0),
             trace_number(numbers[2], snapshot.min_units_win / 4096U),
             trace_number(numbers[3], snapshot.max_units_win / 4096U));
    ESP_LOGI("sleep_trace", "deadline_snapshot: os=%s frc2=%s equal=%s unknown=%s (estimates; not wake reasons)",
             trace_number(numbers[0], snapshot.os_limits - previous.os_limits),
             trace_number(numbers[1], snapshot.frc_limits - previous.frc_limits),
             trace_number(numbers[2], snapshot.equal_limits - previous.equal_limits),
             trace_number(numbers[3], snapshot.unknown_limits - previous.unknown_limits));
    for (unsigned i = 0; i < TRACE_RECENT; i++) {
        const sleep_sample_t *s = &samples[(next + i) % TRACE_RECENT];
        if (!s->seq || s->seq <= previous.hw_calls) continue;
        ESP_LOGI("sleep_trace", "recent: seq=%s idle_ticks=%u os_est_us=%u frc2_enabled=%d frc2_est_us=%u deadline_valid=%d frc2_pending=%d",
                 trace_number(numbers[0], s->seq), (unsigned)s->idle_ticks,
                 (unsigned)s->os_us, s->frc_enabled, (unsigned)s->frc_us, s->deadline_valid, s->frc_pending);
        ESP_LOGI("sleep_trace", "recent_rtc: programmed_valid=%d requested_est_us=%s rtc_ticks=%u period_q12=%u elapsed_est_us=%s result=0x%08x wake_mask=0x%08x",
                 s->program_valid,
                 trace_number(numbers[0], s->program_valid ? (uint64_t)s->programmed * s->period / 4096U : 0),
                 (unsigned)s->elapsed_ticks, (unsigned)s->period,
                 trace_number(numbers[1], (uint64_t)s->elapsed_ticks * s->period / 4096U),
                 (unsigned)s->result, (unsigned)s->wakeup_opt);
    }
    ESP_LOGI("sleep_trace", "wait_trace: filtered_zero=%s filtered_long_or_infinite=%s dropped_full=%s capacity=%u (scheduled waits; not proven timeouts)",
             trace_number(numbers[0], zero), trace_number(numbers[1], long_waits),
             trace_number(numbers[2], full), TRACE_WAIT_SLOTS);
    static const char *const wait_names[] = { "delay", "notify", "queue_call", "event_list", "timer_list" };
    for (unsigned i = 0; i < TRACE_WAIT_SLOTS; i++) {
        const wait_sample_t *row = &wait_snapshot[i];
        if (!row->calls) continue;
        ESP_LOGI("sleep_trace", "wait_task: task=%s api=%s calls=%u ticks_500ms=%u min_ticks=%u max_ticks=%u last_ticks=%u at_tick=%u caller=0x%08x object=0x%08x",
                 row->name[0] ? row->name : "unavailable", wait_names[row->kind],
                 (unsigned)row->calls, (unsigned)row->half_second,
                 (unsigned)row->min_ticks, (unsigned)row->max_ticks,
                 (unsigned)row->last_ticks, (unsigned)row->last_at,
                 (unsigned)row->caller, (unsigned)row->object);
    }
    previous = snapshot;
    report_at = now;
}
