/* Load the experimental module and render its paired stream inside libobs. */
#include <obs.h>
#include <util/platform.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    if (!obs_startup("en-US", NULL, NULL)) return 3;
    obs_add_data_path("/Applications/OBS.app/Contents/Frameworks/libobs.framework/Versions/A/Resources");
    struct obs_video_info video = {0};
    video.graphics_module = "/Applications/OBS.app/Contents/Frameworks/libobs-opengl.dylib";
    video.fps_num = 30; video.fps_den = 1;
    video.base_width = video.output_width = 1280;
    video.base_height = video.output_height = 720;
    video.output_format = VIDEO_FORMAT_NV12;
    video.colorspace = VIDEO_CS_709; video.range = VIDEO_RANGE_PARTIAL;
    if (obs_reset_video(&video) != OBS_VIDEO_SUCCESS) { obs_shutdown(); return 4; }
    obs_module_t *module = NULL;
    if (obs_open_module(&module, argv[1], argv[2]) != MODULE_SUCCESS || !obs_init_module(module)) {
        fprintf(stderr, "module load failed\n"); obs_shutdown(); return 5;
    }
    obs_source_t *source = obs_source_create("offleak_gpu_experiment", "gpu test", NULL, NULL);
    if (!source) { fprintf(stderr, "source creation failed\n"); obs_shutdown(); return 6; }
    obs_source_inc_showing(source);
    sleep(2);
    bool passed = false;
    obs_enter_graphics();
    gs_texrender_t *target = gs_texrender_create(GS_RGBA, GS_ZS_NONE);
    gs_stagesurf_t *stage = gs_stagesurface_create(1280, 720, GS_RGBA);
    if (target && stage && gs_texrender_begin(target, 1280, 720)) {
        gs_ortho(0, 1280, 0, 720, -100, 100);
        gs_matrix_identity(); gs_set_cull_mode(GS_NEITHER); gs_enable_blending(false);
        obs_source_video_render(source);
        gs_texrender_end(target);
        gs_stage_texture(stage, gs_texrender_get_texture(target));
        uint8_t *pixels = NULL; uint32_t stride = 0;
        if (gs_stagesurface_map(stage, &pixels, &stride)) {
            unsigned left = pixels[(size_t)360 * stride + 100 * 4];
            unsigned right = pixels[(size_t)360 * stride + 800 * 4];
            unsigned alpha = pixels[(size_t)360 * stride + 100 * 4 + 3];
            printf("source pixels unmasked=%u masked=%u alpha=%u\n", left, right, alpha);
            passed = alpha >= 250 && right > 40 && right < 215;
            gs_stagesurface_unmap(stage);
        }
    }
    uint64_t begin = os_gettime_ns();
    unsigned samples = 0;
    if (passed) {
        for (unsigned i = 0; i < 30; i++) {
            gs_texrender_reset(target);
            if (!gs_texrender_begin(target, 1280, 720)) break;
            gs_ortho(0, 1280, 0, 720, -100, 100);
            gs_matrix_identity(); gs_set_cull_mode(GS_NEITHER); gs_enable_blending(false);
            obs_source_video_render(source);
            gs_texrender_end(target);
            gs_stage_texture(stage, gs_texrender_get_texture(target));
            uint8_t *pixels = NULL; uint32_t stride = 0;
            if (!gs_stagesurface_map(stage, &pixels, &stride)) break;
            gs_stagesurface_unmap(stage);
            samples++;
        }
    }
    double duration = (os_gettime_ns() - begin) / 1e9;
    if (samples) printf("synchronized offscreen renders=%u seconds=%.3f fps=%.2f\n", samples, duration, samples / duration);
    gs_stagesurface_destroy(stage); gs_texrender_destroy(target);
    obs_leave_graphics();
    obs_source_dec_showing(source);
    obs_source_release(source);
    obs_shutdown();
    if (!passed) return 7;
    puts("OBS GPU source rendered a paired synthetic frame");
    return 0;
}
