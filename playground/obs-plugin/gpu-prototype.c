/* Experimental paired-frame/mask GPU source. Not registered by the production plugin. */
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
#include <string.h>

OBS_DECLARE_MODULE()
#define W 1280
#define H 720
#define BYTES ((size_t)W * H * 4)

struct gpu_source {
    obs_source_t *source;
    pthread_t thread;
    pthread_mutex_t lock;
    atomic_bool stop;
    uint8_t *frame;
    uint8_t *black;
    uint64_t received;
    bool connected;
    gs_effect_t *effect;
    gs_texture_t *texture;
};

static bool read_all(int fd, void *buffer, size_t n)
{
    uint8_t *p = buffer;
    while (n) {
        ssize_t got = recv(fd, p, n, 0);
        if (got <= 0) return false;
        p += got; n -= (size_t)got;
    }
    return true;
}

static void *reader(void *arg)
{
    struct gpu_source *s = arg;
    uint8_t *next = malloc(BYTES);
    if (!next) return NULL;
    while (!atomic_load(&s->stop)) {
        int fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) break;
        struct timeval timeout = {.tv_sec = 1};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        struct sockaddr_un addr = {.sun_family = AF_UNIX};
        snprintf(addr.sun_path, sizeof(addr.sun_path), "/tmp/offleak-gpu-%u.sock", getuid());
        if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
            uint32_t header[2];
            while (!atomic_load(&s->stop) && read_all(fd, header, sizeof(header))) {
                if (ntohl(header[0]) != W || ntohl(header[1]) != H || !read_all(fd, next, BYTES)) break;
                pthread_mutex_lock(&s->lock);
                memcpy(s->frame, next, BYTES);
                s->received = os_gettime_ns();
                s->connected = true;
                pthread_mutex_unlock(&s->lock);
            }
        }
        close(fd);
        pthread_mutex_lock(&s->lock);
        s->connected = false;
        pthread_mutex_unlock(&s->lock);
        if (!atomic_load(&s->stop)) usleep(250000);
    }
    free(next);
    return NULL;
}

static const char *name(void *unused) { UNUSED_PARAMETER(unused); return "Offleak GPU experiment (unsafe)"; }
static void *create(obs_data_t *settings, obs_source_t *source)
{
    UNUSED_PARAMETER(settings);
    struct gpu_source *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->source = source;
    s->frame = malloc(BYTES);
    s->black = calloc(1, BYTES);
    if (!s->frame || !s->black) { free(s->frame); free(s->black); free(s); return NULL; }
    pthread_mutex_init(&s->lock, NULL);
    char *path = obs_module_file("gpu-prototype.effect");
    obs_enter_graphics();
    if (path) s->effect = gs_effect_create_from_file(path, NULL);
    s->texture = gs_texture_create(W, H, GS_BGRA, 1, NULL, GS_DYNAMIC);
    obs_leave_graphics();
    bfree(path);
    if (!s->effect || !s->texture || pthread_create(&s->thread, NULL, reader, s) != 0) {
        obs_enter_graphics(); gs_effect_destroy(s->effect); gs_texture_destroy(s->texture); obs_leave_graphics();
        pthread_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s); return NULL;
    }
    return s;
}

static void destroy(void *data)
{
    struct gpu_source *s = data;
    atomic_store(&s->stop, true);
    pthread_join(s->thread, NULL);
    obs_enter_graphics(); gs_effect_destroy(s->effect); gs_texture_destroy(s->texture); obs_leave_graphics();
    pthread_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s);
}

static bool frame_fresh(struct gpu_source *s, uint64_t now)
{
    return s->connected && now >= s->received && now - s->received < 500000000ULL;
}

static void render(void *data, gs_effect_t *unused)
{
    UNUSED_PARAMETER(unused);
    struct gpu_source *s = data;
    pthread_mutex_lock(&s->lock);
    bool valid = frame_fresh(s, os_gettime_ns());
    gs_texture_set_image(s->texture, valid ? s->frame : s->black, W * 4, false);
    pthread_mutex_unlock(&s->lock);
    gs_effect_set_texture(gs_effect_get_param_by_name(s->effect, "image"), s->texture);
    while (gs_effect_loop(s->effect, "Draw")) gs_draw_sprite(s->texture, 0, W, H);
}

static uint32_t width(void *data) { UNUSED_PARAMETER(data); return W; }
static uint32_t height(void *data) { UNUSED_PARAMETER(data); return H; }
static struct obs_source_info info = {.id = "offleak_gpu_experiment", .type = OBS_SOURCE_TYPE_INPUT,
    .output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW, .get_name = name, .create = create,
    .destroy = destroy, .video_render = render, .get_width = width, .get_height = height};
static struct obs_source_info filter = {.id = "offleak_gpu_filter_experiment", .type = OBS_SOURCE_TYPE_FILTER,
    .output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW, .get_name = name, .create = create,
    .destroy = destroy, .video_render = render, .get_width = width, .get_height = height};
bool obs_module_load(void) { obs_register_source(&info); obs_register_source(&filter); return true; }
