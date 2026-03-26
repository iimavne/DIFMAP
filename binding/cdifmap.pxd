# binding/cdifmap.pxd

# Déclaration des fonctions externes provenant de mon API C (difmap_api.h)
cdef extern from "difmap_api.h":
    # Fonctions d'action (retournent des codes de statut int)
    int native_observe(const char* filepath)
    int native_select(const char* pol)
    int native_mapsize(int size, float cellsize)
    int native_invert()
    
    # Fonctions de récupération de données (Pointeurs bruts)
    float* get_native_map_data()
    float* get_native_beam_data()
    
    # Fonctions de métadonnées
    float get_native_bmaj()
    float get_native_bmin()
    float get_native_bpa()
    # float get_native_imrms()
    #float get_native_cdelt1()
    #float get_native_cdelt2()
    int   get_native_map_nx()
    int   get_native_map_ny()
    const char* get_native_source_name()