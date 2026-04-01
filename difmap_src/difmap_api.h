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
double get_native_pixsize(void);

/* Extraction du plan UV */
int l_extract_uv(void);
int get_native_uv_count(void);
float* get_native_u(void);
float* get_native_v(void);
float* get_native_vis_amp(void);
float* get_native_vis_wgt(void);

/* Commandes (Actions) */
int native_observe(const char* filepath);
int native_nsub(void);
int native_select(const char* pol, int if_beg, int if_end, int ch_beg, int ch_end);

/* Paramètres d'imagerie complets*/
int native_uvweight(float uvbin, float errpow, int dorad);
int native_uvtaper(float gauval, float gaurad_wav);
int native_mapsize(int nx, float cellsize);
int native_invert(void);
int native_wfits(const char* filename);

#endif