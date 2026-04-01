cdef extern from "difmap_api.h":
    # Getters
    int get_native_no_error()
    int get_native_map_nx()
    int get_native_map_ny()
    char* get_native_source_name()
    float* get_native_map_data()
    float* get_native_beam_data()
    double get_native_bmaj()
    double get_native_bmin()
    double get_native_bpa()
    double get_native_pixsize()

    int l_extract_uv()
    int get_native_uv_count()
    float* get_native_u()
    float* get_native_v()
    float* get_native_vis_amp()
    float* get_native_vis_wgt()

    # Setters / Actions
    int native_observe(const char* filepath)
    int native_nsub()
    int native_select(const char* pol, int if_beg, int if_end, int ch_beg, int ch_end)
    int native_uvweight(float uvbin, float errpow, int dorad)
    int native_uvtaper(float gauval, float gaurad_wav)
    int native_mapsize(int nx, float cellsize)
    int native_invert()

    int native_wfits(const char* filename)