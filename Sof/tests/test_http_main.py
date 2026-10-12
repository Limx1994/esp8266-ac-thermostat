"""Exercise the complete HTTP main source with deterministic socket/task adapters."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "http_main_test"

MOCK = r'''
#pragma once
#include <winsock2.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
/* Match lwIP's bitset FD macros; Windows duplicate/capacity checks are not firmware paths. */
struct mock_fd_set { uint64_t mask; };
#define fd_set struct mock_fd_set
#undef FD_ZERO
#undef FD_SET
#undef FD_ISSET
#define FD_ZERO(set) ((set)->mask=0)
#define FD_SET(fd,set) ((set)->mask |= 1ULL<<(fd))
#define FD_ISSET(fd,set) (((set)->mask & (1ULL<<(fd))) != 0)
typedef int esp_err_t;
typedef int socklen_t;
typedef void *httpd_handle_t;
typedef void (*httpd_work_fn_t)(void *);
enum { ESP_OK, ESP_FAIL, ESP_ERR_INVALID_ARG, ESP_ERR_HTTPD_ALLOC_MEM,
       ESP_ERR_HTTPD_TASK, THREAD_RUNNING, THREAD_STOPPING, THREAD_STOPPED };
typedef struct { int unused; } httpd_uri_t;
struct sock_db { int unused; };
struct resp_hdr { int unused; };
typedef struct {
 unsigned max_uri_handlers, max_open_sockets, max_resp_headers, stack_size, task_priority;
 unsigned short server_port, ctrl_port;
 int backlog_conn, recv_wait_timeout, send_wait_timeout;
 bool lru_purge_enable;
 void *global_user_ctx, *global_transport_ctx;
 void (*global_user_ctx_free_fn)(void *), (*global_transport_ctx_free_fn)(void *);
} httpd_config_t;
struct httpd_data {
 httpd_config_t config;
 httpd_uri_t **hd_calls;
 struct sock_db *hd_sd;
 struct httpd_req_aux { struct resp_hdr *resp_hdrs; } hd_req_aux;
 struct { void *handle; int status; } hd_td;
 int listen_fd, ctrl_fd, msg_fd;
};
static bool opened[64], sessions[64], available=true, pending;
static int next_fd=3, alloc_count, alloc_fail, socket_count, socket_fail;
static int accept_result=20, recv_result, send_result=1, select_result;
static int recv_calls, processed, invalid_deleted, deleted, work_calls, exits;
static int new_result, process_result, task_result, option_result, bind_result, listen_result;
static unsigned long long read_mask;
static unsigned char payload[128];
static bool thread_mode;
static struct httpd_data *live;
#define LOG_FMT(x) x
#define ESP_LOGE(tag, ...) ((void)(tag))
#define ESP_LOGW(tag, ...) ((void)(tag))
#define ESP_LOGD(tag, ...) ((void)(tag))
#define MAX(a,b) ((a)>(b)?(a):(b))
static void *mock_calloc(size_t n,size_t size) {
 if (++alloc_count==alloc_fail) return NULL;
 return calloc(n,size);
}
static int mock_socket(int domain,int type,int protocol) {
 (void)domain; (void)type; (void)protocol;
 if (++socket_count==socket_fail) return -1;
 assert(next_fd<64); opened[next_fd]=true; return next_fd++;
}
static int mock_close(int fd) {
 assert(fd>=0 && fd<64 && opened[fd]); opened[fd]=false; return 0;
}
static int mock_accept(int fd,struct sockaddr *addr,socklen_t *size) {
 (void)fd; (void)addr; (void)size;
 if (accept_result>=0) opened[accept_result]=true;
 return accept_result;
}
static int mock_setsockopt(int fd,int level,int opt,const void *data,int size) {
 (void)fd; (void)level; (void)opt; (void)data; (void)size; return option_result;
}
static int mock_bind(int fd,const struct sockaddr *addr,int size) {
 (void)fd; (void)addr; (void)size; return bind_result;
}
static int mock_listen(int fd,int backlog) { (void)fd; (void)backlog; return listen_result; }
static int mock_recv(int fd,void *data,size_t size,int flags) {
 (void)fd; (void)flags; recv_calls++;
 memcpy(data,payload,size); return recv_result;
}
static int mock_select(int max,fd_set *set,void *w,void *e,void *timeout) {
 (void)max; (void)w; (void)e; (void)timeout;
 FD_ZERO(set);
 for (int fd=0; fd<64; fd++) if (read_mask & (1ULL<<fd)) FD_SET(fd,set);
 if (thread_mode) {
  thread_mode=false; FD_ZERO(set); return 0; /* First iteration continues, second consumes shutdown. */
 }
 return select_result;
}
static int cs_create_ctrl_sock(unsigned short port) { (void)port; return mock_socket(0,0,0); }
static void cs_free_ctrl_sock(int fd) { mock_close(fd); }
static int cs_send_to_ctrl_sock(int fd,unsigned short port,void *data,size_t size) {
 (void)fd; (void)port;
 memcpy(payload,data,size);
 return send_result<0 ? -1 : (send_result==0 ? (int)size-1 : (int)size);
}
static bool httpd_is_sess_available(struct httpd_data *hd) { (void)hd; return available; }
static int httpd_sess_close_lru(struct httpd_data *hd) { (void)hd; return ESP_FAIL; }
static int httpd_sess_new(struct httpd_data *hd,int fd) {
 (void)hd; if (!new_result) sessions[fd]=true; return new_result;
}
static int httpd_sess_iterate(struct httpd_data *hd,int prev) {
 (void)hd;
 for (int fd=prev+1; fd<64; fd++) if (sessions[fd]) return fd;
 return -1;
}
static int httpd_sess_delete(struct httpd_data *hd,int fd) {
 (void)hd; assert(sessions[fd]); sessions[fd]=false; deleted++; return fd-1;
}
static void httpd_sess_set_descriptors(struct httpd_data *hd,fd_set *set,int *max) {
 (void)hd; (void)set; *max=0;
 for (int fd=0; fd<64; fd++) if (sessions[fd]) *max=fd;
}
static void httpd_sess_delete_invalid(struct httpd_data *hd) { (void)hd; invalid_deleted++; }
static bool httpd_sess_pending(struct httpd_data *hd,int fd) { (void)hd; (void)fd; return pending; }
static int httpd_sess_process(struct httpd_data *hd,int fd) {
 (void)hd; (void)fd; processed++; return process_result;
}
static void httpd_sess_init(struct httpd_data *hd) { hd->hd_td.status=THREAD_RUNNING; }
static void httpd_unregister_all_uri_handlers(struct httpd_data *hd) { (void)hd; }
static int httpd_os_thread_create(void **handle,const char *name,unsigned stack,unsigned pri,
                                 void (*fn)(void *),void *arg) {
 (void)handle; (void)name; (void)stack; (void)pri; (void)fn; (void)arg; return task_result;
}
static void httpd_os_thread_delete(void) { exits++; }
static void httpd_os_thread_sleep(unsigned ms);
#define calloc mock_calloc
#define socket mock_socket
#define close mock_close
#define accept mock_accept
#define setsockopt mock_setsockopt
#define bind mock_bind
#define listen mock_listen
#define recv mock_recv
#define select mock_select
'''

TEST = r'''
#include "mock.h"
#include "__SOURCE__"
static void httpd_os_thread_sleep(unsigned ms) {
 assert(ms==100); recv_result=sizeof(struct httpd_ctrl_data);
 read_mask=1ULL<<live->ctrl_fd; select_result=1; httpd_thread(live);
}
static void work(void *arg) { assert(arg==&work_calls); work_calls++; }
static void free_context(void *arg) { free(arg); }
static void reset(void) {
 memset(opened,0,sizeof(opened)); memset(sessions,0,sizeof(sessions));
 next_fd=3; socket_count=alloc_count=0; read_mask=0; pending=false;
}
static void check_closed(void) { for (int fd=0; fd<64; fd++) assert(!opened[fd]); }
int main(void) {
 httpd_config_t cfg={ .max_uri_handlers=2,.max_open_sockets=2,.max_resp_headers=2,
                      .server_port=80,.ctrl_port=32768,.backlog_conn=5 };
 httpd_handle_t handle=NULL;
 assert(httpd_start(NULL,&cfg)==ESP_ERR_INVALID_ARG);
 assert(httpd_start(&handle,NULL)==ESP_ERR_INVALID_ARG);
 assert(httpd_stop(NULL)==ESP_ERR_INVALID_ARG);
 for (alloc_fail=1; alloc_fail<=4; alloc_fail++) {
  reset(); assert(httpd_start(&handle,&cfg)==ESP_ERR_HTTPD_ALLOC_MEM); check_closed();
 }
 alloc_fail=0;
 for (socket_fail=1; socket_fail<=3; socket_fail++) {
  reset(); assert(httpd_start(&handle,&cfg)==ESP_FAIL); check_closed();
 }
 socket_fail=0;
 int *errors[]={&option_result,&bind_result,&listen_result};
 for (unsigned i=0; i<3; i++) {
  reset(); *errors[i]=-1; assert(httpd_start(&handle,&cfg)==ESP_FAIL);
  check_closed(); *errors[i]=0;
 }
 reset(); task_result=ESP_FAIL;
 assert(httpd_start(&handle,&cfg)==ESP_ERR_HTTPD_TASK); check_closed(); task_result=0;
 reset(); assert(httpd_start(&handle,&cfg)==ESP_OK); live=handle;
 assert(httpd_get_global_user_ctx(handle)==NULL && httpd_get_global_transport_ctx(handle)==NULL);
 assert(httpd_queue_work(NULL,work,NULL)==ESP_ERR_INVALID_ARG);
 assert(httpd_queue_work(handle,NULL,NULL)==ESP_ERR_INVALID_ARG);
 send_result=-1; assert(httpd_queue_work(handle,work,&work_calls)==ESP_FAIL);
 assert(httpd_stop(handle)==ESP_FAIL && live->hd_td.status==THREAD_RUNNING);
 send_result=0; assert(httpd_stop(handle)==ESP_FAIL);
 send_result=1; assert(httpd_queue_work(handle,work,&work_calls)==ESP_OK);
 struct httpd_ctrl_data msg={.hc_msg=HTTPD_CTRL_WORK,.hc_work=work,.hc_work_arg=&work_calls};
 memcpy(payload,&msg,sizeof(msg)); recv_result=-1; httpd_process_ctrl_msg(live);
 recv_result=0; httpd_process_ctrl_msg(live);
 recv_result=1; httpd_process_ctrl_msg(live);
 recv_result=sizeof(msg); httpd_process_ctrl_msg(live); assert(work_calls==1);
 msg.hc_work=NULL; memcpy(payload,&msg,sizeof(msg)); httpd_process_ctrl_msg(live);
 msg.hc_msg=(enum httpd_ctrl_msg)99; memcpy(payload,&msg,sizeof(msg)); httpd_process_ctrl_msg(live);
 cfg.lru_purge_enable=true; live->config=cfg; available=false;
 assert(httpd_accept_conn(live,3)==ESP_FAIL && !opened[20]);
 available=true; accept_result=-1; assert(httpd_accept_conn(live,3)==ESP_FAIL);
 accept_result=20; new_result=ESP_FAIL; assert(httpd_accept_conn(live,3)==ESP_FAIL && !opened[20]);
 new_result=0; assert(httpd_accept_conn(live,3)==ESP_OK && sessions[20]);
 httpd_close_all_sessions(live); assert(!sessions[20] && !opened[20]);
 live->config.lru_purge_enable=false;
 select_result=-1; assert(httpd_server(live)==ESP_OK && invalid_deleted==1);
 select_result=0; assert(httpd_server(live)==ESP_OK);
 sessions[7]=sessions[8]=sessions[9]=true; opened[7]=opened[8]=opened[9]=true;
 read_mask=1ULL<<7; assert(httpd_server(live)==ESP_OK && processed==1);
 pending=true; process_result=ESP_FAIL;
 assert(httpd_server(live)==ESP_OK && !sessions[7] && !sessions[8] && !sessions[9]);
 process_result=0; pending=false;
 read_mask=1ULL<<live->listen_fd; accept_result=-1; assert(httpd_server(live)==ESP_OK);
 accept_result=20; assert(httpd_server(live)==ESP_OK && sessions[20]);
 read_mask=1ULL<<live->ctrl_fd; recv_result=0; assert(httpd_server(live)==ESP_OK);
 live->config.global_user_ctx=malloc(1); live->config.global_transport_ctx=malloc(1);
 thread_mode=true; assert(httpd_stop(handle)==ESP_OK && exits==1); check_closed();
 reset(); assert(httpd_start(&handle,&cfg)==ESP_OK); live=handle;
 live->config.global_user_ctx=malloc(1); live->config.global_transport_ctx=malloc(1);
 live->config.global_user_ctx_free_fn=free_context;
 live->config.global_transport_ctx_free_fn=free_context;
 live->listen_fd=10; opened[3]=false; opened[10]=true;
 read_mask=0; assert(httpd_server(live)==ESP_OK); /* Both MAX outcomes. */
 assert(httpd_stop(handle)==ESP_OK); check_closed();
 reset(); assert(httpd_start(&handle,&cfg)==ESP_OK); live=handle;
 mock_close(live->msg_fd); cs_free_ctrl_sock(live->ctrl_fd); mock_close(live->listen_fd);
 live->hd_td.status=THREAD_STOPPED; assert(httpd_stop(handle)==ESP_OK); check_closed();
 puts("HTTP complete source: accept/control/select/session/thread/resource failures passed");
 return 0;
}
'''


def main():
    gcc = shutil.which("gcc")
    if gcc is None:
        raise FileNotFoundError("Full HTTP test requires GCC")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mock.h").write_text(MOCK, encoding="utf-8")
    for name in ("sys/socket.h", "sys/param.h", "esp_log.h", "esp_err.h",
                 "esp_http_server.h", "esp_httpd_priv.h", "ctrl_sock.h"):
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "mock.h"\n', encoding="utf-8")
    source = ROOT / "components/esp_http_server/httpd_main.c"
    path, exe = OUT / "test.c", OUT / "test.exe"
    path.write_text(TEST.replace("__SOURCE__", source.as_posix()), encoding="utf-8")
    subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-sign-compare", "-I", str(OUT), str(path),
                    "-lws2_32", "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
