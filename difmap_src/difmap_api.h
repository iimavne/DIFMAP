#ifndef DIFMAP_API_H
#define DIFMAP_API_H

/* Getters (Lecture de la RAM) */
int get_native_no_error(void);
int get_native_map_nx(void);
int get_native_map_ny(void);
char* get_native_source_name(void);
float* get_native_map_data(void);
float* get_native_beam_data(void);
double get_native_bmaj(void);
double get_native_bmin(void);
double get_native_bpa(void);
double get_native_estimated_bmaj(void);
double get_native_estimated_bmin(void);
double get_native_estimated_bpa(void);
double get_native_pixsize(void);

/* Extraction du plan UV */
int l_extract_uv(void);
int get_native_uv_count(void);
float* get_native_u(void);
float* get_native_v(void);
float* get_native_vis_amp(void);
float* get_native_vis_wgt(void);
float* get_native_mod_amp(void);
float* get_native_mod_phs(void);


/* Commandes (Actions) */
int native_observe(const char* filepath);
int native_nsub(void);
int native_select(const char* pol, int if_beg, int if_end, int ch_beg, int ch_end);
int native_set_if_range(int if_beg, int if_end);
int native_get_nif(void);
const char *native_get_header_text(void);

/* Paramètres d'imagerie complets*/
int native_uvweight(float uvbin, float errpow, int dorad);
int native_uvtaper(float gauval, float gaurad_wav);
int native_mapsize(int nx, float cellsize, int ny, float cellsize_y);
int native_invert(void);
int native_clean(int niter, float gain, float cutoff);
int native_clrmod(void);
int native_reset_map_flags(void);
int native_refresh_beam(void);
int native_restore(void);
int native_wfits(const char* filename);

const char* get_observation_polarization(void);

/* Statistiques de la carte courante */
float native_get_peak_flux(void);
float native_get_peak_x(void);
float native_get_peak_y(void);
float native_get_positive_peak_flux(void);
float native_get_positive_peak_x(void);
float native_get_positive_peak_y(void);
float native_get_map_rms(void);

/* Gestion des fenêtres CLEAN */
int native_addwin(float xa, float xb, float ya, float yb);
int native_delwin(void);
int native_peakwin(float size, int doabs);
int native_get_window_count(void);
float native_get_window_xmin(int index);
float native_get_window_xmax(int index);
float native_get_window_ymin(int index);
float native_get_window_ymax(int index);

/* Auto-calibration */
int native_selfcal(int doamp, int dofloat, float solint);

/* Modèle CLEAN — export des composantes */
int    native_extract_model(void);
int    native_get_model_ncmp(void);
float* native_get_model_flux(void);
float* native_get_model_x(void);
float* native_get_model_y(void);
float* native_get_model_major(void);
float* native_get_model_ratio(void);
float* native_get_model_phi(void);
int*   native_get_model_type(void);

int native_cleanup(void);

#endif
