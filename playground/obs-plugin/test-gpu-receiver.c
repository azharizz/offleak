/* Exercise the GPU source receiver without rendering or exposing real video. */
#include "gpu-prototype.c"
#include <assert.h>

static void write_all(int fd, const uint8_t *p, size_t size)
{
    while (size) {
        ssize_t n = send(fd, p, size, 0);
        assert(n > 0);
        p += n; size -= (size_t)n;
    }
}

static bool connected(struct gpu_source *s)
{
    pthread_mutex_lock(&s->lock);
    bool result = s->connected;
    pthread_mutex_unlock(&s->lock);
    return result;
}

int main(void)
{
    char path[108];
    snprintf(path, sizeof(path), "/tmp/offleak-gpu-%u.sock", getuid());
    int server = socket(AF_UNIX, SOCK_STREAM, 0);
    assert(server >= 0);
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", path);
    /* Refuse to touch a live or stale user socket; this test owns only its new path. */
    assert(bind(server, (struct sockaddr *)&addr, sizeof(addr)) == 0);
    assert(listen(server, 1) == 0);
    struct gpu_source s = {0};
    s.frame = calloc(1, BYTES);
    assert(s.frame);
    assert(pthread_mutex_init(&s.lock, NULL) == 0);
    assert(pthread_create(&s.thread, NULL, reader, &s) == 0);
    int client = accept(server, NULL, NULL);
    assert(client >= 0);
    uint32_t header[2] = {htonl(W), htonl(H)};
    write_all(client, (uint8_t *)header, sizeof(header));
    uint8_t *payload = calloc(1, BYTES);
    assert(payload);
    payload[0] = 42; payload[3] = 255; payload[BYTES - 1] = 7;
    write_all(client, payload, BYTES);
    for (int i = 0; i < 200 && !connected(&s); i++) usleep(10000);
    assert(connected(&s));
    pthread_mutex_lock(&s.lock);
    assert(s.frame[0] == 42 && s.frame[3] == 255 && s.frame[BYTES - 1] == 7);
    assert(frame_fresh(&s, s.received));
    assert(!frame_fresh(&s, s.received + 500000000ULL));
    assert(!frame_fresh(&s, s.received - 1));
    pthread_mutex_unlock(&s.lock);
    close(client);
    for (int i = 0; i < 200 && connected(&s); i++) usleep(10000);
    assert(!connected(&s));
    atomic_store(&s.stop, true);
    pthread_join(s.thread, NULL);
    pthread_mutex_destroy(&s.lock);
    free(payload); free(s.frame);
    close(server); unlink(path);
    puts("GPU receiver paired-frame and disconnect checks passed");
    return 0;
}
