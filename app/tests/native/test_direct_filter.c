/* Standalone libobs harness for the experimental direct filter. */
#include <obs.h>
#include <util/platform.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#define W 1920
#define H 1080
static const char *synthetic_name(void *p) { UNUSED_PARAMETER(p); return "synthetic"; }
static void *synthetic_create(obs_data_t *settings, obs_source_t *source)
{
    UNUSED_PARAMETER(settings); UNUSED_PARAMETER(source);
    uint8_t *pixels = malloc((size_t)W * H * 4);
    if (!pixels) return NULL;
    for (size_t i = 0; i < (size_t)W * H; i++) { pixels[i*4] = 255; pixels[i*4+1] = 0; pixels[i*4+2] = 0; pixels[i*4+3] = 255; }
    const uint8_t *data[] = {pixels};
    obs_enter_graphics();
    gs_texture_t *texture = gs_texture_create(W, H, GS_RGBA, 1, data, 0);
    obs_leave_graphics();
    free(pixels);
    return texture;
}
static void synthetic_destroy(void *data) { obs_enter_graphics(); gs_texture_destroy(data); obs_leave_graphics(); }
static void synthetic_render(void *data, gs_effect_t *unused)
{
    UNUSED_PARAMETER(unused);
    gs_effect_t *effect = obs_get_base_effect(OBS_EFFECT_DEFAULT);
    gs_effect_set_texture(gs_effect_get_param_by_name(effect, "image"), data);
    while (gs_effect_loop(effect, "Draw")) gs_draw_sprite(data, 0, W, H);
}
static uint32_t width(void *data) { UNUSED_PARAMETER(data); return W; }
static uint32_t height(void *data) { UNUSED_PARAMETER(data); return H; }
static struct obs_source_info info = {.id="offleak_test_image", .type=OBS_SOURCE_TYPE_INPUT,
    .output_flags=OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW, .get_name=synthetic_name,
    .create=synthetic_create, .destroy=synthetic_destroy, .video_render=synthetic_render,
    .get_width=width, .get_height=height};
int main(int argc, char **argv)
{
    if (argc != 2 || !obs_startup("en-US", NULL, NULL)) return 2;
    obs_add_data_path("/Applications/OBS.app/Contents/Frameworks/libobs.framework/Versions/A/Resources");
    struct obs_video_info v = {0};
    v.graphics_module="/Applications/OBS.app/Contents/Frameworks/libobs-opengl.dylib";
    v.fps_num=30; v.fps_den=1; v.base_width=v.output_width=W; v.base_height=v.output_height=H;
    v.output_format=VIDEO_FORMAT_NV12; v.colorspace=VIDEO_CS_709; v.range=VIDEO_RANGE_PARTIAL;
    if (obs_reset_video(&v) != OBS_VIDEO_SUCCESS) return 3;
    obs_module_t *module = NULL;
    if (obs_open_module(&module, argv[1], ".") != MODULE_SUCCESS || !obs_init_module(module)) return 4;
    obs_register_source(&info);
    obs_source_t *source=obs_source_create("offleak_test_image", "input", NULL, NULL);
    obs_source_t *filter=obs_source_create("offleak_direct_filter_experiment", "filter", NULL, NULL);
    if (!source || !filter) return 5;
    obs_source_filter_add(source, filter);
    obs_source_inc_showing(source);
    int count = getenv("OFFLEAK_DIRECT_LONG") ? 900 : 120;
    for (int n=0; n<count; n++) {
        obs_enter_graphics();
        gs_texrender_t *target=gs_texrender_create(GS_RGBA, GS_ZS_NONE);
        gs_stagesurf_t *stage=gs_stagesurface_create(W,H,GS_RGBA);
        if (target && stage && gs_texrender_begin(target,W,H)) {
            gs_ortho(0,W,0,H,-100,100); gs_matrix_identity(); gs_enable_blending(false);
            obs_source_video_render(source);
            gs_texrender_end(target);
            gs_stage_texture(stage,gs_texrender_get_texture(target));
            uint8_t *pixels=NULL; uint32_t stride=0;
            if (gs_stagesurface_map(stage,&pixels,&stride)) {
                if (n==0 || n==60 || n==119 || (count > 120 && n % 60 == 0)) { size_t i=(size_t)(H - 100)*stride+(W - 100)*4; printf("sample %d %u %u %u %u\n",n,pixels[i],pixels[i+1],pixels[i+2],pixels[i+3]); fflush(stdout); }
                gs_stagesurface_unmap(stage);
            }
        }
        gs_stagesurface_destroy(stage); gs_texrender_destroy(target);
        obs_leave_graphics();
        usleep(33333);
    }
    obs_source_dec_showing(source); obs_source_filter_remove(source,filter);
    obs_source_release(filter); obs_source_release(source); obs_shutdown();
    return 0;
}
