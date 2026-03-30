# binding/difmap_native.pyx

import numpy as np
cimport numpy as np
cimport cdifmap  # Importe tes déclarations depuis cdifmap.pxd

# =====================================================================
# COMMANDES DE BASE (Typage strict et gestion des erreurs)
# =====================================================================

def observe(filepath: str) -> int:
    """Charge un fichier UV FITS dans la mémoire de Difmap."""
    # Encodage sécurisé de la chaîne Python vers const char* C
    cdef bytes filepath_bytes = filepath.encode('utf-8')
    return cdifmap.native_observe(filepath_bytes)

def select(pol: str) -> int:
    """Sélectionne la polarisation (ex: 'I', 'RR', 'LL')."""
    cdef bytes pol_bytes = pol.encode('utf-8')
    return cdifmap.native_select(pol_bytes)

def mapsize(size: int, cellsize: float) -> int:
    """Définit la taille de l'image et du pixel en mas."""
    if size <= 0 or size % 2 != 0:
        print("Avertissement: Difmap préfère des tailles paires (ex: 256, 512).")
    return cdifmap.native_mapsize(size, cellsize)

def invert() -> int:
    """Calcule la Dirty Map (Transformée de Fourier + Gridding)."""
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



def get_uv_data() -> dict:
    """
    Récupère les données de visibilité brutes (Zéro-Copie).
    """
    # 1. On demande combien il y a de points
    cdef int n_pts = cdifmap.get_native_uv_count()
    
    if n_pts <= 0:
        raise RuntimeError("Aucune donnée UV en mémoire. Avez-vous chargé une observation ?")

    # 2. On récupère les pointeurs bruts du C
    cdef float* u_ptr = cdifmap.get_native_u_coords()
    cdef float* v_ptr = cdifmap.get_native_v_coords()
    cdef float* amp_ptr = cdifmap.get_native_vis_amp()
    cdef float* wgt_ptr = cdifmap.get_native_vis_wgt()

    if u_ptr == NULL or v_ptr == NULL or amp_ptr == NULL or wgt_ptr == NULL:
        raise RuntimeError("Erreur interne : Pointeurs UV invalides.")

    # 3. MAGIE ZÉRO-COPIE : On plaque un calque (Memoryview) 1D sur la RAM C
    cdef float[:] u_view = <float[:n_pts]> u_ptr
    cdef float[:] v_view = <float[:n_pts]> v_ptr
    cdef float[:] amp_view = <float[:n_pts]> amp_ptr
    cdef float[:] wgt_view = <float[:n_pts]> wgt_ptr

    # 4. On renvoie le tout empaqueté pour Python
    # np.asarray ne copie pas les données si on lui passe une Memoryview Cython !
    return {
        "u": np.asarray(u_view),
        "v": np.asarray(v_view),
        "amp": np.asarray(amp_view),
        "weight": np.asarray(wgt_view)
    }