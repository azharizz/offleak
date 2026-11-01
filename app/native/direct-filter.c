/* Offleak direct filter: sends the filtered source to the local worker and shows only the redacted frames it
 * returns (black until they arrive or when they go stale). macOS and Windows; see offleak_compat.h. */
#include <obs-module.h>
#include "offleak_compat.h" /* before util/platform.h: it declares os_stat(struct stat *) */
#include <util/platform.h>
#include <stdatomic.h>
#include <time.h>

OBS_DECLARE_MODULE()
/* Worker endpoints: /tmp/<name>-<uid>.sock on macOS, <config>/<name>.endpoint on Windows. */
#if defined(_WIN32)
#define OUTPUT_ENDPOINT "direct-output"
#define INPUT_ENDPOINT "filter-input"
#elif defined(OFFLEAK_DIRECT_TEST)
#define OUTPUT_ENDPOINT "offleak-direct-test-output"
#define INPUT_ENDPOINT "offleak-direct-test-input"
#else
#define OUTPUT_ENDPOINT "offleak-direct-output"
#define INPUT_ENDPOINT "offleak-filter-input"
#endif
#define W 1280
#define H 720
#define BYTES ((size_t)W * H * 4)

struct gpu_source {
    obs_source_t *source;
    ol_thread thread;
    ol_thread sender;
    uint8_t *input;
    uint64_t input_sequence;
    gs_texrender_t *capture;
    gs_stagesurf_t *stage;
    ol_mutex lock;
    atomic_bool stop;
    uint8_t *frame;
    uint8_t *black;
    uint64_t received;
    bool connected;
    gs_effect_t *effect;
    gs_texture_t *texture;
    float settings_elapsed;
};

static bool read_all(ol_socket fd, void *buffer, size_t n)
{
    uint8_t *p = buffer;
    while (n) {
        int got = recv(fd, (char *)p, (int)(n > 1048576 ? 1048576 : n), 0);
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
        ol_socket fd = ol_connect(OUTPUT_ENDPOINT, false);
        if (fd != OL_INVALID) {
            uint32_t header[2];
            while (!atomic_load(&s->stop) && read_all(fd, header, sizeof(header))) {
                if (ntohl(header[0]) != W || ntohl(header[1]) != H || !read_all(fd, next, BYTES)) break;
                ol_mutex_lock(&s->lock);
                memcpy(s->frame, next, BYTES);
                s->received = os_gettime_ns();
                s->connected = true;
                ol_mutex_unlock(&s->lock);
            }
            ol_close(fd);
        }
        ol_mutex_lock(&s->lock);
        s->connected = false;
        ol_mutex_unlock(&s->lock);
        if (!atomic_load(&s->stop)) ol_sleep_ms(250);
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
        ol_socket fd = ol_connect(INPUT_ENDPOINT, true);
        if (fd != OL_INVALID) {
            uint64_t seen = 0;
            while (!atomic_load(&s->stop)) {
                ol_mutex_lock(&s->lock);
                uint64_t seq = s->input_sequence;
                if (seq != seen) memcpy(copy, s->input, BYTES);
                ol_mutex_unlock(&s->lock);
                if (seq == seen) { ol_sleep_ms(10); continue; }
                seen = seq;
                uint32_t header[2] = {htonl(W), htonl(H)};
                size_t offset = 0;
                while (offset < sizeof(header)) {
                    int n = send(fd, (const char *)header + offset, (int)(sizeof(header) - offset), OL_NOSIGNAL);
                    if (n <= 0) goto disconnected;
                    offset += (size_t)n;
                }
                offset = 0;
                while (offset < BYTES) {
                    size_t chunk = BYTES - offset > 1048576 ? 1048576 : BYTES - offset;
                    int n = send(fd, (const char *)copy + offset, (int)chunk, OL_NOSIGNAL);
                    if (n <= 0) goto disconnected;
                    offset += (size_t)n;
                }
            }
        }
 disconnected:
        if (fd != OL_INVALID) ol_close(fd);
        if (!atomic_load(&s->stop)) ol_sleep_ms(250);
    }
    free(copy);
    return NULL;
}


static void defaults(obs_data_t *settings)
{
    obs_data_set_default_double(settings, "delay", 5.0);
    obs_data_set_default_int(settings, "fps", 15);
    obs_data_set_default_bool(settings, "worker_enabled", true);
    obs_data_set_default_bool(settings, "face_enabled", true);
    obs_data_set_default_bool(settings, "qr_enabled", true);
    obs_data_set_default_bool(settings, "phone_enabled", true);
}

/* All faces detected in the captured reference are enrolled. */
static bool capture_reference(obs_properties_t *props, obs_property_t *property, void *data)
{
    UNUSED_PARAMETER(props); UNUSED_PARAMETER(property);
    struct gpu_source *s = data;
    char config[3072], directory[4096], path[4096];
    if (!ol_config_dir(config, sizeof(config))) return false;
    if (snprintf(directory, sizeof(directory), "%s/faces", config) >= (int)sizeof(directory)) return false;
    if (os_mkdirs(directory) == MKDIR_ERROR) return false;
    ol_private(directory);
    if (snprintf(path, sizeof(path), "%s/face-%llu.bmp", directory, (unsigned long long)os_gettime_ns()) >= (int)sizeof(path)) return false;
    uint8_t *pixels = malloc(BYTES);
    if (!pixels) return false;
    ol_mutex_lock(&s->lock);
    bool available = s->input_sequence != 0;
    if (available) memcpy(pixels, s->input, BYTES);
    ol_mutex_unlock(&s->lock);
    if (!available) { free(pixels); blog(LOG_WARNING, "Offleak: no webcam frame available"); return false; }
    int fd = ol_create_private(path);
    if (fd < 0) { free(pixels); return false; }
    uint8_t header[54] = {0x42, 0x4d};
    uint32_t file_size = (uint32_t)BYTES + 54, offset = 54, dib = 40, width = W, height = (uint32_t)-(int32_t)H, image_size = BYTES;
    uint16_t planes = 1, bpp = 32;
    memcpy(header+2, &file_size, 4); memcpy(header+10, &offset, 4); memcpy(header+14, &dib, 4);
    memcpy(header+18, &width, 4); memcpy(header+22, &height, 4); memcpy(header+26, &planes, 2);
    memcpy(header+28, &bpp, 2); memcpy(header+34, &image_size, 4);
    bool ok = ol_write(fd, header, sizeof(header)) == sizeof(header);
    size_t pos = 0;
    while (ok && pos < BYTES) { int n = (int)ol_write(fd, pixels + pos, (unsigned)(BYTES - pos)); if (n <= 0) ok = false; else pos += (size_t)n; }
    ol_fclose(fd); free(pixels);
    if (!ok) { ol_unlink(path); return false; }
    obs_data_t *settings = obs_source_get_settings(s->source);
    obs_data_array_t *list = obs_data_get_array(settings, "references");
    if (!list) list = obs_data_array_create();
    obs_data_t *entry = obs_data_create();
    obs_data_set_string(entry, "value", path);
    obs_data_array_push_back(list, entry);
    obs_data_set_array(settings, "references", list);
    obs_data_release(entry); obs_data_array_release(list);
    obs_source_update(s->source, settings);
    obs_data_release(settings);
    return true;
}

static obs_properties_t *properties(void *data)
{
    obs_properties_t *p = obs_properties_create();
    obs_properties_add_path(p, "reference", "Existing face photo (optional)", OBS_PATH_FILE,
                            "Images (*.png *.jpg *.jpeg *.webp *.bmp)", NULL);
    obs_properties_add_editable_list(p, "references", "Additional people to keep visible", OBS_EDITABLE_LIST_TYPE_FILES,
                                     "Images (*.png *.jpg *.jpeg *.webp *.bmp)", NULL);
    obs_properties_add_button2(p, "capture", "Add people from webcam (all detected faces)", capture_reference, data);
    obs_properties_add_float(p, "delay", "Lookahead buffer (seconds)", 1.0, 30.0, 1.0);
    obs_properties_add_int(p, "fps", "Processing FPS target (experimental)", 5, 60, 1);
    obs_properties_add_bool(p, "worker_enabled", "Enable local processing");
    obs_properties_add_bool(p, "face_enabled", "Blur faces (except selected people)");
    obs_properties_add_bool(p, "qr_enabled", "Blur QR codes");
    obs_properties_add_bool(p, "phone_enabled", "Blur phone numbers");
    obs_properties_add_text(p, "note", "Experimental: requires the Offleak direct controller running. Changes restart processing; preview goes black.", OBS_TEXT_INFO);
    return p;
}

static void update(void *data, obs_data_t *settings)
{
    UNUSED_PARAMETER(data);
#ifndef OFFLEAK_DIRECT_TEST
    char directory[4096], path[4096];
    if (!ol_config_dir(directory, sizeof(directory))) return;
    if (os_mkdirs(directory) == MKDIR_ERROR) { blog(LOG_ERROR, "Offleak: cannot create settings directory"); return; }
    ol_private(directory);
    if (snprintf(path, sizeof(path), "%s/settings.json", directory) >= (int)sizeof(path)) return;
    if (!obs_data_save_json_safe(settings, path, "tmp", NULL)) blog(LOG_ERROR, "Offleak: cannot save settings");
    else ol_private_file(path);
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
    ol_mutex_init(&s->lock);
    
    obs_enter_graphics();
    s->effect = obs_get_base_effect(OBS_EFFECT_DEFAULT);
    s->capture = gs_texrender_create(GS_BGRA, GS_ZS_NONE);
    s->stage = gs_stagesurface_create(W, H, GS_BGRA);
    s->texture = gs_texture_create(W, H, GS_BGRA, 1, NULL, GS_DYNAMIC);
    obs_leave_graphics();
    if (!s->effect || !s->texture || !s->capture || !s->stage || ol_thread_create(&s->thread, reader, s) != 0) {
        obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics();
        ol_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s); return NULL;
    }
    if (ol_thread_create(&s->sender, send_input, s) != 0) { atomic_store(&s->stop, true); ol_thread_join(s->thread); obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics(); ol_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s); return NULL; }
    update(s, settings);
    return s;
}

static void destroy(void *data)
{
    struct gpu_source *s = data;
    atomic_store(&s->stop, true);
    ol_thread_join(s->thread);
    ol_thread_join(s->sender);
    obs_enter_graphics(); gs_texrender_destroy(s->capture); gs_stagesurface_destroy(s->stage); gs_texture_destroy(s->texture); obs_leave_graphics();
    ol_mutex_destroy(&s->lock); free(s->frame); free(s->black); free(s->input); free(s);
}

static void tick(void *data, float seconds)
{
#ifndef OFFLEAK_DIRECT_TEST
    struct gpu_source *s = data;
    s->settings_elapsed += seconds;
    if (s->settings_elapsed < 0.5f) return;
    s->settings_elapsed = 0;
    char directory[3072], path[4096];
    if (!ol_config_dir(directory, sizeof(directory))) return;
    if (snprintf(path, sizeof(path), "%s/settings.json", directory) >= (int)sizeof(path)) return;
    obs_data_t *incoming = obs_data_create_from_json_file(path);
    if (!incoming) return;
    obs_data_t *current = obs_source_get_settings(s->source);
    const char *incoming_json = obs_data_get_json(incoming);
    const char *current_json = obs_data_get_json(current);
    bool changed = incoming_json && current_json && strcmp(incoming_json, current_json) != 0;
    bool capture = *obs_data_get_string(incoming, "capture_request") != 0;
    if (capture) obs_data_set_string(incoming, "capture_request", "");
    if (changed) obs_source_update(s->source, incoming);
    obs_data_release(current);
    obs_data_release(incoming);
    if (capture) capture_reference(NULL, NULL, s);
#else
    UNUSED_PARAMETER(data); UNUSED_PARAMETER(seconds);
#endif
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
                ol_mutex_lock(&s->lock);
                for (uint32_t y = 0; y < H; y++) memcpy(s->input + (size_t)y * W * 4, pixels + (size_t)y * stride, W * 4);
                s->input_sequence++;
                ol_mutex_unlock(&s->lock);
                gs_stagesurface_unmap(s->stage);
            }
        }
    }
    ol_mutex_lock(&s->lock);
    bool valid = frame_fresh(s, os_gettime_ns());
    gs_texture_set_image(s->texture, valid ? s->frame : s->black, W * 4, false);
    ol_mutex_unlock(&s->lock);
    gs_effect_set_texture(gs_effect_get_param_by_name(s->effect, "image"), s->texture);
    while (gs_effect_loop(s->effect, "Draw")) gs_draw_sprite(s->texture, 0, width, height);
}

static struct obs_source_info filter = {.id = "offleak_direct_filter_experiment", .type = OBS_SOURCE_TYPE_FILTER,
    .output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW, .get_name = name, .create = create,
    .destroy = destroy, .video_render = render, .video_tick = tick, .get_defaults = defaults, .get_properties = properties, .update = update};
bool obs_module_load(void)
{
    if (!ol_net_init()) return false;
    obs_register_source(&filter);
    return true;
}
void obs_module_unload(void) { ol_net_cleanup(); }
