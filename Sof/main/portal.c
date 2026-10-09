#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "driver/rtc.h"
#include "esp_log.h"
#include "esp_http_server.h"
#include "tcpip_adapter.h"
#include "lwip/sockets.h"
#ifdef CONFIG_APP_PAUSE_NETWORK_TIMERS
#include "lwip/tcpip.h"
#include "lwip/sys.h"
#endif
#include "cJSON.h"
#include "app.h"
#include "ir.h"
#include "portal.h"
#include "noise_timer.h"
#include "page.h"

static const char *TAG = "portal";
static httpd_handle_t server;
static volatile bool dns_running;
static volatile bool dns_exited = true;
static int dns_fd = -1;
static bool ap_on;
static TickType_t last_action;
static bool ap_used;

#ifdef CONFIG_APP_PAUSE_NETWORK_TIMERS
/* Implemented in the generated SDK timeouts.c; called only by tiT. */
extern err_t app_lwip_timers_set(int active, unsigned counts[3]);
typedef struct {
    sys_sem_t done;
    bool active;
    err_t result;
    unsigned counts[3];
} timer_request_t;

static void network_timer_request(void *arg)
{
    timer_request_t *request = arg;
    request->result = app_lwip_timers_set(request->active, request->counts);
    sys_sem_signal(&request->done);
}
#endif

static esp_err_t set_network_timers(bool active)
{
#ifdef CONFIG_APP_PAUSE_NETWORK_TIMERS
    timer_request_t request = { .active = active };
    err_t result = sys_sem_new(&request.done, 0);
    if (result != ERR_OK) {
        ESP_LOGE(TAG, "network timer semaphore failed: %d", result);
        return ESP_ERR_NO_MEM;
    }
    result = tcpip_callback(network_timer_request, &request);
    if (result == ERR_OK) {
        /* No timeout: the queued callback owns this stack context until done. */
        sys_sem_wait(&request.done);
        result = request.result;
    }
    sys_sem_free(&request.done);
    if (result != ERR_OK) {
        ESP_LOGE(TAG, "network timers %s failed: %d", active ? "resume" : "pause", result);
        return result == ERR_MEM ? ESP_ERR_NO_MEM : ESP_FAIL;
    }
    ESP_LOGI(TAG, "network timers %s: cyclic=%u tcp=%u remaining=%u",
             active ? "resumed" : "paused", request.counts[0], request.counts[1], request.counts[2]);
#endif
    return ESP_OK;
}

/* RF/Wi-Fi 停止后独立清理两组定时器，保留首个错误。 */
static esp_err_t pause_timers(void)
{
    esp_err_t err = noise_timer_set_active(false);
    esp_err_t network_err = set_network_timers(false);
    return err != ESP_OK ? err : network_err;
}

/* 仅页面访问和控制操作刷新空闲计时；状态轮询及手机后台探测不延长热点寿命。 */
static void record_action(void)
{
    last_action = xTaskGetTickCount();
    ap_used = true;
}

static esp_err_t reply(httpd_req_t *req, const char *status, const char *body)
{
    esp_err_t err = httpd_resp_set_status(req, status);
    if (err == ESP_OK) err = httpd_resp_set_type(req, "application/json; charset=utf-8");
    if (err == ESP_OK) err = httpd_resp_send(req, body, strlen(body));
    return err;
}

static esp_err_t error_reply(httpd_req_t *req, const char *status, esp_err_t err)
{
    char body[80];
    snprintf(body, sizeof(body), "{\"error\":\"%s\",\"code\":%d}",
             esp_err_to_name(err), err);
    return reply(req, status, body);
}

/* 请求体限制为 255 字节，并循环读取分片；读取或解析失败返回 NULL，由调用方回复错误。 */
static cJSON *read_json(httpd_req_t *req)
{
    if (req->content_len <= 0 || req->content_len > 255) return NULL;
    char body[256];
    int remain = req->content_len;
    int pos = 0;
    while (remain > 0) {
        int got = httpd_req_recv(req, body + pos, remain);
        if (got <= 0) return NULL;
        pos += got;
        remain -= got;
    }
    body[pos] = 0;
    return cJSON_Parse(body);
}

/* HTTP 使用槽位 1、2，校验整数后转换为固件内部槽位 0、1。 */
static bool json_slot(const cJSON *json, int *slot)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(json, "slot");
    if (!cJSON_IsNumber(item) || item->valuedouble != item->valueint ||
        item->valueint < 1 || item->valueint > 2) return false;
    *slot = item->valueint - 1;
    return true;
}

static esp_err_t page_get(httpd_req_t *req)
{
    record_action();
    esp_err_t err = httpd_resp_set_type(req, "text/html; charset=utf-8");
    if (err == ESP_OK) err = httpd_resp_send(req, control_page, sizeof(control_page) - 1);
    return err;
}

/* 手机联网探测重定向到配置页；不将探测计入实际使用。 */
static esp_err_t probe_get(httpd_req_t *req)
{
    ESP_LOGI(TAG, "captive portal probe: %s", req->uri);
    esp_err_t err = httpd_resp_set_status(req, "302 Found");
    if (err == ESP_OK) err = httpd_resp_set_hdr(req, "Location", "http://192.168.4.1/");
    if (err == ESP_OK) err = httpd_resp_send(req, NULL, 0);
    return err;
}

static esp_err_t favicon_get(httpd_req_t *req)
{
    esp_err_t err = httpd_resp_set_status(req, "204 No Content");
    if (err == ESP_OK) err = httpd_resp_send(req, NULL, 0);
    return err;
}

static esp_err_t background_get(httpd_req_t *req)
{
    esp_err_t err = httpd_resp_set_status(req, "404 Not Found");
    if (err == ESP_OK) err = httpd_resp_send(req, NULL, 0);
    return err;
}

/* 只读取状态快照，不刷新热点计时；无效读数配套返回错误码供页面展示。 */
static esp_err_t status_get(httpd_req_t *req)
{
    app_status_t st;
    app_get_status(&st);
    char body[640];
    int len = snprintf(body, sizeof(body),
        "{\"temperature10\":%d,\"valid\":%s,\"sensorError\":%d,\"carrier\":%d,"
        "\"batteryMv\":%u,\"batteryValid\":%s,\"batteryError\":%d,"
        "\"learnState\":%d,\"learnError\":%d,\"rules\":["
        "{\"threshold10\":%d,\"rising\":%s,\"enabled\":%s,\"learned\":%s,\"sendError\":%d},"
        "{\"threshold10\":%d,\"rising\":%s,\"enabled\":%s,\"learned\":%s,\"sendError\":%d}]}",
        st.temp10, st.temp_valid ? "true" : "false", st.sensor_error,
        ir_get_carrier(),
        (unsigned)st.battery_mv, st.battery_valid ? "true" : "false", st.battery_error,
        ir_state(), ir_last_error(), st.rules[0].threshold10,
        st.rules[0].rising ? "true" : "false", st.rules[0].enabled ? "true" : "false",
        ir_has_code(0) ? "true" : "false", st.send_error[0], st.rules[1].threshold10,
        st.rules[1].rising ? "true" : "false", st.rules[1].enabled ? "true" : "false",
        ir_has_code(1) ? "true" : "false", st.send_error[1]);
    if (len < 0 || len >= sizeof(body)) return error_reply(req, "500 Internal Server Error", ESP_ERR_NO_MEM);
    return reply(req, "200 OK", body);
}

static esp_err_t rule_post(httpd_req_t *req)
{
    record_action();
    cJSON *json = read_json(req);
    int slot;
    if (!json || !json_slot(json, &slot)) {
        cJSON_Delete(json);
        return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    }
    const cJSON *temp = cJSON_GetObjectItemCaseSensitive(json, "threshold10");
    const cJSON *rise = cJSON_GetObjectItemCaseSensitive(json, "rising");
    const cJSON *enabled = cJSON_GetObjectItemCaseSensitive(json, "enabled");
    if (!cJSON_IsNumber(temp) || temp->valuedouble != temp->valueint ||
        temp->valueint < -100 || temp->valueint > 500 ||
        !cJSON_IsBool(rise) || !cJSON_IsBool(enabled)) {
        cJSON_Delete(json);
        return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    }
    rule_cfg_t cfg = {
        .threshold10 = temp->valueint,
        .rising = cJSON_IsTrue(rise), .enabled = cJSON_IsTrue(enabled)
    };
    cJSON_Delete(json);
    if (!rule_valid(&cfg)) return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    esp_err_t err = app_save_rule(slot, &cfg);
    if (err != ESP_OK) return error_reply(req, "500 Internal Server Error", err);
    return reply(req, "200 OK", "{\"ok\":true}");
}

static esp_err_t learn_post(httpd_req_t *req)
{
    record_action();
    cJSON *json = read_json(req);
    int slot;
    if (!json || !json_slot(json, &slot)) {
        cJSON_Delete(json);
        return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    }
    cJSON_Delete(json);
    esp_err_t err = ir_start_learn(slot);
    if (err == ESP_ERR_INVALID_STATE) return error_reply(req, "409 Conflict", err);
    if (err != ESP_OK) return error_reply(req, "500 Internal Server Error", err);
    return reply(req, "202 Accepted", "{\"ok\":true}");
}

static esp_err_t carrier_post(httpd_req_t *req)
{
    record_action();
    cJSON *json = read_json(req);
    if (!json) return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(json, "carrier");
    if (!cJSON_IsNumber(item) || item->valuedouble != item->valueint ||
        (item->valueint != 36 && item->valueint != 38 && item->valueint != 40)) {
        cJSON_Delete(json);
        return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    }
    int khz = item->valueint;
    cJSON_Delete(json);
    esp_err_t err = ir_set_carrier(khz);
    if (err != ESP_OK) return error_reply(req, "500 Internal Server Error", err);
    return reply(req, "200 OK", "{\"ok\":true}");
}

static esp_err_t send_post(httpd_req_t *req)
{
    record_action();
    cJSON *json = read_json(req);
    int slot;
    if (!json || !json_slot(json, &slot)) {
        cJSON_Delete(json);
        return error_reply(req, "400 Bad Request", ESP_ERR_INVALID_ARG);
    }
    cJSON_Delete(json);
    esp_err_t err = ir_send(slot);
    if (err == ESP_ERR_NOT_FOUND) return error_reply(req, "404 Not Found", err);
    if (err == ESP_ERR_INVALID_STATE) return error_reply(req, "409 Conflict", err);
    if (err != ESP_OK) return error_reply(req, "500 Internal Server Error", err);
    return reply(req, "200 OK", "{\"ok\":true}");
}

/* 仅为 IN 类 A 查询返回 192.168.4.1；不支持的查询返回无答案响应。
 * 使用接收超时定期检查退出标记，任务退出时自行关闭 socket。 */
static void dns_task(void *arg)
{
    uint8_t query[256], response[300];
    struct timeval timeout = { .tv_sec = 0, .tv_usec = 200000 };
    if (setsockopt(dns_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0) {
        ESP_LOGE(TAG, "DNS receive timeout setup failed");
        dns_running = false;
    }
    while (dns_running) {
        struct sockaddr_in peer;
        socklen_t peer_len = sizeof(peer);
        int n = recvfrom(dns_fd, query, sizeof(query), 0,
                         (struct sockaddr *)&peer, &peer_len);
        if (n < 17) continue;
        int pos = 12;
        while (pos < n && query[pos] && query[pos] <= 63) pos += query[pos] + 1;
        if (pos + 5 > n || query[pos] != 0) continue;
        int question_end = pos + 5;
        if (question_end + 16 > sizeof(response)) continue;
        memcpy(response, query, question_end);
        response[2] = 0x81; response[3] = 0x80;
        response[4] = 0; response[5] = 1;
        response[6] = 0; response[7] = 0;
        response[8] = response[9] = response[10] = response[11] = 0;
        int out = question_end;
        if (query[pos + 1] == 0 && query[pos + 2] == 1 &&
            query[pos + 3] == 0 && query[pos + 4] == 1) {
            const uint8_t answer[] = { 0xc0, 0x0c, 0, 1, 0, 1, 0, 0, 0, 0, 0, 4,
                                       192, 168, 4, 1 };
            memcpy(response + out, answer, sizeof(answer));
            out += sizeof(answer);
            response[7] = 1;
        }
        if (sendto(dns_fd, response, out, 0, (struct sockaddr *)&peer, peer_len) < 0)
            ESP_LOGW(TAG, "DNS reply failed");
    }
    close(dns_fd);
    dns_fd = -1;
    dns_exited = true;
    vTaskDelete(NULL);
}

esp_err_t portal_init(void)
{
    ESP_LOGI(TAG, "init stage=tcpip_adapter_init");
    tcpip_adapter_init();
    ESP_LOGI(TAG, "init stage=esp_event_loop_create_default");
    esp_err_t err = esp_event_loop_create_default();
    if (err != ESP_OK) return err;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_LOGI(TAG, "init stage=esp_wifi_init");
    err = esp_wifi_init(&init);
    if (err != ESP_OK) return err;
    ESP_LOGI(TAG, "init stage=esp_wifi_set_storage");
    err = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (err != ESP_OK) return err;
    ESP_LOGI(TAG, "init stage=esp_wifi_set_mode");
    err = esp_wifi_set_mode(WIFI_MODE_AP);
    if (err != ESP_OK) return err;
    wifi_config_t cfg = { 0 };
    snprintf((char *)cfg.ap.ssid, sizeof(cfg.ap.ssid), "空调智能温控");
    cfg.ap.ssid_len = strlen((char *)cfg.ap.ssid);
    cfg.ap.authmode = WIFI_AUTH_OPEN;
    cfg.ap.max_connection = 4;
    ESP_LOGI(TAG, "init stage=esp_wifi_set_config");
    err = esp_wifi_set_config(ESP_IF_WIFI_AP, &cfg);
    if (err != ESP_OK) return err;
    ESP_LOGI(TAG, "init stage=phy_close_rf");
    phy_close_rf();
    err = pause_timers();
    if (err != ESP_OK) return err;
    ESP_LOGI(TAG, "RF disabled; AP off");
    return ESP_OK;
}

esp_err_t portal_start(void)
{
    last_action = xTaskGetTickCount();
    if (ap_on)
        return server && dns_running && !dns_exited ? ESP_OK : ESP_ERR_INVALID_STATE;
    ap_used = false;
    esp_err_t err = set_network_timers(true);
    if (err != ESP_OK) return err;
    err = noise_timer_set_active(true);
    if (err != ESP_OK) {
        esp_err_t cleanup = set_network_timers(false);
        return cleanup != ESP_OK ? cleanup : err;
    }
    phy_open_rf();
    err = esp_wifi_start();
    if (err != ESP_OK) {
        phy_close_rf();
        esp_err_t cleanup = pause_timers();
        if (cleanup != ESP_OK) return cleanup;
        return err;
    }
    ap_on = true;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_open_sockets = 5;
    config.lru_purge_enable = true;
    config.max_uri_handlers = 15;
    err = httpd_start(&server, &config);
    if (err != ESP_OK) goto fail_wifi;
    /* 同时注册手机探测、后台请求和五个控制 API；通配路径依赖本地 SDK URI 覆盖。 */
    const httpd_uri_t routes[] = {
        { .uri = "/", .method = HTTP_GET, .handler = page_get },
        { .uri = "/generate_204", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/generate_204_*", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/gen_204", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/hotspot-detect.html", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/connecttest.txt", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/ncsi.txt", .method = HTTP_GET, .handler = probe_get },
        { .uri = "/favicon.ico", .method = HTTP_GET, .handler = favicon_get },
        { .uri = "/mmtls/*", .method = HTTP_GET, .handler = background_get },
        { .uri = "/mmtls/*", .method = HTTP_POST, .handler = background_get },
        { .uri = "/api/status", .method = HTTP_GET, .handler = status_get },
        { .uri = "/api/rule", .method = HTTP_POST, .handler = rule_post },
        { .uri = "/api/carrier", .method = HTTP_POST, .handler = carrier_post },
        { .uri = "/api/learn", .method = HTTP_POST, .handler = learn_post },
        { .uri = "/api/send", .method = HTTP_POST, .handler = send_post }
    };
    for (int i = 0; i < sizeof(routes) / sizeof(routes[0]); i++) {
        err = httpd_register_uri_handler(server, &routes[i]);
        if (err != ESP_OK) goto fail_http;
    }
    dns_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (dns_fd < 0) { err = ESP_FAIL; goto fail_http; }
    struct sockaddr_in addr = { .sin_family = AF_INET, .sin_port = htons(53),
                                .sin_addr.s_addr = INADDR_ANY };
    if (bind(dns_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        err = ESP_FAIL;
        close(dns_fd); dns_fd = -1;
        goto fail_http;
    }
    dns_running = true;
    dns_exited = false;
    if (xTaskCreate(dns_task, "dns", 3072, NULL, 5, NULL) != pdPASS) {
        err = ESP_ERR_NO_MEM;
        dns_running = false; dns_exited = true;
        close(dns_fd); dns_fd = -1;
        goto fail_http;
    }
    ap_on = true;
    ESP_LOGI(TAG, "open AP at http://192.168.4.1");
    return ESP_OK;
/* 启动失败按 HTTP、Wi-Fi 顺序清理；清理失败返回该错误，保留状态便于后续处理。 */
fail_http:
    {
        esp_err_t cleanup = httpd_stop(server);
        if (cleanup != ESP_OK) {
            ESP_LOGE(TAG, "HTTP cleanup failed: %s", esp_err_to_name(cleanup));
            return cleanup;
        }
        server = NULL;
    }
fail_wifi:
    {
        esp_err_t cleanup = esp_wifi_stop();
        if (cleanup != ESP_OK) {
            ESP_LOGE(TAG, "Wi-Fi cleanup failed: %s", esp_err_to_name(cleanup));
            return cleanup;
        }
        phy_close_rf();
        ap_on = false;
        cleanup = pause_timers();
        if (cleanup != ESP_OK) return cleanup;
    }
    return err;
}

esp_err_t portal_stop(void)
{
    if (!ap_on) {
        return pause_timers();
    }
    if (ir_is_busy())
        return ESP_ERR_INVALID_STATE;
    /* 等待 DNS 任务自行退出，确认 socket 关闭后再停止 HTTP 和 Wi-Fi。 */
    dns_running = false;
    for (int i = 0; i < 20 && !dns_exited; i++) vTaskDelay(pdMS_TO_TICKS(20));
    if (!dns_exited) return ESP_ERR_TIMEOUT;
    esp_err_t err;
    if (server) {
        err = httpd_stop(server);
        if (err != ESP_OK) return err;
        server = NULL;
    }
    err = esp_wifi_stop();
    if (err == ESP_OK) {
        phy_close_rf();
        ap_on = false;
        ESP_LOGI(TAG, "AP stopped; RF disabled");
        err = pause_timers();
    }
    return err;
}

bool portal_is_on(void) { return ap_on; }
uint32_t portal_idle_ms(void)
{
    return (xTaskGetTickCount() - last_action) * portTICK_PERIOD_MS;
}

uint32_t portal_timeout_ms(void)
{
    return ap_used ? 600000 : 180000;
}
