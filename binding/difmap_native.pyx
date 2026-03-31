# binding/difmap_native.pyx

import numpy as np
cimport numpy as np
cimport cdifmap  # Importe tes déclarations depuis cdifmap.pxd

# =====================================================================
# COMMANDES D'OBSERVATION ET D'IMAGERIE
# =====================================================================

def observe(filepath: str) -> int:
    cdef bytes filepath_bytes = filepath.encode('utf-8')
    return cdifmap.native_observe(filepath_bytes)

def select(pol: str, if_beg: int, if_end: int, ch_beg: int, ch_end: int) -> int:
    cdef bytes pol_bytes = pol.encode('utf-8')
    return cdifmap.native_select(pol_bytes, if_beg, if_end, ch_beg, ch_end)

def nsub() -> int:
    return cdifmap.native_nsub()

def uvweight(uvbin: float, errpow: float, dorad: int) -> int:
    return cdifmap.native_uvweight(uvbin, errpow, dorad)

def uvtaper(gauval: float, gaurad_wav: float) -> int:
    return cdifmap.native_uvtaper(gauval, gaurad_wav)

def mapsize(size: int, cellsize: float) -> int:
    return cdifmap.native_mapsize(size, cellsize)

def invert() -> int:
    return cdifmap.native_invert()

# =====================================================================
# EXTRACTION DE DONNÉES (Principe Zero-Copy et Memoryviews)
# =====================================================================

def get_map():
    """Récupère la matrice de l'image (Dirty Map ou Clean Map) sans copie."""
    cdef float* map_ptr = cdifmap.get_native_map_data()
    cdef int nx = cdifmap.get_native_map_nx()
    cdef int ny = cdifmap.get_native_map_ny()
    
    if map_ptr == NULL or nx == 0 or ny == 0:
        raise RuntimeError("Aucune image en mémoire. Avez-vous appelé 'invert()' ?")
    
    # Création du Memoryview direct sur la RAM C
    cdef float[:, :] view = <float[:ny, :nx]> map_ptr
    # Difmap a un axe inversé (RA), on applique fliplr pour s'aligner sur la norme FITS
    return np.fliplr(np.asarray(view))

def get_beam():
    """Récupère la matrice du Dirty Beam sans copie."""
    cdef float* beam_ptr = cdifmap.get_native_beam_data()
    cdef int nx = cdifmap.get_native_map_nx()
    cdef int ny = cdifmap.get_native_map_ny()
    
    if beam_ptr == NULL or nx == 0 or ny == 0:
        raise RuntimeError("Aucun beam en mémoire.")
        
    cdef float[:, :] view = <float[:ny, :nx]> beam_ptr
    return np.fliplr(np.asarray(view))

# =====================================================================
# MÉTADONNÉES (Encapsulation propre)
# =====================================================================

def get_source() -> str:
    """Récupère le nom de la source astronomique observée."""
    cdef const char* name = cdifmap.get_native_source_name()
    if name == NULL:
        return "UNKNOWN"
    return name.decode('utf-8')

def get_header() -> dict:
    """Extrait la taille des pixels (en mas)."""
    return {
        "CDELT": 1.0,  # On utilise 1 car les pixels sont carrés
        "UNIT": "mas",
        "NX": cdifmap.get_native_map_nx(),
        "NY": cdifmap.get_native_map_ny()
    }

def get_beam_info() -> dict:
    """Extrait les paramètres de la fonction de pointage (PSF)."""
    return {
        "BMAJ": cdifmap.get_native_bmaj(),
        "BMIN": cdifmap.get_native_bmin(),
        "BPA": cdifmap.get_native_bpa(),
        "RMS": 0.0
    }
