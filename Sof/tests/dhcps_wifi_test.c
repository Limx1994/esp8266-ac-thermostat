/* Host adapters around the generated SDK callback/transform/output functions. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include "esp_aio.h"

#define ESP_TCP 1
#define ESP_IF_WIFI_AP 1
#define ESP_TCP_TXRX_PBUF_DEBUG 0
#define ETH_PAD_SIZE 0
#define LWIP_STATS 0
#define ERR_OK 0
#define ERR_ARG -16
#define ERR_RTE -4
#define ERR_MEM -1
#define PBUF_FLAG_IS_CUSTOM 2
#define PBUF_RAW 0
#define PBUF_RAM 0
#define ETH_HWADDR_LEN 6
#define LWIP_DEBUGF(flags,args) ((void)0)
#define NETIF_FLAG_LINK_UP 1
#define ETHTYPE_IP 0x800
#define ETHTYPE_IPV6 0x86dd
#define ETHTYPE_ARP 0x806
static uint16_t swap16(uint16_t v) { return (v << 8) | (v >> 8); }
#define htons swap16
struct pbuf { void *payload; uint16_t len, tot_len, ref; unsigned flags; };
struct netif { void *state; bool up; unsigned flags;
               int (*input)(struct pbuf *, struct netif *); };
struct eth_hdr { uint8_t dest[6], src[6]; uint16_t type; };
__WIFI_STATUS__
__WIFI_RESULT__
static bool alloc_fail, alloc_iram;
static int queue_error;
static unsigned frees, live, submits, retries, log_count;
static char logs[1024];
static esp_aio_t pending;
static const void *iram;
static unsigned failures, failed_type;
static uint8_t failed_xid[4], failed_mac[6];
void app_dhcps_note_failure(const uint8_t *xid, const uint8_t *mac, unsigned type) {
    failures++; failed_type=type; memcpy(failed_xid,xid,4); memcpy(failed_mac,mac,6);
}
#define IS_DRAM(p) ((p) != iram)
#define IS_IRAM(p) ((p) == iram)
static void wifi_log(const char *tag, const char *fmt, ...) {
    assert(!strcmp(tag,"dhcps_trace"));
    if (!log_count) logs[0]=0;
    size_t length=strlen(logs);
    va_list args; va_start(args,fmt);
    int n=vsnprintf(logs+length,sizeof(logs)-length,fmt,args);
    assert(n >= 0 && (size_t)n < sizeof(logs)-length-1);
    va_end(args); strcat(logs,"\n"); log_count++;
}
#undef ESP_LOGI
#define ESP_LOGI(tag,...) wifi_log(tag,__VA_ARGS__)
#define ESP_LOGE(tag,...) wifi_log(tag,__VA_ARGS__)
static void pbuf_ref(struct pbuf *p) { assert(p->ref); p->ref++; }
static void pbuf_free(struct pbuf *p) {
    assert(p && p->ref); frees++;
    if (--p->ref == 0) { free(p->payload); free(p); live--; }
}
static struct pbuf *pbuf_alloc(int layer, unsigned len, int type) {
    (void)layer; (void)type;
    if (alloc_fail) return NULL;
    struct pbuf *p = calloc(1,sizeof(*p)); assert(p);
    p->payload = calloc(1,len); assert(p->payload);
    p->len = p->tot_len = len; p->ref = 1; live++;
    if (alloc_iram) iram = p->payload;
    return p;
}
static bool netif_is_up(struct netif *n) { return n->up; }
static bool check_pbuf_to_insert(struct pbuf *p) {
    const uint8_t *b = p->payload;
    return p->len >= 24 && b[12] == 8 && b[13] == 0 && b[23] == 6;
}
static void insert_to_list(int fd, struct pbuf *p) {
    (void)fd; (void)p; retries++;
}
static int ieee80211_output_pbuf(esp_aio_t *aio) {
    assert(!log_count); /* No serial logging before submission. */
    pending = *aio; submits++;
    /* Driver rewrite must not change the logged original Ethernet address. */
    memset((void *)aio->pbuf,0xaa,12);
    return queue_error;
}
static int input_error;
static int receive_input(struct pbuf *p, struct netif *netif) {
    assert(netif && !log_count);
    /* Prove RX logging does not read the frame after ownership handoff. */
    if (!input_error) pbuf_free(p);
    return input_error;
}
#include "__WIFI_WRAPPER__"
__WIFI_CALLBACK__
__WIFI_TRANSFORM__
__WIFI_OUTPUT__
__WIFI_INPUT__

static void put16(uint8_t *b, unsigned v) { b[0]=v>>8; b[1]=v; }
static struct pbuf *reply(unsigned type, bool options) {
    unsigned ihl = options ? 24 : 20;
    struct pbuf *p = pbuf_alloc(0,14+ihl+8+548,0);
    uint8_t *f=p->payload, *ip=f+14, *udp=ip+ihl, *msg=udp+8;
    f[12]=8; ip[0]=0x40+ihl/4; ip[9]=17; ip[6]=0x40;
    ip[16]=192; ip[17]=168; ip[18]=4; ip[19]=2;
    put16(ip+2,ihl+8+548); put16(udp,67); put16(udp+2,68); put16(udp+4,8+548);
    msg[0]=2; msg[4]=0x12; msg[5]=0x34; msg[6]=0x56; msg[7]=0x78;
    const uint8_t mac[] = {2,3,4,5,6,7}; memcpy(msg+28,mac,6); memcpy(f,mac,6);
    const uint8_t opts[] = {99,130,83,99,0,53,1,type,255};
    memcpy(msg+236,opts,sizeof(opts)); return p;
}
static void complete(unsigned result) {
    wifi_tx_status_t status = { .wifi_tx_result=result, .wifi_tx_src=3,
                                .wifi_tx_lrc=5, .wifi_tx_rate=11 };
    memcpy(&pending.ret,&status,sizeof(status));
    unsigned before = frees;
    assert(pending.cb(&pending) == 0 && frees == before+1);
    assert(log_count == 2 && strstr(logs,"xid=12345678"));
    assert(strstr(logs,"l2=02:03:04:05:06:07 chaddr=02:03:04:05:06:07 match=1"));
    char text[32]; snprintf(text,sizeof(text),"result=%u",result);
    assert(strstr(logs,text) && strstr(logs,"src=3 lrc=5 rate=11 bytes=548"));
    assert(!retries);
}
int main(void) {
    struct netif netif = { .state=(void *)1, .up=true, .flags=NETIF_FLAG_LINK_UP,
                           .input=receive_input };
    for (unsigned result=1; result<=4; result++) {
        struct pbuf *p=reply(result==1 ? 2 : 5,result==4);
        log_count=0;
        assert(low_level_output(&netif,p) == ERR_OK && p->ref == 2);
        pbuf_free(p); /* Upper layer can release before driver completion. */
        assert(pending.arg);
        memset(((struct pbuf *)pending.arg)->payload,0xaa,12);
        complete(result); assert(!live);
        assert(failures == (result == 1 ? 0 : result - 1));
        if (result != 1) {
            const uint8_t xid[] = {0x12,0x34,0x56,0x78}, mac[] = {2,3,4,5,6,7};
            assert(failed_type == 5 && !memcmp(failed_xid,xid,4) && !memcmp(failed_mac,mac,6));
        }
    }
    struct pbuf *p=reply(5,false); p->flags=PBUF_FLAG_IS_CUSTOM;
    log_count=0;
    assert(low_level_output(&netif,p) == ERR_OK && p->ref == 1);
    assert(pending.arg != p && live == 2);
    pbuf_free(p); complete(1); assert(!live);
    p=reply(5,false); queue_error=ERR_MEM; log_count=0;
    unsigned before=frees;
    assert(low_level_output(&netif,p) == ERR_MEM && frees == before+1);
    assert(p->ref == 1 && log_count == 1 && strstr(logs,"err=-1")); pbuf_free(p);
    queue_error=0;
    p=reply(5,false); p->flags=PBUF_FLAG_IS_CUSTOM; alloc_fail=true;
    log_count=0; before=submits;
    /* Preserve SDK return value; expose its silent transform drop in logs. */
    assert(low_level_output(&netif,p) == ERR_OK && submits == before);
    assert(log_count == 1 && strstr(logs,"wifi_drop reason=pbuf_transform"));
    assert(p->ref == 1); alloc_fail=false; pbuf_free(p);
    p=reply(5,false); p->flags=PBUF_FLAG_IS_CUSTOM; alloc_iram=true;
    log_count=0; before=submits;
    assert(low_level_output(&netif,p) == ERR_OK && submits == before && live == 1);
    assert(strstr(logs,"wifi_drop")); alloc_iram=false; iram=NULL; pbuf_free(p);
    p=reply(5,false); log_count=0;
    assert(low_level_output(NULL,p) == ERR_ARG && !log_count);
    netif.up=false; assert(low_level_output(&netif,p) == ERR_RTE && p->ref == 1);
    netif.up=true; assert(low_level_output(&netif,p) == ERR_OK);
    pbuf_free(p); complete(1); assert(!live);
    p=reply(5,false); esp_aio_t aio={.arg=p};
    unsigned full=p->len;
    for (unsigned len=0; len<full; len++) {
        p->len=len; log_count=0; dhcps_wifi_done(&aio); assert(!log_count);
    }
    p->len=full;
    uint8_t *ip=(uint8_t *)p->payload+14;
    ip[9]=6; log_count=0; dhcps_wifi_done(&aio); assert(!log_count); ip[9]=17;
    ip[6]=0x20; dhcps_wifi_done(&aio); assert(!log_count); ip[6]=0x40;
    ip[7]=1; dhcps_wifi_done(&aio); assert(!log_count); ip[7]=0;
    uint8_t *udp=ip+20;
    udp[3]=69; dhcps_wifi_done(&aio); assert(!log_count); udp[3]=68;
    put16(udp+4,65535); dhcps_wifi_done(&aio); assert(!log_count);
    put16(udp+4,8+548);
    uint8_t *msg=udp+8;
    msg[236]=0; dhcps_wifi_done(&aio); assert(!log_count); msg[236]=99;
    unsigned before_failures=failures;
    wifi_tx_status_t failed={.wifi_tx_result=TX_STATUS_SRC_EXCEED};
    memcpy(&aio.ret,&failed,sizeof(failed)); aio.fd=ESP_IF_WIFI_AP;
    memset(ip+16,255,4); dhcps_wifi_done(&aio); assert(failures == before_failures);
    ip[16]=192; ip[17]=168; ip[18]=4; ip[19]=2;
    aio.fd=0; dhcps_wifi_done(&aio); assert(failures == before_failures);
    aio.fd=ESP_IF_WIFI_AP; msg[24]=1;
    dhcps_wifi_done(&aio); assert(failures == before_failures); msg[24]=0;
    msg[243]=6; dhcps_wifi_done(&aio); assert(failures == before_failures);
    msg[243]=2; dhcps_wifi_done(&aio); assert(failures == before_failures+1 && failed_type == 2);
    /* Malformed options remain bounded and are reported with unknown type. */
    msg[240]=53; msg[241]=255; put16(udp+4,8+242);
    log_count=0; dhcps_wifi_done(&aio); assert(log_count == 1 && strstr(logs,"type=0"));
    pbuf_free(p); assert(!live && !retries);
    /* Reject every header boundary independently, without passing invalid frames to SDK input. */
    const uint8_t *checked_ip; unsigned checked_length;
    assert(!dhcps_wifi_message(NULL,true,&checked_ip,&checked_length));
    for (unsigned fault=0; fault<10; fault++) {
        p=reply(5,false);
        uint8_t *frame=p->payload, *bad_ip=frame+14, *bad_udp=bad_ip+20;
        void *payload=p->payload;
        switch (fault) {
        case 0: p->payload=NULL; break;
        case 1: frame[12]=0; break;
        case 2: frame[13]=1; break;
        case 3: bad_ip[0]=0x65; break;
        case 4: bad_ip[0]=0x44; break;
        case 5: put16(bad_ip+2,267); break;
        case 6: put16(bad_udp,68); break;
        case 7: put16(bad_udp+4,247); break;
        case 8: bad_udp[8]=1; break;
        case 9: p->len=0; break;
        }
        assert(!dhcps_wifi_message(p,true,&checked_ip,&checked_length));
        p->payload=payload; pbuf_free(p);
    }
    p=reply(5,false);
    struct dhcps_wifi_link link;
    netif.state=NULL; dhcps_wifi_link_save(&link,&netif,p,true); assert(!link.valid);
    netif.state=(void *)ESP_IF_WIFI_AP; p->len=0;
    dhcps_wifi_link_save(&link,&netif,p,true); assert(!link.valid);
    log_count=0; dhcps_wifi_link_log("tx",&link,ERR_OK); assert(!log_count);
    pbuf_free(p);
    const uint8_t option_cases[][5]={{255},{1},{1,1,99,255},{53,2,2,3,255},{0}};
    const unsigned option_lengths[]={1,1,4,5,1};
    for (unsigned test=0; test<5; test++) {
        p=reply(5,false); ip=(uint8_t *)p->payload+14; udp=ip+20; msg=udp+8;
        memcpy(msg+240,option_cases[test],option_lengths[test]);
        put16(udp+4,8+240+option_lengths[test]);
        aio.arg=p; aio.fd=ESP_IF_WIFI_AP; log_count=0; before_failures=failures;
        dhcps_wifi_done(&aio);
        assert(log_count==1 && strstr(logs,"type=0") && failures==before_failures);
        pbuf_free(p);
    }
    for (unsigned fault=0; fault<2; fault++) {
        p=reply(5,false); ip=(uint8_t *)p->payload+14;
        failed.wifi_tx_result=fault==0 ? 99 : TX_STATUS_SRC_EXCEED;
        if (fault==1) ip[16]=0;
        aio.arg=p; memcpy(&aio.ret,&failed,sizeof(failed));
        log_count=0; before_failures=failures; dhcps_wifi_done(&aio);
        assert(log_count==1 && failures==before_failures); pbuf_free(p);
    }
    for (unsigned mismatch=0; mismatch<2; mismatch++) {
        for (unsigned error=0; error<2; error++) {
            p=reply(5,false);
            uint8_t *frame=p->payload, *rx_ip=frame+14, *rx_udp=rx_ip+20;
            memcpy(frame+6,frame,6); if (mismatch) frame[11]++;
            put16(rx_udp,68); put16(rx_udp+2,67); rx_udp[8]=1;
            input_error=error ? ERR_MEM : ERR_OK; log_count=0;
            ethernetif_input(&netif,p);
            assert(!live && log_count == 1 && strstr(logs,"wifi_link dir=rx"));
            assert(strstr(logs,mismatch ? "match=0" : "match=1"));
            assert(strstr(logs,error ? "err=-1" : "err=0"));
        }
    }
    puts("WiFi: actual SDK input/callback/output/transform, MAC match/mismatch and original TX snapshot, async results 1-4, bounded DHCP reader, pbuf ownership, queue/drop errors and recovery passed; failures=0 skipped=0");
    return 0;
}
