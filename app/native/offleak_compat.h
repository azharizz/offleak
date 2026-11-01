/* Platform layer for the Offleak OBS plugins: sockets, threads, sleep, config paths and private files.
 *
 * macOS: user-only Unix sockets in /tmp, POSIX threads/files, ~/Library/Application Support (unchanged behaviour).
 * Windows: Winsock loopback TCP; the worker publishes {"port", "token"} in <config>/<name>.endpoint and the plugin
 * sends the 64-character token first (see app/offleak/pipeline/transport.py). Win32 threads, %APPDATA% config. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <process.h>
#include <io.h>
#include <fcntl.h>
#include <sys/stat.h>

typedef SOCKET ol_socket;
#define OL_INVALID INVALID_SOCKET
#define OL_NOSIGNAL 0
typedef HANDLE ol_thread;
typedef CRITICAL_SECTION ol_mutex;

static inline void ol_mutex_init(ol_mutex *m) { InitializeCriticalSection(m); }
static inline void ol_mutex_lock(ol_mutex *m) { EnterCriticalSection(m); }
static inline void ol_mutex_unlock(ol_mutex *m) { LeaveCriticalSection(m); }
static inline void ol_mutex_destroy(ol_mutex *m) { DeleteCriticalSection(m); }

struct ol_start { void *(*fn)(void *); void *arg; };
static unsigned __stdcall ol_trampoline(void *p)
{
    struct ol_start start = *(struct ol_start *)p;
    free(p);
    start.fn(start.arg);
    return 0;
}
static inline int ol_thread_create(ol_thread *t, void *(*fn)(void *), void *arg)
{
    struct ol_start *start = malloc(sizeof(*start));
    if (!start) return -1;
    start->fn = fn; start->arg = arg;
    *t = (HANDLE)_beginthreadex(NULL, 0, ol_trampoline, start, 0, NULL);
    if (!*t) { free(start); return -1; }
    return 0;
}
static inline void ol_thread_join(ol_thread t) { WaitForSingleObject(t, INFINITE); CloseHandle(t); }
static inline void ol_sleep_ms(unsigned ms) { Sleep(ms); }
static inline void ol_close(ol_socket s) { closesocket(s); }

static inline bool ol_net_init(void)
{
    WSADATA data;
    return WSAStartup(MAKEWORD(2, 2), &data) == 0;
}
static inline void ol_net_cleanup(void) { WSACleanup(); }

static inline bool ol_config_dir(char *out, size_t n)
{
    const char *appdata = getenv("APPDATA");
    return appdata && snprintf(out, n, "%s\\obs-studio\\plugin_config\\offleak-direct", appdata) < (int)n;
}

static inline void ol_private(const char *path) { (void)path; } /* %APPDATA% is already per-user */
static inline void ol_private_file(const char *path) { (void)path; }

static inline int ol_create_private(const char *path)
{
    return _open(path, _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY, _S_IREAD | _S_IWRITE);
}
#define ol_write _write
#define ol_fclose _close
#define ol_unlink _unlink

/* Connect to a Python worker endpoint: read <config>/<name>.endpoint, connect to 127.0.0.1:port, send the token. */
static inline ol_socket ol_connect(const char *name, bool send_timeout)
{
    char dir[1024], path[1200];
    if (!ol_config_dir(dir, sizeof(dir)) || snprintf(path, sizeof(path), "%s\\%s.endpoint", dir, name) >= (int)sizeof(path))
        return OL_INVALID;
    obs_data_t *endpoint = obs_data_create_from_json_file(path);
    if (!endpoint) return OL_INVALID;
    int port = (int)obs_data_get_int(endpoint, "port");
    char token[65] = {0};
    strncpy(token, obs_data_get_string(endpoint, "token"), 64);
    obs_data_release(endpoint);
    if (port <= 0 || port > 65535 || strlen(token) != 64) return OL_INVALID;
    ol_socket s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == OL_INVALID) return OL_INVALID;
    DWORD timeout = 1000;
    setsockopt(s, SOL_SOCKET, send_timeout ? SO_SNDTIMEO : SO_RCVTIMEO, (const char *)&timeout, sizeof(timeout));
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons((u_short)port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) != 0 || send(s, token, 64, 0) != 64) {
        closesocket(s);
        return OL_INVALID;
    }
    return s;
}

#else /* macOS / POSIX */
#include <arpa/inet.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

typedef int ol_socket;
#define OL_INVALID (-1)
#define OL_NOSIGNAL MSG_NOSIGNAL
typedef pthread_t ol_thread;
typedef pthread_mutex_t ol_mutex;

static inline void ol_mutex_init(ol_mutex *m) { pthread_mutex_init(m, NULL); }
static inline void ol_mutex_lock(ol_mutex *m) { pthread_mutex_lock(m); }
static inline void ol_mutex_unlock(ol_mutex *m) { pthread_mutex_unlock(m); }
static inline void ol_mutex_destroy(ol_mutex *m) { pthread_mutex_destroy(m); }
static inline int ol_thread_create(ol_thread *t, void *(*fn)(void *), void *arg) { return pthread_create(t, NULL, fn, arg); }
static inline void ol_thread_join(ol_thread t) { pthread_join(t, NULL); }
static inline void ol_sleep_ms(unsigned ms) { usleep(ms * 1000); }
static inline void ol_close(ol_socket s) { close(s); }
static inline bool ol_net_init(void) { return true; }
static inline void ol_net_cleanup(void) {}

static inline bool ol_config_dir(char *out, size_t n)
{
    const char *home = getenv("HOME");
    return home && snprintf(out, n, "%s/Library/Application Support/obs-studio/plugin_config/offleak-direct", home) < (int)n;
}

static inline void ol_private(const char *path) { chmod(path, 0700); }
static inline void ol_private_file(const char *path) { chmod(path, 0600); }
static inline int ol_create_private(const char *path) { return open(path, O_WRONLY | O_CREAT | O_EXCL, 0600); }
#define ol_write write
#define ol_fclose close
#define ol_unlink unlink

/* Connect to the worker's user-only Unix socket /tmp/<name>-<uid>.sock. */
static inline ol_socket ol_connect(const char *name, bool send_timeout)
{
    ol_socket s = socket(AF_UNIX, SOCK_STREAM, 0);
    if (s < 0) return OL_INVALID;
    struct timeval timeout = {.tv_sec = 1};
    setsockopt(s, SOL_SOCKET, send_timeout ? SO_SNDTIMEO : SO_RCVTIMEO, &timeout, sizeof(timeout));
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    snprintf(addr.sun_path, sizeof(addr.sun_path), "/tmp/%s-%u.sock", name, getuid());
    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        close(s);
        return OL_INVALID;
    }
    return s;
}
#endif
