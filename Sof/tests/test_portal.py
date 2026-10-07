r"""Run actual portal and URI dispatch code against host SDK mocks.

Run: python tests\test_portal.py. Outputs stay in build_ascii\portal_test.
This checks HTTP dispatch and idle accounting, not Android's login UI.
"""

import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "portal_test"
SDK_PATH = Path(os.environ.get("IDF_PATH") or
                r"D:\APPS\Espressif\frameworks\ESP8266_RTOS_SDK")
HEADERS = ["esp_err.h", "esp_log.h", "esp_event.h", "esp_wifi.h", "driver/rtc.h",
           "tcpip_adapter.h", "esp_http_server.h", "esp_httpd_priv.h",
           "freertos/FreeRTOS.h", "freertos/task.h", "lwip/sockets.h", "lwip/tcpip.h",
           "lwip/sys.h", "osal.h"]

# 用主机 mock 承接实际 portal 和 HTTP 覆盖代码，验证协议及资源生命周期。
SDK = r'''
#pragma once
#include <winsock2.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <http_parser.h>
#include <errno.h>
#include <stdarg.h>
typedef int esp_err_t;
typedef uint32_t TickType_t;
typedef int err_t;
enum { ERR_OK = 0, ERR_MEM = -1, ERR_VAL = -6 };
typedef struct { bool signaled; } sys_sem_t;
err_t sys_sem_new(sys_sem_t *sem, uint8_t count);
void sys_sem_signal(sys_sem_t *sem);
void sys_sem_wait(sys_sem_t *sem);
void sys_sem_free(sys_sem_t *sem);
err_t tcpip_callback(void (*fn)(void *), void *arg);
typedef void *httpd_handle_t;
typedef enum http_method httpd_method_t;
typedef int httpd_err_resp_t;
enum { ESP_OK, ESP_FAIL, ESP_ERR_INVALID_ARG, ESP_ERR_NO_MEM,
       ESP_ERR_NOT_FOUND, ESP_ERR_INVALID_STATE, ESP_ERR_TIMEOUT,
       ESP_ERR_HTTPD_HANDLER_EXISTS, ESP_ERR_HTTPD_ALLOC_MEM,
       ESP_ERR_HTTPD_HANDLERS_FULL, ESP_ERR_HTTPD_INVALID_REQ,
       ESP_ERR_HTTPD_RESP_HDR, ESP_ERR_HTTPD_RESP_SEND, ESP_ERR_HTTPD_RESULT_TRUNC };
enum { HTTPD_500_SERVER_ERROR=500, HTTPD_501_METHOD_NOT_IMPLEMENTED=501,
       HTTPD_505_VERSION_NOT_SUPPORTED=505, HTTPD_400_BAD_REQUEST=400,
       HTTPD_404_NOT_FOUND=404, HTTPD_405_METHOD_NOT_ALLOWED=405,
       HTTPD_408_REQ_TIMEOUT=408, HTTPD_411_LENGTH_REQUIRED=411,
       HTTPD_414_URI_TOO_LONG=414, HTTPD_431_REQ_HDR_FIELDS_TOO_LARGE=431,
       HTTPD_XXX_UPGRADE_NOT_SUPPORTED=200 };
enum { HTTPD_SOCK_ERR_FAIL=-1, HTTPD_SOCK_ERR_INVALID=-2, HTTPD_SOCK_ERR_TIMEOUT=-3 };
#define HTTPD_MAX_URI_LEN 1024
#define HTTPD_MAX_REQ_HDR_LEN 2048
#define HTTPD_SCRATCH_BUF 2048
#define PARSER_BLOCK_SIZE 128
#define HTTPD_200 "200 OK"
#define HTTPD_TYPE_TEXT "text/html"
#define MIN(a, b) ((a) < (b) ? (a) : (b))
typedef void (*httpd_free_ctx_fn_t)(void *);
typedef int (*httpd_send_func_t)(httpd_handle_t, int, const char *, size_t, int);
typedef int (*httpd_recv_func_t)(httpd_handle_t, int, char *, size_t, int);
typedef int (*httpd_pending_func_t)(httpd_handle_t, int);
typedef struct {
    uint16_t max_uri_handlers, max_open_sockets, max_resp_headers;
    bool lru_purge_enable;
} httpd_config_t;
typedef struct httpd_req {
    httpd_handle_t handle;
    int method;
    char uri[HTTPD_MAX_URI_LEN + 1];
    size_t content_len;
    void *aux, *user_ctx;
    void *sess_ctx;
    httpd_free_ctx_fn_t free_ctx;
} httpd_req_t;
typedef struct {
    const char *uri;
    httpd_method_t method;
    esp_err_t (*handler)(httpd_req_t *);
    void *user_ctx;
} httpd_uri_t;
struct sock_db {
    int fd;
    void *ctx;
    httpd_handle_t handle;
    httpd_free_ctx_fn_t free_ctx;
    httpd_send_func_t send_fn;
    httpd_recv_func_t recv_fn;
    httpd_pending_func_t pending_fn;
    char pending_data[PARSER_BLOCK_SIZE];
    size_t pending_len;
};
struct httpd_req_aux {
    struct sock_db *sd;
    char scratch[HTTPD_SCRATCH_BUF + 1];
    size_t remaining_len;
    char *status, *content_type;
    bool first_chunk_sent;
    unsigned req_hdrs_count, resp_hdrs_count;
    struct resp_hdr { const char *field, *value; } *resp_hdrs;
    struct http_parser_url url_parse_res;
};
struct httpd_data {
    httpd_config_t config;
    httpd_uri_t **hd_calls;
    httpd_req_t hd_req;
    struct httpd_req_aux hd_req_aux;
    struct { void *handle; } hd_td;
};
typedef struct { int unused; } wifi_init_config_t;
typedef struct {
    struct { char ssid[32]; int ssid_len, authmode, max_connection; } ap;
} wifi_config_t;
enum { WIFI_STORAGE_RAM, WIFI_MODE_AP, WIFI_AUTH_OPEN, ESP_IF_WIFI_AP };
#define WIFI_INIT_CONFIG_DEFAULT() {0}
#define HTTPD_DEFAULT_CONFIG() { .max_uri_handlers=8 }
#define pdPASS 1
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define portTICK_PERIOD_MS 1
#define LOG_FMT(x) "%s: " x, __func__
#define ESP_LOGI(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGE(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) test_warn(tag, __VA_ARGS__)
void test_log(const char *, const char *, ...);
void test_warn(const char *, const char *, ...);
TickType_t xTaskGetTickCount(void);
void vTaskDelete(void *);
void vTaskDelay(TickType_t);
int xTaskCreate(void (*)(void *), const char *, unsigned, void *, unsigned, void *);
const char *esp_err_to_name(esp_err_t);
esp_err_t httpd_start(httpd_handle_t *, const httpd_config_t *);
esp_err_t httpd_stop(httpd_handle_t);
esp_err_t httpd_resp_set_status(httpd_req_t *, const char *);
esp_err_t httpd_resp_set_type(httpd_req_t *, const char *);
esp_err_t httpd_resp_set_hdr(httpd_req_t *, const char *, const char *);
esp_err_t httpd_resp_send(httpd_req_t *, const char *, ssize_t);
esp_err_t httpd_resp_send_err(httpd_req_t *, httpd_err_resp_t);
int httpd_req_recv(httpd_req_t *, char *, size_t);
esp_err_t httpd_register_uri_handler(httpd_handle_t, const httpd_uri_t *);
bool httpd_validate_req_ptr(httpd_req_t *);
#define httpd_valid_req(req) httpd_validate_req_ptr(req)
void *httpd_os_thread_handle(void);
struct sock_db *httpd_sess_get(httpd_handle_t, int);
void httpd_sess_free_ctx(void *, httpd_free_ctx_fn_t);
size_t strlcpy(char *, const char *, size_t);
size_t httpd_unrecv(httpd_req_t *, const char *, size_t);
int httpd_recv_with_opt(httpd_req_t *, char *, size_t, bool);
esp_err_t httpd_uri(struct httpd_data *);
void tcpip_adapter_init(void);
esp_err_t esp_event_loop_create_default(void);
esp_err_t esp_wifi_init(const wifi_init_config_t *);
esp_err_t esp_wifi_set_storage(int);
esp_err_t esp_wifi_set_mode(int);
esp_err_t esp_wifi_set_config(int, const wifi_config_t *);
esp_err_t esp_wifi_start(void);
esp_err_t esp_wifi_stop(void);
void phy_open_rf(void);
void phy_close_rf(void);
#define socket test_socket
#define bind test_bind
#define close test_close
#define setsockopt test_setsockopt
#define recvfrom test_recvfrom
#define sendto test_sendto
#define htons test_htons
typedef int socklen_t;
int test_socket(int, int, int);
int test_bind(int, const struct sockaddr *, size_t);
int test_close(int);
int test_setsockopt(int, int, int, const void *, size_t);
int test_recvfrom(int, void *, size_t, int, struct sockaddr *, socklen_t *);
int test_sendto(int, const void *, size_t, int, const struct sockaddr *, socklen_t);
uint16_t test_htons(uint16_t);
#define send test_io_send
#define recv test_io_recv
#define getsockopt test_io_sockopt
int test_io_send(int, const char *, size_t, int);
int test_io_recv(int, char *, size_t, int);
int test_io_sockopt(int, int, int, void *, size_t *);
'''

TEST = r'''
#define TAG httpd_tag
#include "../../components/esp_http_server/httpd_uri.c"
#undef TAG
#include "../../main/portal.c"

static struct httpd_data hd;
static TickType_t now;
static int warnings, response_code, response_calls, fail_call;
static char location[80];
static char status_body[640];
static bool battery_valid = true;
static size_t response_len;
static void (*dns_fn)(void *);
static bool socket_failed;
static bool rf_enabled = true, wifi_started;
static bool start_failed, stop_failed, http_failed;
static int rf_opens, rf_closes;
static bool timers_active = true, core_owned, sem_failed, callback_failed;
static err_t timer_failed;
static unsigned sem_created, sem_freed;
static bool noise_active = true, noise_failed;

esp_err_t noise_timer_set_active(bool active) {
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    if (!active) assert(!rf_enabled && !wifi_started);
    if (noise_failed) return ESP_FAIL;
    noise_active = active;
#else
    (void)active;
#endif
    return ESP_OK;
}

err_t sys_sem_new(sys_sem_t *sem, uint8_t count) {
    assert(count == 0);
    if (sem_failed) return ERR_MEM;
    sem->signaled = false; sem_created++; return ERR_OK;
}
void sys_sem_signal(sys_sem_t *sem) { assert(core_owned); sem->signaled = true; }
void sys_sem_wait(sys_sem_t *sem) { assert(!core_owned && sem->signaled); }
void sys_sem_free(sys_sem_t *sem) { sem_freed++; }
err_t tcpip_callback(void (*fn)(void *), void *arg) {
    if (callback_failed) return ERR_MEM;
    assert(!core_owned); core_owned = true; fn(arg); core_owned = false; return ERR_OK;
}
err_t app_lwip_timers_set(int active, unsigned counts[3]) {
    assert(core_owned);
    if (!active) assert(!rf_enabled && !wifi_started);
    if (timer_failed) return timer_failed;
    counts[0] = active != timers_active ? 4 : 0;
    counts[1] = 0; counts[2] = active ? 4 : 0;
    timers_active = active; return ERR_OK;
}

void test_log(const char *tag, const char *fmt, ...) {}
void test_warn(const char *tag, const char *fmt, ...) { warnings++; }
TickType_t xTaskGetTickCount(void) { return now; }
void vTaskDelete(void *task) {}
void vTaskDelay(TickType_t ticks) {
    now += ticks;
    if (dns_fn) { dns_fn(NULL); dns_fn = NULL; }
}
int xTaskCreate(void (*fn)(void *), const char *name, unsigned stack,
                void *arg, unsigned priority, void *task) {
    dns_fn = fn;
    return pdPASS;
}
const char *esp_err_to_name(esp_err_t err) { return "mock error"; }
esp_err_t httpd_start(httpd_handle_t *handle, const httpd_config_t *cfg) {
    if (http_failed) return ESP_FAIL;
    memset(&hd, 0, sizeof(hd));
    hd.config = *cfg;
    hd.hd_calls = calloc(cfg->max_uri_handlers, sizeof(*hd.hd_calls));
    assert(hd.hd_calls);
    *handle = &hd;
    return ESP_OK;
}
esp_err_t httpd_stop(httpd_handle_t handle) {
    assert(handle == &hd);
    httpd_unregister_all_uri_handlers(&hd);
    free(hd.hd_calls);
    hd.hd_calls = NULL;
    return ESP_OK;
}
static esp_err_t response_step(void) {
    response_calls++;
    return response_calls == fail_call ? ESP_FAIL : ESP_OK;
}
esp_err_t httpd_resp_set_status(httpd_req_t *req, const char *status) {
    response_code = atoi(status);
    return response_step();
}
esp_err_t httpd_resp_set_type(httpd_req_t *req, const char *type) {
    return response_step();
}
esp_err_t httpd_resp_set_hdr(httpd_req_t *req, const char *name, const char *value) {
    assert(strcmp(name, "Location") == 0);
    snprintf(location, sizeof(location), "%s", value);
    return response_step();
}
esp_err_t httpd_resp_send(httpd_req_t *req, const char *body, ssize_t len) {
    response_len = len;
    if (body && strncmp(req->uri, "/api/status", 11) == 0) {
        assert(len > 0 && (size_t)len < sizeof(status_body));
        memcpy(status_body, body, len);
        status_body[len] = 0;
    }
    return response_step();
}
esp_err_t httpd_resp_send_err(httpd_req_t *req, httpd_err_resp_t err) {
    response_code = err;
    warnings++;
    return response_step();
}
int httpd_req_recv(httpd_req_t *req, char *body, size_t len) { return -1; }
void tcpip_adapter_init(void) {}
esp_err_t esp_event_loop_create_default(void) { return ESP_OK; }
esp_err_t esp_wifi_init(const wifi_init_config_t *cfg) { return ESP_OK; }
esp_err_t esp_wifi_set_storage(int mode) { return ESP_OK; }
esp_err_t esp_wifi_set_mode(int mode) { return ESP_OK; }
esp_err_t esp_wifi_set_config(int iface, const wifi_config_t *cfg) { return ESP_OK; }
esp_err_t esp_wifi_start(void) {
    assert(rf_enabled && !wifi_started);
    if (start_failed) return ESP_FAIL;
    wifi_started = true;
    return ESP_OK;
}
esp_err_t esp_wifi_stop(void) {
    assert(rf_enabled && wifi_started);
    if (stop_failed) return ESP_FAIL;
    wifi_started = false;
    return ESP_OK;
}
void phy_open_rf(void) {
    assert(!rf_enabled && !wifi_started);
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    assert(noise_active);
#endif
#ifdef CONFIG_APP_PAUSE_NETWORK_TIMERS
    assert(timers_active); /* Restoration completes before RF/Wi-Fi start. */
#endif
    rf_enabled = true;
    rf_opens++;
}
void phy_close_rf(void) {
    assert(rf_enabled && !wifi_started);
    rf_enabled = false;
    rf_closes++;
}
int test_socket(int domain, int type, int proto) { return socket_failed ? -1 : 5; }
int test_bind(int fd, const struct sockaddr *addr, size_t len) { return 0; }
int test_close(int fd) { return 0; }
int test_setsockopt(int fd, int level, int opt, const void *val, size_t len) { return 0; }
int test_recvfrom(int fd, void *buf, size_t len, int flags,
                  struct sockaddr *peer, socklen_t *peer_len) { return -1; }
int test_sendto(int fd, const void *buf, size_t len, int flags,
                const struct sockaddr *peer, socklen_t peer_len) { return -1; }
uint16_t test_htons(uint16_t value) { return value; }
void app_get_status(app_status_t *st) {
    memset(st, 0, sizeof(*st));
    st->battery_mv = 4199;
    st->battery_valid = battery_valid;
    st->battery_error = battery_valid ? ESP_OK : ESP_FAIL;
}
esp_err_t app_save_rule(int slot, const rule_cfg_t *cfg) { return ESP_OK; }
bool rule_valid(const rule_cfg_t *cfg) { return true; }
esp_err_t ir_start_learn(int slot) { return ESP_OK; }
int ir_get_carrier(void) { return 38; }
esp_err_t ir_set_carrier(int carrier) { return ESP_OK; }
esp_err_t ir_send(int slot) { return ESP_OK; }
bool ir_has_code(int slot) { return false; }
bool ir_is_busy(void) { return false; }
ir_state_t ir_state(void) { return IR_IDLE; }
esp_err_t ir_last_error(void) { return ESP_OK; }

/* 构造请求后调用实际 URI 分发，单独检查响应和空闲计时，不模拟手机登录界面。 */
static esp_err_t request(const char *uri, int method) {
    memset(&hd.hd_req, 0, sizeof(hd.hd_req));
    strcpy(hd.hd_req.uri, uri);
    hd.hd_req.method = method;
    hd.hd_req.handle = &hd;
    hd.hd_req.aux = &hd.hd_req_aux;
    assert(http_parser_parse_url(uri, strlen(uri), 0,
                                &hd.hd_req_aux.url_parse_res) == 0);
    warnings = response_code = response_calls = 0;
    response_len = 0;
    location[0] = 0;
    return httpd_uri(&hd);
}

int main(void) {
    assert(portal_init() == ESP_OK);
    assert(!rf_enabled && !wifi_started && rf_closes == 1 && rf_opens == 0);
    assert(portal_stop() == ESP_OK && rf_closes == 1);
    now = 100;
    assert(portal_start() == ESP_OK && portal_is_on());
    assert(rf_enabled && wifi_started && rf_opens == 1);
    assert(portal_start() == ESP_OK && rf_opens == 1);
    assert(portal_timeout_ms() == 180000);
    assert(hd.config.max_uri_handlers == 15);
    for (int i = 0; i < 15; i++) assert(hd.hd_calls[i]);
    assert(httpd_register_uri_handler(&hd, hd.hd_calls[0]) ==
           ESP_ERR_HTTPD_HANDLER_EXISTS);
    const char *probes[] = {
        "/generate_204", "/generate_204?test=1",
        "/generate_204_5dca7a2f-7dd6-4fa2-9651-b14dbece592b",
        "/generate_204_08c0cd15-532a-4007-b532-cd5caa8d267c?test=1",
        "/gen_204", "/hotspot-detect.html", "/connecttest.txt", "/ncsi.txt"
    };
    for (int i = 0; i < 8; i++) {
        now += 100000;
        assert(request(probes[i], HTTP_GET) == ESP_OK);
        assert(response_code == 302 && warnings == 0 && response_len == 0);
        assert(strcmp(location, "http://192.168.4.1/") == 0);
        assert(portal_idle_ms() == now - 100);
    }
    assert(portal_idle_ms() >= 600000);
    assert(request("/favicon.ico", HTTP_GET) == ESP_OK);
    assert(response_code == 204 && warnings == 0 && response_len == 0);
    assert(portal_idle_ms() == now - 100);
    assert(request("/mmtls/15c634ca", HTTP_GET) == ESP_OK);
    assert(response_code == 404 && warnings == 0 && response_len == 0);
    assert(portal_idle_ms() == now - 100);
    assert(request("/mmtls/698f2814", HTTP_POST) == ESP_OK);
    assert(response_code == 404 && warnings == 0 && response_len == 0);
    assert(portal_idle_ms() == now - 100);
    assert(request("/unknown", HTTP_GET) == ESP_OK);
    assert(response_code == 404 && warnings > 0);
    assert(request("/generate_204oops", HTTP_GET) == ESP_OK);
    assert(response_code == 404);
    assert(request("/api/status?test=1", HTTP_GET) == ESP_OK);
    assert(response_code == 200 && warnings == 0);
    assert(strstr(status_body, "\"batteryMv\":4199,\"batteryValid\":true,\"batteryError\":0"));
    battery_valid = false;
    assert(request("/api/status", HTTP_GET) == ESP_OK);
    assert(strstr(status_body, "\"batteryValid\":false,\"batteryError\":1"));
    battery_valid = true;
    assert(portal_idle_ms() == now - 100);
    assert(portal_timeout_ms() == 180000);
    assert(request("/api/status/extra", HTTP_GET) == ESP_OK);
    assert(response_code == 404);
    assert(request("/generate_204_random", HTTP_POST) == ESP_OK);
    assert(response_code == 405 && warnings > 0);
    assert(request("/api/send", HTTP_GET) == ESP_OK);
    assert(response_code == 405);
    assert(request("/api/send", HTTP_POST) == ESP_OK);
    assert(response_code == 400 && portal_idle_ms() == 0);
    assert(portal_timeout_ms() == 600000);
    now += 1000;
    assert(request("/?test=1", HTTP_GET) == ESP_OK);
    assert(warnings == 0 && response_len > 0 && portal_idle_ms() == 0);
    assert(portal_timeout_ms() == 600000);
    for (int i = 1; i <= 3; i++) {
        fail_call = i;
        assert(request("/generate_204_random", HTTP_GET) == ESP_FAIL);
        assert(warnings > 0 && response_calls == i);
    }
    for (int i = 1; i <= 2; i++) {
        fail_call = i;
        assert(request("/favicon.ico", HTTP_GET) == ESP_FAIL);
        assert(request("/mmtls/random", HTTP_GET) == ESP_FAIL);
    }
    fail_call = 0;
    assert(request("/api/status", HTTP_GET) == ESP_OK && response_code == 200);
    assert(portal_stop() == ESP_OK && !portal_is_on());
    assert(!rf_enabled && !wifi_started && rf_closes == 2);
    assert(portal_start() == ESP_OK);
    assert(portal_timeout_ms() == 180000);
    assert(request("/generate_204_again", HTTP_GET) == ESP_OK);
    assert(response_code == 302);
    assert(portal_timeout_ms() == 180000);
    assert(request("/", HTTP_GET) == ESP_OK && portal_timeout_ms() == 600000);
    now += 600000;
    assert(request("/api/status", HTTP_GET) == ESP_OK);
    assert(portal_idle_ms() == 600000 && portal_timeout_ms() == 600000);
    assert(portal_stop() == ESP_OK);
    assert(!rf_enabled && !wifi_started);
    socket_failed = true;
    assert(portal_start() == ESP_FAIL && !portal_is_on());
    assert(!rf_enabled && !wifi_started);
    assert(server == NULL && hd.hd_calls == NULL);
    socket_failed = false;
    start_failed = true;
    assert(portal_start() == ESP_FAIL && !portal_is_on());
    assert(!rf_enabled && !wifi_started);
    start_failed = false;
    http_failed = true;
    assert(portal_start() == ESP_FAIL && !portal_is_on());
    assert(!rf_enabled && !wifi_started);
    http_failed = false;
    assert(portal_start() == ESP_OK);
    stop_failed = true;
    assert(portal_stop() == ESP_FAIL && portal_is_on());
    assert(rf_enabled && wifi_started && server == NULL);
    stop_failed = false;
    assert(portal_stop() == ESP_OK && !portal_is_on());
    assert(!rf_enabled && !wifi_started);
    socket_failed = stop_failed = true;
    assert(portal_start() == ESP_FAIL && portal_is_on());
    assert(rf_enabled && wifi_started && server == NULL);
    socket_failed = stop_failed = false;
    assert(portal_stop() == ESP_OK && !portal_is_on());
    assert(!rf_enabled && !wifi_started && rf_closes == rf_opens + 1);
#ifdef CONFIG_APP_PAUSE_NETWORK_TIMERS
    assert(!timers_active && sem_created == sem_freed);
    sem_failed = true;
    assert(portal_start() == ESP_ERR_NO_MEM && !rf_enabled && !timers_active);
    sem_failed = false; callback_failed = true;
    assert(portal_start() == ESP_ERR_NO_MEM && !rf_enabled && !timers_active);
    callback_failed = false; timer_failed = ERR_VAL;
    assert(portal_start() == ESP_FAIL && !rf_enabled && !timers_active);
    timer_failed = ERR_OK;
    assert(portal_start() == ESP_OK && timers_active);
    timer_failed = ERR_MEM;
    assert(portal_stop() == ESP_ERR_NO_MEM && !portal_is_on());
    assert(!rf_enabled && !wifi_started && timers_active);
    timer_failed = ERR_OK;
    assert(portal_stop() == ESP_OK && !timers_active); /* Retry after Wi-Fi stopped. */
    assert(portal_start() == ESP_OK && timers_active);
    stop_failed = true;
    assert(portal_stop() == ESP_FAIL && portal_is_on() && timers_active);
    stop_failed = false;
    assert(portal_stop() == ESP_OK && !timers_active);
    assert(sem_created == sem_freed);
#endif
    (void)noise_active; (void)noise_failed;
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    assert(!noise_active);
    noise_failed = true;
    assert(portal_start() == ESP_FAIL && !portal_is_on() && !rf_enabled);
    assert(!timers_active && !noise_active);
    noise_failed = false;
    for (int i = 0; i < 20; i++) {
        assert(portal_start() == ESP_OK && noise_active && timers_active);
        stop_failed = true;
        assert(portal_stop() == ESP_FAIL && noise_active && timers_active);
        stop_failed = false;
        assert(portal_stop() == ESP_OK && !noise_active && !timers_active);
    }
    assert(portal_start() == ESP_OK);
    noise_failed = true;
    assert(portal_stop() == ESP_FAIL && !portal_is_on() && !rf_enabled);
    assert(timers_active && noise_active);
    noise_failed = false;
    assert(portal_stop() == ESP_OK && !noise_active && !timers_active);
#endif
    puts("portal: routes, redirect, idle time, RF lifecycle, failures and restart passed");
    return 0;
}
'''


WIRE = r'''
#define TAG txrx_tag
#include "../../components/esp_http_server/httpd_txrx.c"
#undef TAG
#define TAG parse_tag
#include "../../components/esp_http_server/httpd_parse.c"
#undef TAG
#define TAG uri_tag
#include "../../components/esp_http_server/httpd_uri.c"
#undef TAG

static struct httpd_data hd;
static struct sock_db sd;
static struct resp_hdr headers[8];
static const char *input;
static size_t input_len, input_pos, output_pos, read_size = 128;
static char output[8000], last_warning[160];
static int socket_errno, socket_error, sockopt_error;
static unsigned filtered_count, eof_reads;
static char last_filter[160];

void test_log(const char *tag, const char *fmt, ...) {
    if (strstr(fmt, "unsupported request prefix")) {
        va_list args;
        va_start(args, fmt);
        vsnprintf(last_filter, sizeof(last_filter), fmt, args);
        va_end(args);
        filtered_count++;
    }
}
void test_warn(const char *tag, const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vsnprintf(last_warning, sizeof(last_warning), fmt, args);
    va_end(args);
}
void *httpd_os_thread_handle(void) { return &hd; }
struct sock_db *httpd_sess_get(httpd_handle_t handle, int fd) { return &sd; }
void httpd_sess_free_ctx(void *ctx, httpd_free_ctx_fn_t free_fn) {
    if (ctx && free_fn) free_fn(ctx);
}
size_t strlcpy(char *dst, const char *src, size_t size) {
    size_t len = strlen(src);
    if (size) {
        size_t count = MIN(len, size - 1);
        memcpy(dst, src, count);
        dst[count] = 0;
    }
    return len;
}
int test_io_sockopt(int fd, int level, int opt, void *value, size_t *size) {
    if (sockopt_error) { errno = EIO; return -1; }
    *(int *)value = socket_error;
    errno = 0; /* lwIP may clear SO_ERROR after reporting it to send/recv. */
    return 0;
}
int test_io_send(int fd, const char *buf, size_t len, int flags) {
    if (socket_errno) { errno = socket_errno; return -1; }
    assert(output_pos + len < sizeof(output));
    memcpy(output + output_pos, buf, len);
    output_pos += len;
    output[output_pos] = 0;
    return len;
}
int test_io_recv(int fd, char *buf, size_t len, int flags) {
    if (socket_errno) { errno = socket_errno; return -1; }
    size_t count = MIN(len, MIN(read_size, input_len - input_pos));
    if (!count) assert(++eof_reads <= 2); /* One buffered byte may accompany the first EOF. */
    memcpy(buf, input + input_pos, count);
    input_pos += count;
    return count;
}
static int receive_data(httpd_handle_t handle, int fd, char *buf, size_t len, int flags) {
    int saved_errno = socket_errno;
    socket_errno = 0;
    int count = test_io_recv(fd, buf, len, flags);
    socket_errno = saved_errno;
    return count;
}
static esp_err_t status_reply(httpd_req_t *req) {
    return httpd_resp_send(req, "{}", 2);
}
static esp_err_t probe_reply(httpd_req_t *req) {
    esp_err_t err = httpd_resp_set_status(req, "302 Found");
    if (err == ESP_OK) err = httpd_resp_set_hdr(req, "Location", "http://192.168.4.1/");
    if (err == ESP_OK) err = httpd_resp_send(req, NULL, 0);
    return err;
}
static esp_err_t background_reply(httpd_req_t *req) {
    esp_err_t err = httpd_resp_set_status(req, "404 Not Found");
    if (err == ESP_OK) err = httpd_resp_send(req, NULL, 0);
    return err;
}
static void new_session(const char *data, size_t len) {
    memset(&sd, 0, sizeof(sd));
    sd.fd = 1;
    sd.handle = &hd;
    sd.send_fn = httpd_default_send;
    sd.recv_fn = httpd_default_recv;
    input = data;
    input_len = len;
    input_pos = output_pos = 0;
    output[0] = last_warning[0] = 0;
    last_filter[0] = 0;
    filtered_count = eof_reads = 0;
    socket_errno = socket_error = sockopt_error = 0;
}
static void check_status(void) {
    const char *get = "GET /api/status HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n";
    new_session(get, strlen(get));
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(httpd_req_delete(&hd) == ESP_OK);
    assert(strstr(output, "HTTP/1.1 200 OK\r\n") && strstr(output, "\r\n\r\n{}"));
    assert(!strstr(output, "Connection: close"));
}
static void check_rejected(const char *data, size_t len, int code) {
    new_session(data, len);
    assert(httpd_req_new(&hd, &sd) != ESP_OK);
    assert(hd.hd_req.aux == NULL && hd.hd_req.handle == NULL);
    char status[32];
    snprintf(status, sizeof(status), "HTTP/1.1 %d ", code);
    assert(strstr(output, status));
    assert(strstr(output, "Connection: close\r\n"));
    assert(strstr(output + 1, "HTTP/1.1") == NULL); /* Exactly one error reply. */
    check_status();
}
static void check_filtered(const char *data, size_t len) {
    new_session(data, len);
    assert(httpd_req_new(&hd, &sd) == ESP_FAIL);
    assert(hd.hd_req.aux == NULL && hd.hd_req.handle == NULL);
    assert(output_pos == 0 && last_warning[0] == 0);
    assert(filtered_count == 1 && strstr(last_filter, "closing connection"));
    check_status();
}
int main(void) {
    hd.config = (httpd_config_t){.max_uri_handlers=3, .max_resp_headers=8};
    hd.hd_td.handle = &hd;
    hd.hd_req_aux.resp_hdrs = headers;
    hd.hd_calls = calloc(3, sizeof(*hd.hd_calls));
    assert(hd.hd_calls);
    const httpd_uri_t routes[] = {
        {.uri="/api/status", .method=HTTP_GET, .handler=status_reply},
        {.uri="/generate_204_*", .method=HTTP_GET, .handler=probe_reply},
        {.uri="/mmtls/*", .method=HTTP_POST, .handler=background_reply}
    };
    for (int i = 0; i < 3; i++)
        assert(httpd_register_uri_handler(&hd, &routes[i]) == ESP_OK);
    assert(HPE_INVALID_METHOD == 16);
    /* Compare all possible first bytes against the real SDK parser. */
    http_parser_settings settings;
    http_parser_settings_init(&settings);
    for (unsigned int ch = 0; ch <= 255; ch++) {
        if (ch == '\r' || ch == '\n') continue;
        http_parser parser;
        http_parser_init(&parser, HTTP_REQUEST);
        char byte = (char)ch;
        size_t parsed = http_parser_execute(&parser, &settings, &byte, 1);
        assert(method_start(ch) == (parsed == 1));
        if (!parsed) assert(HTTP_PARSER_ERRNO(&parser) == HPE_INVALID_METHOD);
    }
    check_status();
    char uri[1100], packet[5000];
    const size_t lengths[] = {616, 617, 618, 1024};
    for (int i = 0; i < 4; i++) {
        strcpy(uri, "/generate_204_");
        size_t prefix = strlen(uri);
        memset(uri + prefix, 'a', lengths[i] - prefix);
        uri[lengths[i]] = 0;
        int len = snprintf(packet, sizeof(packet), "GET %s HTTP/1.1\r\nHost: ap\r\n\r\n", uri);
        new_session(packet, len);
        assert(httpd_req_new(&hd, &sd) == ESP_OK);
        assert(httpd_req_delete(&hd) == ESP_OK);
        assert(strstr(output, "HTTP/1.1 302 Found"));
        assert(strstr(output, "Location: http://192.168.4.1/\r\n"));
    }
    uri[1024] = 'a'; uri[1025] = 0;
    int len = snprintf(packet, sizeof(packet), "GET %s HTTP/1.1\r\nHost: ap\r\n\r\n", uri);
    check_rejected(packet, len, 414);
    char value[2600];
    memset(value, 'b', 1400); value[1400] = 0;
    len = snprintf(packet, sizeof(packet),
                   "GET /api/status HTTP/1.1\r\nX-Test: %s\r\n\r\n", value);
    new_session(packet, len);
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(httpd_req_delete(&hd) == ESP_OK);
    assert(strstr(output, "HTTP/1.1 200 OK"));
    memset(value, 'b', 2500); value[2500] = 0;
    len = snprintf(packet, sizeof(packet),
                   "GET /api/status HTTP/1.1\r\nX-Test: %s\r\n\r\n", value);
    check_rejected(packet, len, 431);
    memset(packet, 0x16, 400); /* Non-HTTP payload, like a binary handshake. */
    check_filtered(packet, 400);
    const unsigned char prefixes[] = {0x00, 0x80, 0xff, 'X', 'g'};
    for (unsigned int i = 0; i < sizeof(prefixes); i++) {
        packet[0] = prefixes[i];
        check_filtered(packet, 400);
    }
    const char *bad = "GARBAGE / HTTP/1.1\r\n\r\n";
    check_rejected(bad, strlen(bad), 400);
    const char *post = "POST /mmtls/698f2814 HTTP/1.1\r\nContent-Length: 200\r\n\r\n";
    len = snprintf(packet, sizeof(packet), "%s", post);
    memset(packet + len, 0x16, 200);
    len += 200;
    const char *get = "GET /api/status HTTP/1.1\r\nHost: ap\r\n\r\n";
    memcpy(packet + len, get, strlen(get));
    new_session(packet, len + strlen(get));
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(httpd_req_delete(&hd) == ESP_OK); /* Purges the binary POST body. */
    assert(strstr(output, "HTTP/1.1 404 Not Found"));
    output_pos = 0; output[0] = 0;
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(httpd_req_delete(&hd) == ESP_OK);
    assert(strstr(output, "HTTP/1.1 200 OK"));
    len = snprintf(packet, sizeof(packet), "%s", post);
    packet[len++] = 0x16; /* Declared 200 bytes, then EOF after one byte. */
    new_session(packet, len);
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(strstr(output, "HTTP/1.1 404 Not Found"));
    assert(httpd_req_delete(&hd) == ESP_FAIL);
    assert(eof_reads == 2 && hd.hd_req.aux == NULL && hd.hd_req.handle == NULL);
    check_status(); /* A new session still works after the truncated body. */
    read_size = 7;
    check_status(); /* Fragmented HTTP remains valid. */
    read_size = 1;
    const char *leading_crlf = "\r\n\r\nGET /api/status HTTP/1.1\r\nHost: ap\r\n\r\n";
    new_session(leading_crlf, strlen(leading_crlf));
    assert(httpd_req_new(&hd, &sd) == ESP_OK);
    assert(httpd_req_delete(&hd) == ESP_OK);
    assert(strstr(output, "HTTP/1.1 200 OK") && filtered_count == 0);
    const char *leading_binary = "\r\n\r\n\x16";
    check_filtered(leading_binary, strlen(leading_binary));
    read_size = 128;
    socket_errno = ECONNRESET;
    assert(httpd_default_send(&hd, 1, "x", 1, 0) == HTTPD_SOCK_ERR_FAIL);
    char expected[40];
    snprintf(expected, sizeof(expected), "error in send : %d", ECONNRESET);
    assert(strstr(last_warning, expected));
    socket_errno = EAGAIN;
    assert(httpd_default_recv(&hd, 1, packet, 1, 0) == HTTPD_SOCK_ERR_TIMEOUT);
    socket_errno = EBADF;
    assert(httpd_default_send(&hd, 1, "x", 1, 0) == HTTPD_SOCK_ERR_INVALID);
    socket_errno = EAGAIN; socket_error = EINVAL;
    assert(httpd_default_send(&hd, 1, "x", 1, 0) == HTTPD_SOCK_ERR_INVALID);
    sockopt_error = 1;
    assert(httpd_default_send(&hd, 1, "x", 1, 0) == HTTPD_SOCK_ERR_FAIL);
    new_session(bad, strlen(bad));
    sd.recv_fn = receive_data;
    /* 接收和解析正常，单独注入错误响应发送失败，检查资源清理。 */
    socket_errno = ECONNRESET;
    assert(httpd_req_new(&hd, &sd) == ESP_ERR_HTTPD_RESP_SEND);
    assert(hd.hd_req.aux == NULL);
    check_status();
    new_session(bad, strlen(bad));
    hd.config.max_resp_headers = 0;
    assert(httpd_req_new(&hd, &sd) == ESP_ERR_HTTPD_RESP_HDR);
    assert(hd.hd_req.aux == NULL);
    hd.config.max_resp_headers = 8;
    check_status();
    httpd_unregister_all_uri_handlers(&hd);
    free(hd.hd_calls);
    puts("HTTP: protocol filtering, long URI/header, POST body, error-close, recovery and socket errno passed");
    return 0;
}
'''


def main():
    gcc = shutil.which("gcc")
    if gcc is None:
        raise FileNotFoundError("找不到规则测试所需的主机 GCC")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sdk_mock.h").write_text(SDK, encoding="utf-8")
    for name in HEADERS:
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "sdk_mock.h"\n', encoding="utf-8")
    command = [
        gcc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter", "-Wno-sign-compare",
        "-Wno-implicit-fallthrough",  # SDK 3.4 解析器有意使用 switch fallthrough。
        "-Wno-format",  # 保留 SDK 3.4 面向 Xtensa 的 printf 格式。
        "-I", str(OUT),
        "-I", str(SDK_PATH / "components" / "http_parser" / "include"),
        "-I", str(SDK_PATH / "components" / "json" / "cJSON"),
        "-include", str(OUT / "sdk_mock.h"),
        str(SDK_PATH / "components" / "http_parser" / "src" / "http_parser.c"),
        str(SDK_PATH / "components" / "json" / "cJSON" / "cJSON.c"),
    ]
    for name, source in [("portal", TEST), ("portal_pause", TEST), ("http", WIRE)]:
        path = OUT / f"{name}_test.c"
        path.write_text(source, encoding="utf-8")
        exe = OUT / f"{name}_test.exe"
        options = ["-DCONFIG_APP_PAUSE_NETWORK_TIMERS=1", "-DCONFIG_APP_PAUSE_NOISE_TIMER=1"] if name == "portal_pause" else []
        subprocess.run(command + options + [str(path), "-o", str(exe)], check=True, cwd=ROOT)
        subprocess.run([str(exe)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
