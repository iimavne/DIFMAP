#ifndef DIFMAP_API_H
#define DIFMAP_API_H

/* Fonctions pour lire les variables (Getters) */
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


/* Fonctions pour piloter le moteur (Actions) */
int native_observe(char *name);
int native_select(char *polarization);
int native_mapsize(int nx, float cellsize);
int native_invert(void);

/* Fonctions pour extraire les visibilités (UV) en RAM */
int get_native_uv_count(void);         /* Renvoie le nombre total de points */
float* get_native_u_coords(void);      /* Pointeur vers le tableau des U */
float* get_native_v_coords(void);      /* Pointeur vers le tableau des V */
float* get_native_vis_amp(void);       /* Pointeur vers les amplitudes */
float* get_native_vis_wgt(void);       /* Pointeur vers les poids (weights) */
#endif