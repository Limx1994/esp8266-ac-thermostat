/* Honor direct AP clients' DHCP delivery flags and retain packet summaries.
 * Save RX fields before SDK create_msg overwrites them.
 * Emit logs after udp_sendto so serial output cannot delay the first reply.
 * Packet handling and ARP learning run on tiT. The WiFi completion task
 * shares only the protected failure records below.
 */
#include <stddef.h>
#include "esp_log.h"
#include "lwip/etharp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

err_t app_dhcps_arp_learn(struct netif *netif, const ip4_addr_t *ip,
                         struct eth_addr *mac);

struct dhcps_trace_data {
    u8_t xid[4], ip[4], req[4], sid[4], mask[4], gw[4], dns[4];
    u16_t flags, bytes, copied;
    u8_t type, cookie, options, direct;
};

static struct dhcps_trace_data dhcps_trace_rx;
static bool dhcps_trace_pending;

/* The WiFi completion task only records failures. tiT consumes a matching
 * failure on the client's next retry. No extra sends, timers or allocations.
 * Protect the bounded cache against task switches; never log under the lock.
 */
static struct {
    u8_t xid[4], mac[6], type;
    bool used;
} dhcps_failed[CONFIG_LWIP_DHCPS_MAX_STATION_NUM];
static bool dhcps_retry_active;
static unsigned dhcps_failed_next;

static void dhcps_retry_reset(bool active)
{
    portENTER_CRITICAL();
    memset(dhcps_failed, 0, sizeof(dhcps_failed));
    dhcps_failed_next = 0;
    dhcps_retry_active = active;
    portEXIT_CRITICAL();
}

void app_dhcps_note_failure(const u8_t *xid, const u8_t *mac, unsigned type)
{
    bool evicted = false;
    portENTER_CRITICAL();
    if (dhcps_retry_active && (type == 2 || type == 5)) {
        unsigned count = CONFIG_LWIP_DHCPS_MAX_STATION_NUM;
        unsigned slot = count;
        for (unsigned i = 0; i < count; i++) {
            if (dhcps_failed[i].used && dhcps_failed[i].type == type &&
                !memcmp(dhcps_failed[i].xid, xid, 4) &&
                !memcmp(dhcps_failed[i].mac, mac, 6)) { slot = i; break; }
            if (!dhcps_failed[i].used && slot == count) slot = i;
        }
        if (slot == count) {
            slot = dhcps_failed_next++ % count;
            evicted = true;
        }
        memcpy(dhcps_failed[slot].xid, xid, 4);
        memcpy(dhcps_failed[slot].mac, mac, 6);
        dhcps_failed[slot].type = type;
        dhcps_failed[slot].used = true;
    }
    portEXIT_CRITICAL();
    if (evicted) ESP_LOGW("dhcps_trace", "fallback_record evicted=1 reason=capacity");
}

static bool dhcps_take_fallback(const u8_t *xid, const u8_t *mac, unsigned type)
{
    bool found = false;
    portENTER_CRITICAL();
    for (unsigned i = 0; i < CONFIG_LWIP_DHCPS_MAX_STATION_NUM; i++) {
        if (dhcps_retry_active && dhcps_failed[i].used &&
            dhcps_failed[i].type == type && !memcmp(dhcps_failed[i].xid, xid, 4) &&
            !memcmp(dhcps_failed[i].mac, mac, 6)) {
            dhcps_failed[i].used = false;
            found = true;
            break;
        }
    }
    portEXIT_CRITICAL();
    return found;
}

static void dhcps_trace_decode(struct dhcps_trace_data *d,
                               const struct dhcps_msg *m, size_t len)
{
    memset(d, 0, sizeof(*d));
    d->bytes = d->copied = len;
    if (len < offsetof(struct dhcps_msg, options) + 4) return;
    memcpy(d->xid, m->xid, 4);
    memcpy(d->ip, m->op == 1 ? m->ciaddr : m->yiaddr, 4);
    d->flags = ntohs(m->flags);
    const u8_t zero[] = {0, 0, 0, 0};
    d->direct = memcmp(m->giaddr, zero, 4) == 0;
    const u8_t cookie[] = {99, 130, 83, 99};
    d->cookie = memcmp(m->options, cookie, 4) == 0;
    size_t available = len - offsetof(struct dhcps_msg, options);
    if (available > sizeof(m->options)) available = sizeof(m->options);
    for (size_t i = 4; i < available;) {
        u8_t code = m->options[i++];
        if (code == 255) { d->options = 1; return; }
        if (code == 0) continue;
        if (i == available) return;
        u8_t n = m->options[i++];
        if (n > available - i) return;
        if (code == 53 && n == 1) d->type = m->options[i];
        u8_t *ip = NULL;
        switch (code) {
            case 50: ip = d->req; break;
            case 54: ip = d->sid; break;
            case 1: ip = d->mask; break;
            case 3: ip = d->gw; break;
            case 6: ip = d->dns; break;
        }
        if (ip && n >= 4) memcpy(ip, &m->options[i], 4);
        i += n;
    }
}

#define DHCPS_TRACE_IP(a) (a)[0], (a)[1], (a)[2], (a)[3]

static void dhcps_trace_flush(bool attempted)
{
    if (!dhcps_trace_pending) return;
    const struct dhcps_trace_data *d = &dhcps_trace_rx;
    ESP_LOGI("dhcps_trace", "rx type=%u xid=%02x%02x%02x%02x flags=%04x "
             "ci=%u.%u.%u.%u req=%u.%u.%u.%u sid=%u.%u.%u.%u "
             "bytes=%u copied=%u cookie=%u options=%u tx_attempted=%u",
             d->type, DHCPS_TRACE_IP(d->xid), d->flags,
             DHCPS_TRACE_IP(d->ip), DHCPS_TRACE_IP(d->req),
             DHCPS_TRACE_IP(d->sid), d->bytes, d->copied,
             d->cookie, d->options, attempted);
    dhcps_trace_pending = false;
}

static void dhcps_trace_save(const struct dhcps_msg *m, u16_t copied, u16_t total)
{
    dhcps_trace_decode(&dhcps_trace_rx, m, copied);
    dhcps_trace_rx.bytes = total;
    dhcps_trace_pending = true;
}

static err_t dhcps_trace_send(struct netif *netif, struct udp_pcb *pcb, struct pbuf *p,
                             const ip_addr_t *dest, u16_t port,
                             const struct dhcps_msg *m)
{
    struct dhcps_trace_data d;
    dhcps_trace_decode(&d, m, sizeof(*m));
    ip_addr_t target = *dest;
    err_t arp_error = ERR_OK;
    bool fallback = false;
    if (dhcps_trace_rx.direct && (d.type == 2 || d.type == 5)) {
        ip4_addr_t ci;
        memcpy(&ci.addr, dhcps_trace_rx.ip, 4);
        bool unicast = !ip4_addr_isany_val(ci) || !(dhcps_trace_rx.flags & 0x8000);
        if (unicast && ip4_addr_isany_val(ci)) {
            fallback = dhcps_take_fallback(m->xid, m->chaddr, d.type);
            if (fallback) unicast = false;
        }
        if (unicast) {
            if (ip4_addr_isany_val(ci)) memcpy(&ci.addr, m->yiaddr, 4);
            ip4_addr_set(ip_2_ip4(&target), &ci);
            struct eth_addr mac;
            memcpy(mac.addr, m->chaddr, sizeof(mac.addr));
            arp_error = app_dhcps_arp_learn(netif, &ci, &mac);
        }
    }
    /* udp_sendto can leave UDP/IP/Ethernet headers in p; log payload size
       captured before sending, rather than those added headers. */
    u16_t bytes = p->tot_len;
    err_t result = arp_error;
    if (result == ERR_OK) result = udp_sendto(pcb, p, &target, port);
    dhcps_trace_flush(arp_error == ERR_OK);
    ESP_LOGI("dhcps_trace", "tx type=%u xid=%02x%02x%02x%02x flags=%04x "
             "yi=%u.%u.%u.%u dst=" IPSTR ":%u bytes=%u arp_err=%d err=%d fallback=%u",
             d.type, DHCPS_TRACE_IP(d.xid), d.flags, DHCPS_TRACE_IP(d.ip),
             IP2STR(ip_2_ip4(&target)), port, bytes, (int)arp_error, (int)result, fallback);
    ESP_LOGI("dhcps_trace", "tx options mask=%u.%u.%u.%u gw=%u.%u.%u.%u "
             "dns=%u.%u.%u.%u sid=%u.%u.%u.%u cookie=%u options=%u",
             DHCPS_TRACE_IP(d.mask), DHCPS_TRACE_IP(d.gw),
             DHCPS_TRACE_IP(d.dns), DHCPS_TRACE_IP(d.sid), d.cookie, d.options);
    return result;
}

#undef DHCPS_TRACE_IP
