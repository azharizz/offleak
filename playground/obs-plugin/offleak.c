#include <obs-module.h>
#include <util/platform.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <stdatomic.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>

OBS_DECLARE_MODULE()

struct offleak_source {
    obs_source_t *source;
    pthread_t thread;
    atomic_bool stopping;
};

static bool read_all(int fd, void *data, size_t size)
{
    char *p = data;
    while (size) {
        ssize_t n = recv(fd, p, size, 0);
        if (n <= 0) return false;
        p += n;
        size -= (size_t)n;
    }
    return true;
}

static void *receive_frames(void *arg)
{
    struct offleak_source *s = arg;
    while (!atomic_load(&s->stopping)) {
        int fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) break;
        struct timeval timeout = {.tv_sec = 2};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        struct sockaddr_un address = {.sun_family = AF_UNIX};
        snprintf(address.sun_path, sizeof(address.sun_path), "/tmp/offleak-%u.sock", getuid());
        if (connect(fd, (struct sockaddr *)&address, sizeof(address)) == 0) {
            uint32_t header[2];
            while (!atomic_load(&s->stopping) && read_all(fd, header, sizeof(header))) {
                uint32_t width = ntohl(header[0]), height = ntohl(header[1]);
                if (width != 1280 || height != 720) break;
                size_t bytes = (size_t)width * height * 4;
                uint8_t *pixels = malloc(bytes);
                if (!pixels) break;
                if (!read_all(fd, pixels, bytes)) { free(pixels); break; }
                struct obs_source_frame frame = {0};
                frame.data[0] = pixels;
                frame.linesize[0] = width * 4;
                frame.width = width;
                frame.height = height;
                frame.format = VIDEO_FORMAT_BGRA;
                frame.timestamp = os_gettime_ns();
                obs_source_output_video(s->source, &frame);
                free(pixels);
            }
        }
        close(fd);
        obs_source_output_video(s->source, NULL);
        if (!atomic_load(&s->stopping)) usleep(250000);
    }
    return NULL;
}

static const char *source_name(void *unused) { UNUSED_PARAMETER(unused); return "Offleak Redacted Video"; }
static void *source_create(obs_data_t *settings, obs_source_t *source)
{
    UNUSED_PARAMETER(settings);
    struct offleak_source *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->source = source;
    if (pthread_create(&s->thread, NULL, receive_frames, s) != 0) { free(s); return NULL; }
    return s;
}
static void source_destroy(void *data)
{
    struct offleak_source *s = data;
    atomic_store(&s->stopping, true);
    pthread_join(s->thread, NULL);
    free(s);
}
static struct obs_source_info offleak_info = {
    .id = "offleak_redacted_video",
    .type = OBS_SOURCE_TYPE_INPUT,
    .output_flags = OBS_SOURCE_ASYNC_VIDEO,
    .get_name = source_name,
    .create = source_create,
    .destroy = source_destroy,
};
bool obs_module_load(void) { obs_register_source(&offleak_info); return true; }
