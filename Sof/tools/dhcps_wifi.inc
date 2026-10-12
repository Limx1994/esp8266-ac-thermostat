/* Called before the SDK's original TX callback releases its pbuf.
 * Read only the contiguous Ethernet/IP/UDP/DHCP bytes still in that pbuf.
 * The driver can rewrite Ethernet addresses; identification uses the DHCP XID.
 * Record failed AP unicasts for the client's next retry. No allocations,
 * immediate retransmits or changes to callback ownership/status.
 */
#include "esp_log.h"

void app_dhcps_note_failure(const uint8_t *xid, const uint8_t *mac, unsigned type);

static unsigned dhcps_wifi_u16(const uint8_t *p)
{
    return ((unsigned)p[0] << 8) | p[1];
}

static const uint8_t *dhcps_wifi_message(const struct pbuf *p, bool reply,
                                        const uint8_t **ip_out, unsigned *len_out)
{
    if (!p || !p->payload || p->len < 14 + 20) return NULL;
    const uint8_t *frame = p->payload;
    if (frame[12] != 0x08 || frame[13] != 0x00) return NULL;
    const uint8_t *ip = frame + 14;
    unsigned ihl = (ip[0] & 15) * 4;
    unsigned total = dhcps_wifi_u16(ip + 2);
    if ((ip[0] >> 4) != 4 || ihl < 20 || total < ihl + 8 + 240 ||
        total > (unsigned)p->len - 14 || ip[9] != 17 ||
        (ip[6] & 0x3f) || ip[7]) return NULL;
    const uint8_t *udp = ip + ihl;
    unsigned length = dhcps_wifi_u16(udp + 4);
    if (dhcps_wifi_u16(udp) != (reply ? 67U : 68U) ||
        dhcps_wifi_u16(udp + 2) != (reply ? 68U : 67U) ||
        length < 8 + 240 || length > total - ihl) return NULL;
    const uint8_t *msg = udp + 8;
    const uint8_t cookie[] = {99, 130, 83, 99};
    if (msg[0] != (reply ? 2 : 1) || memcmp(msg + 236, cookie, 4)) return NULL;
    *ip_out = ip;
    *len_out = length;
    return msg;
}

/* Copy before passing pbuf ownership to the next layer/driver. Log afterward
 * using this stack snapshot, never a potentially freed or rewritten frame.
 */
struct dhcps_wifi_link {
    uint8_t xid[4], l2[6], mac[6];
    bool valid;
};

static void dhcps_wifi_link_save(struct dhcps_wifi_link *link,
                                 const struct netif *netif, const struct pbuf *p,
                                 bool reply)
{
    link->valid = false;
    if ((intptr_t)netif->state != ESP_IF_WIFI_AP) return;
    const uint8_t *ip;
    unsigned length;
    const uint8_t *msg = dhcps_wifi_message(p, reply, &ip, &length);
    if (!msg) return;
    memcpy(link->xid, msg + 4, 4);
    memcpy(link->mac, msg + 28, 6);
    memcpy(link->l2, (const uint8_t *)p->payload + (reply ? 0 : 6), 6);
    link->valid = true;
}

#define DHCPS_WIFI_MAC(m) (m)[0], (m)[1], (m)[2], (m)[3], (m)[4], (m)[5]

static void dhcps_wifi_link_log(const char *direction,
                                const struct dhcps_wifi_link *link, int error)
{
    if (!link->valid) return;
    ESP_LOGI("dhcps_trace", "wifi_link dir=%s xid=%02x%02x%02x%02x "
             "l2=%02x:%02x:%02x:%02x:%02x:%02x "
             "chaddr=%02x:%02x:%02x:%02x:%02x:%02x match=%u err=%d",
             direction, link->xid[0], link->xid[1], link->xid[2], link->xid[3],
             DHCPS_WIFI_MAC(link->l2), DHCPS_WIFI_MAC(link->mac),
             memcmp(link->l2, link->mac, 6) == 0, error);
}

#undef DHCPS_WIFI_MAC

static void dhcps_wifi_done(const esp_aio_t *aio)
{
    const uint8_t *ip;
    unsigned length;
    const uint8_t *msg = dhcps_wifi_message(aio->arg, true, &ip, &length);
    if (!msg) return;
    unsigned type = 0;
    for (unsigned i = 240; i < length - 8;) {
        unsigned code = msg[i++];
        if (code == 255) break;
        if (code == 0) continue;
        if (i == length - 8) break;
        unsigned n = msg[i++];
        if (n > length - 8 - i) break;
        if (code == 53 && n == 1) { type = msg[i]; break; }
        i += n;
    }
    wifi_tx_status_t status;
    memcpy(&status, &aio->ret, sizeof(status));
    if (aio->fd == ESP_IF_WIFI_AP && (type == 2 || type == 5) &&
        status.wifi_tx_result >= TX_STATUS_SRC_EXCEED &&
        status.wifi_tx_result <= TX_STATUS_DISCARD && ip[16] < 224 &&
        ip[16] != 0 && !memcmp(msg + 24, "\0\0\0\0", 4)) {
        app_dhcps_note_failure(msg + 4, msg + 28, type);
    }
    ESP_LOGI("dhcps_trace", "wifi_done type=%u xid=%02x%02x%02x%02x "
             "result=%u src=%u lrc=%u rate=%u bytes=%u",
             type, msg[4], msg[5], msg[6], msg[7], status.wifi_tx_result,
             status.wifi_tx_src, status.wifi_tx_lrc, status.wifi_tx_rate, length - 8);
}
