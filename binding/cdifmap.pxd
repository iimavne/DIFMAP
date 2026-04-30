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
    float* get_native_vis_phs()

    ############# POLARISATION ######################
    
    const char* get_observation_polarization()

    ###############################

    int l_extract_uv()
    int get_native_uv_count()
    float* get_native_u()
    float* get_native_v()
    float* get_native_vis_amp()
    float* get_native_vis_wgt()
    int* get_native_tel_a()
    int* get_native_tel_b()
    double* get_native_time()
    float* get_native_mod_amp()
    float* get_native_mod_phs()
    int* get_native_subarray()
    const char* get_native_telescope_name(int isub, int itel)
    int* get_native_if()

    # Setters / Actions
    int native_observe(const char* filepath)
    int native_nsub()
    int native_select(const char* pol, int if_beg, int if_end, int ch_beg, int ch_end)
    int native_set_if_range(int if_beg, int if_end)
    int native_get_nif()
    const char *native_get_header_text()
    int native_uvweight(float uvbin, float errpow, int dorad)
    int native_uvtaper(float gauval, float gaurad_wav)
    int native_mapsize(int nx, float cellsize)
    int native_invert()
    int native_clean(int niter, float gain)
    int native_restore()

    int native_wfits(const char* filename)
    int flag_native_data(int *indices, int num_indices)
    int save_native_wobs(const char* filepath)
    int unflag_native_data(int *indices, int num_indices)

    # Statistiques du pic et bruit
    float native_get_peak_flux()
    float native_get_peak_x()
    float native_get_peak_y()
    float native_get_map_rms()

    # Fenêtres CLEAN
    int native_addwin(float xa, float xb, float ya, float yb)
    int native_delwin()
    int native_peakwin(float size, int doabs)

    # Auto-calibration
    int native_selfcal(int doamp, int dofloat, float solint)

    int native_cleanup()
