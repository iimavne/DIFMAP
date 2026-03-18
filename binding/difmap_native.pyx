import numpy as np
cimport numpy as cnp

# INDISPENSABLE POUR EVITER UN CRASH MEMOIRE
cnp.import_array()

cdef extern from "difmap_api.h":
    int get_native_no_error()
    int get_native_map_nx()
    int get_native_map_ny()
    char* get_native_source_name()
    float* get_native_map_data()
    int native_observe(char *name)
    int native_mapsize(int nx, float cellsize)
    int native_invert()
    int native_select(char *polarization)
    float* get_native_beam_data()
    double get_native_bmaj()
    double get_native_bmin()
    double get_native_bpa()
    double get_native_pixsize()

def get_status():
    return get_native_no_error()

def get_width():
    return get_native_map_nx()

def get_source():
    cdef char* name = get_native_source_name()
    return name.decode('utf-8')

def observe(str filepath):
    return native_observe(filepath.encode('utf-8'))

def hello_difmap():
    return "Pont Cython opérationnel : OK"

def test_calcul(int a, int b):
    return a + b

def get_map():
    """
    Récupère la Dirty Map. 
    (Déjà corrigée par la fonction de gridding interne de Difmap).
    """
    cdef int nx = get_native_map_nx()
    cdef int ny = get_native_map_ny()
    cdef float* map_ptr = get_native_map_data()
    
    if map_ptr == NULL:
        return None
        
    cdef float[:, :] view = <float[:ny, :nx]> map_ptr
    return np.fliplr(np.asarray(view)).copy()

def mapsize(int nx, float cellsize):
    return native_mapsize(nx, cellsize)

def invert():
    return native_invert()

def select(polarization: str):
    """Sélectionne la polarisation (ex: 'I', 'RR', 'LL')"""
    return native_select(polarization.encode('utf-8'))

def get_beam():
    """Récupère le Dirty Beam (Zéro-Copie)."""
    cdef int nx = get_native_map_nx()
    cdef int ny = get_native_map_ny()
    cdef float* beam_ptr = get_native_beam_data()
    
    if beam_ptr == NULL:
        return None
        
    cdef float[:, :] view = <float[:ny, :nx]> beam_ptr
    arr = np.asarray(view)
    
    return np.fliplr(arr).copy()

def get_header():
    """
    Récupère les métadonnées scientifiques de l'image actuelle.
    """
    return {
        "BMAJ": get_native_bmaj(),    
        "BMIN": get_native_bmin(),    
        "BPA":  get_native_bpa(),     
        "CDELT": get_native_pixsize(),
        "UNIT": "Jy/beam",
        "NX": get_native_map_nx(),
        "NY": get_native_map_ny()
    }