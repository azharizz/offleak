/* Standalone libobs shader compilation check; does not install the plugin. */
#include <obs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc != 2 && argc != 4) return 2;
    if (!obs_startup("en-US", NULL, NULL)) return 3;
    obs_add_data_path("/Applications/OBS.app/Contents/Frameworks/libobs.framework/Versions/A/Resources");
    struct obs_video_info video = {0};
    video.graphics_module = "/Applications/OBS.app/Contents/Frameworks/libobs-opengl.dylib";
    video.fps_num = 30; video.fps_den = 1;
    video.base_width = video.output_width = 1280;
    video.base_height = video.output_height = 720;
    video.output_format = VIDEO_FORMAT_NV12;
    video.colorspace = VIDEO_CS_709;
    video.range = VIDEO_RANGE_PARTIAL;
    int rc = obs_reset_video(&video);
    if (rc != OBS_VIDEO_SUCCESS) { fprintf(stderr, "obs_reset_video failed: %d\n", rc); obs_shutdown(); return 4; }
    obs_enter_graphics();
    char *error = NULL;
    gs_effect_t *effect = gs_effect_create_from_file(argv[1], &error);
    if (!effect) fprintf(stderr, "effect error: %s\n", error ? error : "unknown");
    bool rendered = false;
    if (effect) {
        const uint32_t w = 1280, h = 720;
        uint8_t *pixels = malloc((size_t)w * h * 4);
        if (pixels) {
            for (uint32_t y = 0; y < h; y++) for (uint32_t x = 0; x < w; x++) {
                size_t i = ((size_t)y * w + x) * 4;
                pixels[i] = pixels[i+1] = pixels[i+2] = ((x / 2) % 2) ? 255 : 0;
                pixels[i+3] = x >= w / 2 ? 255 : 0;
            }
            if (argc == 4) {
                FILE *input = fopen(argv[2], "rb");
                if (!input || fread(pixels, 1, (size_t)w * h * 4, input) != (size_t)w * h * 4) {
                    if (input) fclose(input);
                    free(pixels); pixels = NULL;
                } else fclose(input);
            }
            if (!pixels) { gs_effect_destroy(effect); obs_leave_graphics(); obs_shutdown(); return 6; }
            const uint8_t *data[] = {pixels};
            gs_texture_t *texture = gs_texture_create(w, h, GS_RGBA, 1, data, 0);
            gs_texrender_t *target = gs_texrender_create(GS_RGBA, GS_ZS_NONE);
            gs_stagesurf_t *stage = gs_stagesurface_create(w, h, GS_RGBA);
            if (texture && target && stage && gs_texrender_begin(target, w, h)) {
                gs_ortho(0, (float)w, 0, (float)h, -100, 100);
                gs_matrix_identity();
                gs_set_cull_mode(GS_NEITHER);
                gs_enable_blending(false);
                gs_effect_set_texture(gs_effect_get_param_by_name(effect, "image"), texture);
                while (gs_effect_loop(effect, "Draw")) gs_draw_sprite(texture, 0, w, h);
                gs_texrender_end(target);
                gs_stage_texture(stage, gs_texrender_get_texture(target));
                uint8_t *out = NULL; uint32_t stride = 0;
                if (gs_stagesurface_map(stage, &out, &stride)) {
                    unsigned left = out[(size_t)(h / 2) * stride + 100 * 4];
                    unsigned right = out[(size_t)(h / 2) * stride + 800 * 4];
                    unsigned alpha = out[(size_t)(h / 2) * stride + 100 * 4 + 3];
                    printf("unmasked=%u masked=%u alpha=%u\n", left, right, alpha);
                    if (argc == 4) {
                        FILE *output = fopen(argv[3], "wb");
                        if (output) {
                            rendered = true;
                            for (uint32_t row = 0; row < h; row++)
                                if (fwrite(out + (size_t)row * stride, 1, w * 4, output) != w * 4) rendered = false;
                            if (fclose(output) != 0) rendered = false;
                        }
                    } else rendered = alpha >= 250 && right > 40 && right < 215;
                    gs_stagesurface_unmap(stage);
                }
            }
            gs_stagesurface_destroy(stage); gs_texrender_destroy(target); gs_texture_destroy(texture); free(pixels);
        }
    }
    gs_effect_destroy(effect);
    bfree(error);
    obs_leave_graphics();
    obs_shutdown();
    if (!effect || !rendered) return 5;
    puts("GPU effect compiled and rendered");
    return 0;
}
