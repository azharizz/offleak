/* Experimental direct-source filter. Not registered by the installed plugin. */
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
#include <sys/stat.h>

OBS_DECLARE_MODULE()
#ifdef OFFLEAK_DIRECT_TEST
#define OUTPUT_SOCKET "/tmp/offleak-direct-test-output-%u.sock"
#define INPUT_SOCKET "/tmp/offleak-direct-test-input-%u.sock"
#else
#define OUTPUT_SOCKET "/tmp/offleak-direct-output-%u.sock"
#define INPUT_SOCKET "/tmp/offleak-filter-input-%u.sock"
#endif
#define W 1280
#define H 720
#define BYTES ((size_t)W * H * 4)

struct gpu_source {
    obs_source_t *source;
    pthread_t thread;
    pthread_t sender;
    uint8_t *input;
    uint64_t input_sequence;
    gs_texrender_t *capture;
    gs_stagesurf_t *stage;
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
        snprintf(addr.sun_path, sizeof(addr.sun_path), OUTPUT_SOCKET, getuid());
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

static void *send_input(void *arg)
{
    struct gpu_source *s = arg;
    uint8_t *copy = malloc(BYTES);
    if (!copy) return NULL;
    while (!atomic_load(&s->stop)) {
        int fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) break;
        struct timeval timeout = {.tv_sec = 1};
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
        struct sockaddr_un addr = {.sun_family = AF_UNIX};
        snprintf(addr.sun_path, sizeof(addr.sun_path), INPUT_SOCKET, getuid());
        if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
            uint64_t seen = 0;
            while (!atomic_load(&s->stop)) {
                pthread_mutex_lock(&s->lock);
                uint64_t seq = s->input_sequence;
                if (seq != seen) memcpy(copy, s->input, BYTES);
                pthread_mutex_unlock(&s->lock);
                if (seq == seen) { usleep(10000); continue; }
                seen = seq;
                uint32_t header[2] = {htonl(W), htonl(H)};
                size_t offset = 0;
                while (offset < sizeof(header)) {
                    ssize_t n = send(fd, (uint8_t *)header + offset, sizeof(header) - offset, MSG_NOSIGNAL);
                    if (n <= 0) goto disconnected;
                    offset += (size_t)n;
                }
                offset = 0;
                while (offset < BYTES) {
                    ssize_t n = send(fd, copy + offset, BYTES - offset, MSG_NOSIGNAL);
                    if (n <= 0) goto disconnected;
                    offset += (size_t)n;
                }
            }
        }
 disconnected:
        close(fd);
        if (!atomic_load(&s->stop)) usleep(250000);
    }
    free(copy);
    return NULL;
}


static void defaults(obs_data_t *settings)
{
    obs_data_set_default_double(settings, "delay", 5.0);
    obs_data_set_default_int(settings, "fps", 15);
    obs_data_set_default_bool(settings, "worker_enabled", true);
}

static obs_properties_t *properties(void *data)
{
    UNUSED_PARAMETER(data);
    obs_properties_t *p = obs_properties_create();
    obs_properties_add_path(p, "reference", "Face photo to keep visible", OBS_PATH_FILE,
                            "Images (*.png *.jpg *.jpeg *.webp)", NULL);
    obs_properties_add_float(p, "delay", "Lookahead buffer (seconds)", 1.0, 30.0, 1.0);
    obs_properties_add_int(p, "fps", "Processing FPS target", 5, 30, 1);
    obs_properties_add_bool(p, "worker_enabled", "Enable local processing");
    obs_properties_add_text(p, "note", "Experimental: requires the Offleak direct controller running. Changes restart processing; preview goes black.", OBS_TEXT_INFO);
    return p;
}

static void update(void *data, obs_data_t *settings)
{
    UNUSED_PARAMETER(data);
#ifndef OFFLEAK_DIRECT_TEST
    const char *home = getenv("HOME");
    if (!home) return;
    char directory[4096], path[4096];
    if (snprintf(directory, sizeof(directory), "%s/Library/Application Support/obs-studio/plugin_config/offleak-direct", home) >= (int)sizeof(directory)) return;
    if (os_mkdirs(directory) == MKDIR_ERROR) { blog(LOG_ERROR, "Offleak: cannot create settings directory"); return; }
    chmod(directory, 0700);
    if (snprintf(path, sizeof(path), "%s/settings.json", directory) >= (int)sizeof(path)) return;
    if (!obs_data_save_json_safe(settings, path, "tmp", NULL)) blog(LOG_ERROR, "Offleak: cannot save settings");
    else chmod(path, 0600);
#else
    UNUSED_PARAMETER(settings);
#endif
}

static const char *name(void *unused) { UNUSED_PARAMETER(unused); return "Offleak direct filter (experimental)"; }
static void *create(obs_data_t *settings, obs_source_t *source)
{
    struct gpu_source *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->source = source;
    s->frame = malloc(BYTES);
    s->black = calloc(1, BYTES);
    s->input = malloc(BYTES);
    if (s->black) for (size_t i = 3; i < BYTES; i += 4) s->black[i] = 255;
    if (!s->frame || !s->black || !s->input) { free(s->frame); free(s->black); free(s->input); free(s); return NULL; }
    pthread_mutex_init(&s->lock, NULL);
    
    obs_enter_graphics();
    s->effect = obs_get_base_effect(OBS_EFFECT_DEFAULT);
    s->capture = gs_texrender_create(GS_BGRA, GS_ZS_NONE);
    s->stage = gs_stagesurface_create(W, H, GS_BGRA);
    s->texture = gs_texture_create(W, H, GS_BGRA, 1, NULL, GS_DYNAMIC);
    obs_leave_graphics();
    if (!s->effect || !s->texture || !s->capture || !s->stage || pthread_create(&s->thread, NULL, reader, s) != 0) {
        obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics();
        pthread_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s); return NULL;
    }
    if (pthread_create(&s->sender, NULL, send_input, s) != 0) { atomic_store(&s->stop, true); pthread_join(s->thread, NULL); obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics(); pthread_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s); return NULL; }
    update(s, settings);
    return s;
}

static void destroy(void *data)
{
    struct gpu_source *s = data;
    atomic_store(&s->stop, true);
    pthread_join(s->thread, NULL);
    pthread_join(s->sender, NULL);
    obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics();
    pthread_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s);
}

static bool frame_fresh(struct gpu_source *s, uint64_t now)
{
    return s->connected && now >= s->received && now - s->received < 500000000ULL;
}

static void render(void *data, gs_effect_t *unused)
{
    UNUSED_PARAMETER(unused);
    struct gpu_source *s = data;
    obs_source_t *target = obs_filter_get_target(s->source);
    uint32_t width = target ? obs_source_get_base_width(target) : 0;
    uint32_t height = target ? obs_source_get_base_height(target) : 0;
    if (width && height) {
        gs_texrender_reset(s->capture);
        if (gs_texrender_begin(s->capture, W, H)) {
            struct vec4 clear = {0};
            gs_clear(GS_CLEAR_COLOR, &clear, 0, 0);
            gs_ortho(0, W, 0, H, -100, 100);
            gs_matrix_push();
            gs_matrix_scale3f((float)W / width, (float)H / height, 1.0f);
            obs_source_video_render(target);
            gs_matrix_pop();
            gs_texrender_end(s->capture);
            gs_stage_texture(s->stage, gs_texrender_get_texture(s->capture));
            uint8_t *pixels = NULL; uint32_t stride = 0;
            if (gs_stagesurface_map(s->stage, &pixels, &stride)) {
                pthread_mutex_lock(&s->lock);
                for (uint32_t y = 0; y < H; y++) memcpy(s->input + (size_t)y * W * 4, pixels + (size_t)y * stride, W * 4);
                s->input_sequence++;
                pthread_mutex_unlock(&s->lock);
                gs_stagesurface_unmap(s->stage);
            }
        }
    }
    pthread_mutex_lock(&s->lock);
    bool valid = frame_fresh(s, os_gettime_ns());
    gs_texture_set_image(s->texture, valid ? s->frame : s->black, W * 4, false);
    pthread_mutex_unlock(&s->lock);
    gs_effect_set_texture(gs_effect_get_param_by_name(s->effect, "image"), s->texture);
    while (gs_effect_loop(s->effect, "Draw")) gs_draw_sprite(s->texture, 0, W, H);
}

static uint32_t width(void *data) { UNUSED_PARAMETER(data); return W; }
static uint32_t height(void *data) { UNUSED_PARAMETER(data); return H; }
static struct obs_source_info filter = {.id = "offleak_direct_filter_experiment", .type = OBS_SOURCE_TYPE_FILTER,
    .output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW, .get_name = name, .create = create,
    .destroy = destroy, .video_render = render, .get_defaults = defaults, .get_properties = properties, .update = update};
bool obs_module_load(void) { obs_register_source(&filter); return true; }
