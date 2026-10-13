r"""Compile actual SDK DHCP code with/without the build-local reply patch.

Run: python tests\test_dhcps.py. Host adapters verify packets, not WiFi delivery.
"""
import os
from pathlib import Path
import shutil
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "dhcps_test"
SDK = Path(os.environ.get("IDF_PATH") or
           ROOT / "vendor/ESP8266_RTOS_SDK")

MOCK = r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef uint8_t u8_t;
typedef uint16_t u16_t;
typedef uint32_t u32_t;
typedef int16_t s16_t;
typedef int err_t;
#define ESP_DHCP 1
#define CONFIG_LWIP_DHCPS_MAX_STATION_NUM 4
#define CONFIG_LWIP_DHCPS_LEASE_UNIT 60
#define ERR_OK 0
#define ERR_MEM -1
#define ERR_IF -12
#define ERR_ARG -16
#define PBUF_TRANSPORT 0
#define PBUF_RAM 0
#define ESP_IF_WIFI_AP 1
#define bzero(p,n) memset(p,0,n)
#define mem_malloc malloc
#define LWIP_MAKEU32(a,b,c,d) (((a)<<24)|((b)<<16)|((c)<<8)|(d))
#define PP_HTONL(v) ((((v)&255)<<24)|(((v)&65280)<<8)|(((v)>>8)&65280)|(((v)>>24)&255))
#define htonl PP_HTONL
static u16_t swap16(u16_t v) { return (v << 8) | (v >> 8); }
#define htons swap16
#define ntohs swap16
typedef struct { u32_t addr; } ip4_addr_t;
typedef ip4_addr_t ip_addr_t;
#define IPADDR4_INIT(v) {v}
#define IP4_ADDR(p,a,b,c,d) ((p)->addr = PP_HTONL(LWIP_MAKEU32(a,b,c,d)))
#define ip_2_ip4(p) (p)
#define ip4_addr_set(p,q) (*(p)=*(q))
#define ip4_addr_isany(p) (!(p)->addr)
#define ip4_addr_isany_val(p) (!(p).addr)
#define ip4_addr1(p) (((const u8_t *)&(p)->addr)[0])
#define ip4_addr2(p) (((const u8_t *)&(p)->addr)[1])
#define ip4_addr3(p) (((const u8_t *)&(p)->addr)[2])
#define ip4_addr4(p) (((const u8_t *)&(p)->addr)[3])
#define IPSTR "%u.%u.%u.%u"
#define IP2STR(p) ip4_addr1(p),ip4_addr2(p),ip4_addr3(p),ip4_addr4(p)
static const ip_addr_t any_ip = {0};
#define IP_ADDR_ANY (&any_ip)
struct udp_pcb { int unused; };
struct eth_addr { u8_t addr[6]; };
struct netif { struct udp_pcb *dhcps_pcb; ip_addr_t ip_addr; };
struct pbuf { struct pbuf *next; void *payload; u16_t len, tot_len, ref; };
typedef struct { ip4_addr_t ip, netmask, gw; } tcpip_adapter_ip_info_t;
static bool alloc_failed, reply_alloc_failed;
static unsigned live_pbufs, sent, assigned, log_count;
static err_t send_error;
static err_t arp_error;
static unsigned arp_calls;
static ip4_addr_t arp_ip, last_dest;
static struct eth_addr arp_mac;
static u16_t request_flags;
static bool request_ci, request_sid = true;
static unsigned request_pad;
static unsigned char wire[2048];
static size_t wire_len;
static char logs[4096];
static unsigned critical_depth;
#define portENTER_CRITICAL() (critical_depth++)
static void exit_critical(void) { assert(critical_depth); critical_depth--; }
#define portEXIT_CRITICAL() exit_critical()
static struct udp_pcb pcb_instance;
err_t app_dhcps_arp_learn(struct netif *netif, const ip4_addr_t *ip,
                         struct eth_addr *mac) {
    assert(netif->dhcps_pcb == &pcb_instance);
    arp_ip = *ip; arp_mac = *mac; arp_calls++; return arp_error;
}
static void (*receive_cb)(void *, struct udp_pcb *, struct pbuf *, const ip_addr_t *, u16_t);
static void trace_log(const char *tag, const char *fmt, ...) {
    assert(!critical_depth);
    assert(strcmp(tag,"dhcps_trace") == 0);
    size_t len = strlen(logs);
    va_list args; va_start(args,fmt);
    int n = vsnprintf(logs+len,sizeof(logs)-len,fmt,args); va_end(args);
    assert(n >= 0 && (size_t)n < sizeof(logs)-len-1);
    strcat(logs,"\n"); log_count++;
}
#define ESP_LOGI(tag,...) trace_log(tag,__VA_ARGS__)
#define ESP_LOGW(tag,...) trace_log(tag,__VA_ARGS__)
static struct pbuf *pbuf_alloc(int layer, u16_t len, int type) {
    (void)layer; (void)type;
    if (alloc_failed) return NULL;
    struct pbuf *p = calloc(1,sizeof(*p)); assert(p);
    p->payload = calloc(1,len); assert(p->payload);
    p->len = p->tot_len = len; p->ref = 1; live_pbufs++; return p;
}
static void pbuf_free(struct pbuf *p) {
    while (p) { struct pbuf *next = p->next; free(p->payload); free(p);
                live_pbufs--; p = next; }
}
static err_t udp_sendto(struct udp_pcb *pcb, struct pbuf *p,
                       const ip_addr_t *dst, u16_t port) {
    assert(pcb == &pcb_instance && port == 68);
    last_dest = *dst;
    if (dst->addr != UINT32_MAX) {
        const u8_t mac[] = {2,3,4,5,6,7};
        assert(arp_ip.addr == dst->addr && !memcmp(arp_mac.addr,mac,6));
    }
    assert(!log_count); /* Serial logs must follow udp_sendto on every reply. */
    wire_len = 0;
    for (struct pbuf *q=p; q; q=q->next) { assert(wire_len+q->len <= sizeof(wire));
        memcpy(wire+wire_len,q->payload,q->len); wire_len += q->len; }
    p->tot_len += 42; /* Actual SDK can leave UDP/IP/Ethernet headers added. */
    sent++; return send_error;
}
static struct udp_pcb *udp_new(void) { return &pcb_instance; }
static void udp_remove(struct udp_pcb *pcb) { assert(pcb == &pcb_instance); }
static void udp_disconnect(struct udp_pcb *pcb) { assert(pcb == &pcb_instance); }
static err_t udp_bind(struct udp_pcb *pcb, const ip_addr_t *ip, u16_t port) {
    assert(pcb == &pcb_instance && ip->addr && port == 67); return ERR_OK;
}
static void udp_recv(struct udp_pcb *pcb,
                     void (*cb)(void *, struct udp_pcb *, struct pbuf *, const ip_addr_t *, u16_t),
                     void *arg) { assert(pcb == &pcb_instance && !arg); receive_cb = cb; }
static void tcpip_adapter_get_ip_info(int iface, tcpip_adapter_ip_info_t *info) {
    assert(iface == ESP_IF_WIFI_AP); IP4_ADDR(&info->gw,192,168,4,1);
}
'''

TEST = r'''
#include "__SOURCE__"
static void on_ack(u8_t ip[4]) {
    const u8_t expected[] = {192,168,4,2};
    assert(memcmp(ip,expected,4) == 0); assigned++;
}
static void request(u8_t type, u8_t last_ip, bool split) {
    struct dhcps_msg m = { .op=1, .htype=1, .hlen=6,
        .xid={0x12,0x34,0x56,0x78}, .chaddr={2,3,4,5,6,7} };
    const u8_t cookie[] = {99,130,83,99};
    m.flags = htons(request_flags);
    if (request_ci) { const u8_t ci[] = {192,168,4,2}; memcpy(m.ciaddr,ci,4); }
    memcpy(m.options,cookie,4);
    u8_t *opt = m.options+4;
    if (request_pad & 1) *opt++=0;
    opt = add_msg_type(opt,type);
    if (request_pad & 2) *opt++=0;
    if (request_pad & 8) *opt++=0;
    if (last_ip) {
        *opt++=50; *opt++=4; *opt++=192; *opt++=168; *opt++=4; *opt++=last_ip;
        if (request_sid) {
            *opt++=54; *opt++=4; *opt++=192; *opt++=168; *opt++=4; *opt++=1;
        }
    }
    if (request_pad & 4) *opt++=0;
    add_end(opt);
    struct pbuf *p = pbuf_alloc(0,split ? 241 : 300,0); assert(p);
    memcpy(p->payload,&m,p->len);
    if (split) {
        p->next = pbuf_alloc(0,300-p->len,0); assert(p->next);
        memcpy(p->next->payload,(u8_t *)&m+p->len,p->next->len);
        p->tot_len = 300;
    }
    logs[0]=0; log_count=0;
    alloc_failed = reply_alloc_failed;
    receive_cb(NULL,&pcb_instance,p,&any_ip,68);
    alloc_failed = false;
    assert(!live_pbufs);
}
static void check_reply(u8_t type, FILE *out) {
    const struct dhcps_msg *m = (const struct dhcps_msg *)wire;
    assert(wire_len == sizeof(*m));
    assert(m->op == 2 && m->options[6] == type);
    assert(m->xid[0] == 0x12 && m->xid[3] == 0x78);
#ifdef TRACE_ENABLED
    assert(m->flags == htons(request_flags));
    bool unicast = type != DHCPNAK && (request_ci || !(request_flags & 0x8000));
    ip4_addr_t expected; IP4_ADDR(&expected,192,168,4,2);
    assert(last_dest.addr == (unicast ? expected.addr : UINT32_MAX));
    assert(log_count == 3 && strstr(logs,"xid=12345678"));
    assert(strstr(logs,"copied=300 cookie=1 options=1"));
    assert(strstr(logs,":68 bytes=548 arp_err=0"));
    assert(strstr(logs,"tx_attempted=1"));
    if (type != DHCPNAK) {
        assert(strstr(logs,"mask=255.255.255.0 gw=192.168.4.1 dns=192.168.4.1 sid=192.168.4.1"));
    }
#else
    assert(m->flags == htons(BOOTP_BROADCAST) && last_dest.addr == UINT32_MAX);
#endif
    /* The intended BOOTP flag changes; all other payload bytes stay identical. */
    u8_t normalized[sizeof(*m)]; memcpy(normalized,wire,sizeof(normalized));
    normalized[10]=normalized[11]=0;
    if (out) assert(fwrite(normalized,1,sizeof(normalized),out) == sizeof(normalized));
}
int main(int argc, char **argv) {
    assert(argc == 2); FILE *out = fopen(argv[1],"wb"); assert(out);
    struct netif netif = {0}; IP4_ADDR(&netif.ip_addr,192,168,4,1);
    dhcps_start(&netif,netif.ip_addr); dhcps_set_new_lease_cb(on_ack);
    request(DHCPDISCOVER,0,false); check_reply(DHCPOFFER,out); assert(!assigned);
    request(DHCPREQUEST,2,true); check_reply(DHCPACK,out); assert(assigned == 1);
    request(DHCPREQUEST,2,false); check_reply(DHCPACK,out); assert(assigned == 2);
    request(DHCPREQUEST,99,false); check_reply(DHCPNAK,out); assert(assigned == 2);
    send_error = ERR_IF;
    request(DHCPREQUEST,2,false); check_reply(DHCPACK,out); assert(assigned == 2);
#ifdef TRACE_ENABLED
    assert(strstr(logs,"err=-12"));
#endif
    unsigned before = sent;
    reply_alloc_failed = true;
    request(DHCPDISCOVER,0,false);
    assert(sent == before && assigned == 2);
#ifdef TRACE_ENABLED
    assert(log_count == 1 && strstr(logs,"rx type=1") && strstr(logs,"tx_attempted=0"));
#endif
    reply_alloc_failed = false;
    send_error = ERR_OK;
    request(DHCPREQUEST,2,false); check_reply(DHCPACK,out); assert(assigned == 3);
    request_flags = BOOTP_BROADCAST;
    unsigned before_arp = arp_calls;
    request(DHCPDISCOVER,0,false); check_reply(DHCPOFFER,out);
    request(DHCPREQUEST,2,false); check_reply(DHCPACK,out); assert(assigned == 4);
    assert(arp_calls == before_arp);
    request_ci = true;
    request(DHCPREQUEST,0,false); check_reply(DHCPACK,out); assert(assigned == 5);
    request_ci = false; request_flags = 0; request_sid = false;
    request(DHCPREQUEST,2,false); check_reply(DHCPACK,out); assert(assigned == 6);
#ifdef TRACE_ENABLED
    assert(strstr(logs,"sid=0.0.0.0")); /* User's INIT-REBOOT request. */
    before = sent; arp_error = ERR_MEM;
    request(DHCPREQUEST,2,false);
    assert(sent == before && assigned == 6 && !live_pbufs);
    assert(strstr(logs,"tx_attempted=0") && strstr(logs,"arp_err=-1 err=-1"));
    arp_error = ERR_OK;
    request(DHCPREQUEST,2,false); assert(sent == before+1 && assigned == 7);
    const u8_t xid[] = {0x12,0x34,0x56,0x78}, mac[] = {2,3,4,5,6,7};
    app_dhcps_note_failure(xid,mac,5);
    before_arp = arp_calls;
    request(DHCPREQUEST,2,false);
    assert(last_dest.addr == UINT32_MAX && arp_calls == before_arp);
    assert(strstr(logs,"fallback=1") && assigned == 8);
    assert(((struct dhcps_msg *)wire)->flags == 0); /* Preserve BOOTP flags. */
    request(DHCPREQUEST,2,false); assert(last_dest.addr != UINT32_MAX && assigned == 9);
    unsigned before_assigned = assigned;
    app_dhcps_note_failure(xid,mac,5); send_error = ERR_IF;
    request(DHCPREQUEST,2,false);
    assert(last_dest.addr == UINT32_MAX && assigned == before_assigned);
    assert(strstr(logs,"err=-12 fallback=1"));
    send_error = ERR_OK;
    request(DHCPREQUEST,2,false);
    assert(last_dest.addr != UINT32_MAX && assigned == before_assigned+1);
    app_dhcps_note_failure(xid,mac,2);
    request(DHCPREQUEST,2,false); assert(last_dest.addr != UINT32_MAX);
    request(DHCPDISCOVER,0,false); assert(last_dest.addr == UINT32_MAX && strstr(logs,"fallback=1"));
    app_dhcps_note_failure(xid,mac,5); app_dhcps_note_failure(xid,mac,5);
    const u8_t other_xid[] = {0x87,0x65,0x43,0x21}, other_mac[] = {2,3,4,5,6,8};
    assert(!dhcps_take_fallback(other_xid,mac,5));
    assert(!dhcps_take_fallback(xid,other_mac,5));
    assert(dhcps_take_fallback(xid,mac,5) && !dhcps_take_fallback(xid,mac,5));
    app_dhcps_note_failure(xid,mac,5); request_ci = true;
    request(DHCPREQUEST,0,false); assert(last_dest.addr != UINT32_MAX);
    request_ci = false; request_flags = BOOTP_BROADCAST;
    request(DHCPREQUEST,2,false); assert(strstr(logs,"fallback=0"));
    request_flags = 0;
    app_dhcps_note_failure(xid,mac,5);
    dhcps_stop(&netif); assert(!plist && !dhcps_retry_active);
    assert(!dhcps_take_fallback(xid,mac,5));
    app_dhcps_note_failure(xid,mac,5); /* Late callback after shutdown ignored. */
    dhcps_start(&netif,netif.ip_addr);
    request(DHCPREQUEST,2,false); assert(last_dest.addr != UINT32_MAX);
    app_dhcps_note_failure(xid,mac,5);
    dhcps_start(&netif,netif.ip_addr); /* Start alone must also clear old records. */
    request(DHCPREQUEST,2,false); assert(last_dest.addr != UINT32_MAX);
    /* Four independent records; capacity eviction is bounded and reported. */
    for (unsigned i=0; i<4; i++) {
        u8_t key[4] = {i,2,3,4}; app_dhcps_note_failure(key,mac,5);
    }
    u8_t newest[4] = {4,2,3,4}; logs[0]=0; log_count=0;
    app_dhcps_note_failure(newest,mac,5);
    assert(strstr(logs,"evicted=1 reason=capacity"));
    for (unsigned i=0; i<5; i++) {
        u8_t key[4] = {i,2,3,4};
        assert(dhcps_take_fallback(key,mac,5) == (i != 0));
    }
    assert(!critical_depth);
    dhcps_retry_reset(true);
    app_dhcps_note_failure(xid,mac,6); /* Unsupported types cannot fill the cache. */
    assert(!dhcps_take_fallback(xid,mac,6));
    app_dhcps_note_failure(xid,mac,5);
    app_dhcps_note_failure(xid,other_mac,5); /* Same XID, different MAC must stay independent. */
    app_dhcps_note_failure(xid,mac,2); /* Same XID/MAC, different reply type. */
    assert(dhcps_take_fallback(xid,other_mac,5));
    assert(dhcps_take_fallback(xid,mac,5));
    assert(dhcps_take_fallback(xid,mac,2));
    /* Exercise the bounded trace reader separately; do not feed invalid packets
       into the SDK's unrelated legacy parser. */
    struct dhcps_msg m = {0}; struct dhcps_trace_data d;
    for (size_t n=0; n <= sizeof(m); n++) dhcps_trace_decode(&d,&m,n);
    const u8_t pad_options[] = {99,130,83,99,0,53,1,3,255};
    memcpy(m.options,pad_options,sizeof(pad_options));
    dhcps_trace_decode(&d,&m,236+sizeof(pad_options));
    assert(d.type == 3 && d.cookie && d.options);
    m.options[4]=50; m.options[5]=250;
    dhcps_trace_decode(&d,&m,242); assert(!d.options);
    dhcps_trace_decode(&d,&m,sizeof(m)+1); /* Clamp oversized reported lengths. */
    m.options[4]=50;
    dhcps_trace_decode(&d,&m,241); assert(!d.options);
    m.options[4]=53; m.options[5]=2; m.options[6]=3; m.options[7]=0;
    dhcps_trace_decode(&d,&m,244); assert(d.type == 0);
    m.options[4]=50; m.options[5]=1; m.options[6]=9;
    dhcps_trace_decode(&d,&m,243); assert(d.req[0] == 0);
    /* Relayed traffic must preserve the destination and skip direct-client ARP learning. */
    memset(&m,0,sizeof(m)); m.op=2; m.giaddr[0]=10;
    const u8_t offer_opts[] = {99,130,83,99,53,1,2,255};
    memcpy(m.options,offer_opts,sizeof(offer_opts));
    struct pbuf *relay=pbuf_alloc(0,sizeof(m),0); memcpy(relay->payload,&m,sizeof(m));
    logs[0]=0; log_count=0; before_arp=arp_calls;
    dhcps_trace_save(&m,sizeof(m),sizeof(m));
    ip_addr_t broadcast={UINT32_MAX};
    assert(dhcps_trace_send(&netif,&pcb_instance,relay,&broadcast,68,&m)==ERR_OK);
    assert(last_dest.addr==UINT32_MAX && arp_calls==before_arp);
    pbuf_free(relay); assert(!live_pbufs);
    /* Legal SELECTING requests: PAD before/between options and before END.
       Keep the unmodified SDK payload comparison limited to common cases. */
    const unsigned pad_cases[] = {2,10,1,4,7};
    request_sid = true;
    dhcps_retry_reset(true);
    for (unsigned i=0; i<sizeof(pad_cases)/sizeof(pad_cases[0]); i++) {
        request_pad = pad_cases[i];
        for (unsigned split=0; split<2; split++) {
            request_flags = split ? BOOTP_BROADCAST : 0;
            unsigned sent_before = sent, assigned_before = assigned;
            request(DHCPREQUEST,2,split != 0);
            assert(sent == sent_before+1);
            check_reply(DHCPACK,NULL);
            assert(assigned == assigned_before+1);
        }
    }
    request_pad = 0; request_flags = 0;
    puts("SDK DHCP PAD: legal SELECTING, consecutive PAD, END, split pbuf and BOOTP flags passed");
#endif
    dhcps_stop(&netif); assert(!plist && !netif.dhcps_pcb);
    fclose(out); puts("SDK DHCP DISCOVER/OFFER, REQUEST/ACK/retry/NAK, send error and cleanup passed");
    return 0;
}
'''


ARP_TEST = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8_t;
typedef int16_t s16_t;
typedef int err_t;
typedef struct { uint32_t addr; } ip4_addr_t;
struct eth_addr { u8_t addr[6]; };
struct netif { u8_t hwaddr_len, hwaddr[6]; };
struct pbuf { int unused; };
enum { ERR_OK=0, ERR_MEM=-1, ERR_ARG=-16 };
enum { ETHARP_STATE_EMPTY=0, ETHARP_STATE_PENDING, ETHARP_STATE_STABLE,
       ETHARP_STATE_STABLE_REREQUESTING_1, ETHARP_STATE_STABLE_REREQUESTING_2 };
#define ETHARP_SUPPORT_STATIC_ENTRIES 0
#define ARP_QUEUEING 0
#define ETHARP_FLAG_TRY_HARD 1
#define ARP_TABLE_SIZE 2
#define ARP_MAXAGE 300
#define ARP_MAXPENDING 5
#define ETH_HWADDR_LEN 6
#define ETHTYPE_IP 0x800
#define LWIP_ASSERT_CORE_LOCKED() ((void)0)
#define LWIP_ASSERT(msg,cond) assert(cond)
#define LWIP_DEBUGF(flags,args) ((void)0)
#define SMEMCPY memcpy
#define ip4_addr_isany(ip) (!(ip)->addr)
#define ip4_addr_isbroadcast(ip,netif) ((void)(netif),(ip)->addr == UINT32_MAX)
#define ip4_addr_ismulticast(ip) (((ip)->addr & 0xf0000000) == 0xe0000000)
#define mib2_add_arp_entry(netif,ip) ((void)0)
static struct {
    u8_t state; unsigned ctime; struct netif *netif;
    ip4_addr_t ipaddr; struct eth_addr ethaddr; struct pbuf *q;
} arp_table[ARP_TABLE_SIZE];
static err_t find_error;
static unsigned frees, outputs, find_calls;
static s16_t etharp_find_entry(const ip4_addr_t *ip, u8_t flags, struct netif *netif) {
    assert(flags == ETHARP_FLAG_TRY_HARD); (void)netif; find_calls++;
    if (find_error) return find_error;
    arp_table[0].ipaddr = *ip; return 0;
}
static void pbuf_free(struct pbuf *p) { assert(p); frees++; }
static void ethernet_output(struct netif *netif, struct pbuf *p,
                            struct eth_addr *src, struct eth_addr *dst, int type) {
    assert(netif && p && src && dst && type == ETHTYPE_IP); outputs++;
}
static void etharp_free_entry(int i) { arp_table[i].state=ETHARP_STATE_EMPTY; }
static void etharp_request(struct netif *netif, const ip4_addr_t *ip) {
    assert(netif && ip);
}
__ARP_UPDATE__
#include "__ARP_WRAPPER__"
__ARP_TIMER__
__ARP_CLEANUP__
int main(void) {
    struct netif netif = { .hwaddr_len=6 };
    ip4_addr_t ip = {0xc0a80402}; struct eth_addr mac = {{2,3,4,5,6,7}};
    struct pbuf queued;
    arp_table[0].q = &queued;
    assert(app_dhcps_arp_learn(&netif,&ip,&mac) == ERR_OK);
    assert(arp_table[0].state == ETHARP_STATE_STABLE && arp_table[0].netif == &netif);
    assert(!memcmp(&arp_table[0].ethaddr,&mac,sizeof(mac)) && !arp_table[0].ctime);
    assert(!arp_table[0].q && frees == 1 && outputs == 1);
    arp_table[0].ctime = 100; mac.addr[5] = 8;
    assert(app_dhcps_arp_learn(&netif,&ip,&mac) == ERR_OK);
    assert(!arp_table[0].ctime && arp_table[0].ethaddr.addr[5] == 8);
    find_error = ERR_MEM;
    assert(app_dhcps_arp_learn(&netif,&ip,&mac) == ERR_MEM);
    find_error = ERR_OK;
    unsigned before = find_calls;
    for (unsigned i=0; i<3; i++) {
        ip4_addr_t invalid = { i==0 ? 0 : i==1 ? UINT32_MAX : 0xe0000001 };
        assert(app_dhcps_arp_learn(&netif,&invalid,&mac) == ERR_ARG);
    }
    assert(find_calls == before);
    for (unsigned i=0; i<ARP_MAXAGE; i++) etharp_tmr();
    assert(arp_table[0].state == ETHARP_STATE_EMPTY);
    assert(app_dhcps_arp_learn(&netif,&ip,&mac) == ERR_OK);
    etharp_cleanup_netif(&netif);
    assert(arp_table[0].state == ETHARP_STATE_EMPTY);
    puts("ARP: actual SDK update/timer/cleanup, dynamic MAC learning, error propagation, expiration and AP cleanup passed; failures=0 skipped=0");
    return 0;
}
'''


def check_arp(gcc):
    source = SDK / "components/lwip/lwip/src/core/ipv4/etharp.c"
    code = source.read_text(encoding="utf-8")
    harness = ARP_TEST.replace("__ARP_WRAPPER__", (ROOT / "tools/dhcps_arp.inc").as_posix())
    for marker, name in [("__ARP_UPDATE__", "etharp_update_arp_entry"),
                         ("__ARP_TIMER__", "etharp_tmr"),
                         ("__ARP_CLEANUP__", "etharp_cleanup_netif")]:
        match = re.search(r"(?:static err_t|void)\n" + name + r"\(.*?\n}\n", code, re.S)
        if not match:
            raise AssertionError(f"SDK ARP {name} 布局不匹配，禁止跳过")
        line = code.count("\n", 0, match.start()) + 1
        harness = harness.replace(marker, f'\n#line {line} "{source.as_posix()}"\n'
                                  + match[0] + '\n#line 1 "arp_harness"\n')
    path, exe = OUT / "arp.c", OUT / "arp.exe"
    path.write_text(harness, encoding="utf-8")
    subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(path), "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=ROOT, check=True)


def check_wifi(gcc):
    source = OUT / "wlanif_dhcps.c"
    code = source.read_text(encoding="utf-8")
    harness = (ROOT / "tests/dhcps_wifi_test.c").read_text(encoding="utf-8")
    harness = harness.replace("__WIFI_WRAPPER__", (ROOT / "tools/dhcps_wifi.inc").as_posix())
    for marker, name in [("__WIFI_CALLBACK__", "low_level_send_cb"),
                         ("__WIFI_TRANSFORM__", "ethernetif_transform_pbuf"),
                         ("__WIFI_OUTPUT__", "low_level_output"),
                         ("__WIFI_INPUT__", "ethernetif_input")]:
        match = re.search(r"(?:static (?:int|int8_t|inline struct pbuf\*)|void) " + name
                          + r"\([^\n]*\)\n\{.*?\n}\n", code, re.S)
        if not match:
            raise AssertionError(f"SDK WiFi {name} 布局不匹配，禁止跳过")
        line = code.count("\n", 0, match.start()) + 1
        harness = harness.replace(marker, f'\n#line {line} "{source.as_posix()}"\n'
                                  + match[0] + '\n#line 1 "wifi_harness"\n')
    # Use the installed SDK's status bitfield definition, not a host facsimile.
    types = (SDK / "components/esp8266/include/esp_wifi_types.h").read_text(encoding="utf-8")
    match = re.search(r"typedef struct \{\n    unsigned wifi_tx_result:.*?} wifi_tx_status_t;", types, re.S)
    if not match:
        raise AssertionError("SDK WiFi status 布局不匹配，禁止跳过")
    harness = harness.replace("__WIFI_STATUS__", match[0])
    match = re.search(r"typedef enum \{\n    TX_STATUS_SUCCESS.*?} wifi_tx_result_t;", types, re.S)
    if not match:
        raise AssertionError("SDK WiFi result 布局不匹配，禁止跳过")
    harness = harness.replace("__WIFI_RESULT__", match[0])
    path, exe = OUT / "wifi.c", OUT / "wifi.exe"
    path.write_text(harness, encoding="utf-8")
    includes = OUT / "wifi_include"
    includes.mkdir(exist_ok=True)
    (includes / "esp_log.h").write_text("/* Logging provided by the harness. */\n", encoding="utf-8")
    subprocess.run([gcc, "-std=c99", "-pedantic-errors", "-Wall", "-Wextra", "-Werror",
                    "-Wno-pointer-to-int-cast", "-I", str(includes),
                    "-I", str(SDK / "components/esp8266/include"),
                    str(path), "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=ROOT, check=True)


def main():
    gcc, cmake = shutil.which("gcc"), shutil.which("cmake")
    if not gcc or not cmake:
        raise FileNotFoundError("DHCP 回归需要主机 GCC 和 CMake，禁止跳过")
    OUT.mkdir(parents=True, exist_ok=True)
    original = SDK / "components/lwip/apps/dhcpserver/dhcpserver.c"
    arp_original = SDK / "components/lwip/lwip/src/core/ipv4/etharp.c"
    wifi_original = SDK / "components/lwip/port/esp8266/netif/wlanif.c"
    runner = OUT / "trace.cmake"
    runner.write_text(f'''
function(idf_component_get_property out)
    set(${{out}} lwip PARENT_SCOPE)
endfunction()
function(get_target_property out)
    set(${{out}} "{original.as_posix()};{arp_original.as_posix()};{wifi_original.as_posix()}" PARENT_SCOPE)
endfunction()
function(set_property)
endfunction()
include("{(ROOT / 'tools/dhcps_trace.cmake').as_posix()}")
''', encoding="utf-8")
    env = dict(os.environ, IDF_PATH=str(SDK))
    subprocess.run([cmake, "-P", str(runner)], cwd=OUT, env=env, check=True)
    generated = OUT / "dhcpserver_trace.c"
    # A different SDK layout must fail visibly, rather than silently omit hooks.
    changed_sdk = OUT / "changed_sdk"
    changed = changed_sdk / "components/lwip/apps/dhcpserver/dhcpserver.c"
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text(original.read_text(encoding="utf-8").replace(
        "    switch (parse_msg(pmsg_dhcps, tlen - 240)) {", "    switch (0) {"),
        encoding="utf-8")
    result = subprocess.run([cmake, "-P", str(runner)], cwd=OUT,
                            env=dict(env, IDF_PATH=str(changed_sdk)),
                            capture_output=True, text=True)
    assert result.returncode != 0 and "refusing trace patch" in result.stderr
    (OUT / "mock.h").write_text(MOCK, encoding="utf-8")
    for name in ["lwip/inet.h", "lwip/err.h", "lwip/pbuf.h", "lwip/udp.h",
                 "lwip/mem.h", "lwip/ip_addr.h", "lwip/etharp.h", "tcpip_adapter.h",
                 "freertos/FreeRTOS.h", "freertos/task.h", "sdkconfig.h", "esp_log.h"]:
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "mock.h"\n', encoding="utf-8")
    for name, source in [("baseline", original), ("traced", generated)]:
        path, exe = OUT / f"{name}.c", OUT / f"{name}.exe"
        path.write_text(TEST.replace("__SOURCE__", source.as_posix()), encoding="utf-8")
        options = ["-DTRACE_ENABLED"] if name == "traced" else []
        subprocess.run([gcc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-sign-compare",
                        "-I", str(OUT), "-I", str(SDK / "components/lwip/include/apps"),
                        "-include", str(OUT / "mock.h"), *options,
                        str(path), "-o", str(exe)], cwd=ROOT, check=True)
        subprocess.run([str(exe), str(OUT / f"{name}.bin")], cwd=ROOT, check=True)
    assert (OUT / "baseline.bin").read_bytes() == (OUT / "traced.bin").read_bytes()
    check_arp(gcc)
    check_wifi(gcc)
    print("DHCP reply: actual CMake/SDK code, unicast/broadcast/renewal/INIT-REBOOT, unchanged options, send/ARP failures, one-shot matching retry fallback, bounded cache and stop/start reset passed; failures=0 skipped=0")


if __name__ == "__main__":
    main()
