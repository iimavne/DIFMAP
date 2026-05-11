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

def cleanup() -> int:
    return cdifmap.native_cleanup()

def select(pol: str, if_beg: int, if_end: int, ch_beg: int, ch_end: int) -> int:
    cdef bytes pol_bytes = pol.encode('utf-8')
    return cdifmap.native_select(pol_bytes, if_beg, if_end, ch_beg, ch_end)

def set_if_range(if_beg: int, if_end: int) -> int:
    """Met à jour la plage d'IFs sans relire le fichier scratch (pas d'ob_select)."""
    return cdifmap.native_set_if_range(if_beg, if_end)

def get_nif() -> int:
    """Retourne le nombre total d'IFs dans l'observation courante."""
    return cdifmap.native_get_nif()

def get_header_text() -> str:
    """Retourne le header complet de l'observation (équivalent commande 'header')."""
    cdef const char *raw = cdifmap.native_get_header_text()
    if raw == NULL:
        return ""
    return raw.decode('utf-8', errors='replace')

def nsub() -> int:
    return cdifmap.native_nsub()

def uvweight(uvbin: float, errpow: float, dorad: int) -> int:
    return cdifmap.native_uvweight(uvbin, errpow, dorad)

def uvtaper(gauval: float, gaurad_wav: float) -> int:
    return cdifmap.native_uvtaper(gauval, gaurad_wav)

def mapsize(size: int, cellsize: float, ny: int = 0, cellsize_y: float = 0.0) -> int:
    return cdifmap.native_mapsize(size, cellsize, ny, cellsize_y)

def invert() -> int:
    return cdifmap.native_invert()

def clean(niter: int, gain: float, cutoff: float = 0.0) -> int:
    """
    Algorithme CLEAN natif.
    
    Parameters
    ----------
    niter : int
        Nombre max d'itérations. Si négatif, arrêt au premier composant négatif.
    gain : float
        Gain de boucle CLEAN (0 < gain < 1).
    cutoff : float
        Seuil de flux résiduel pour arrêt (Jy/beam). 0 = pas de limite.
    """
    cdef int ret = cdifmap.native_clean(niter, gain, cutoff)
    if ret != 0:
        raise RuntimeError("Échec de la déconvolution CLEAN dans le moteur C.")
    return ret

def clrmod() -> int:
    """Vide le modèle CLEAN côté C."""
    return cdifmap.native_clrmod()

def reset_map_flags() -> int:
    """Réinitialise les flags de carte pour permettre un nouveau invert après clrmod."""
    return cdifmap.native_reset_map_flags()

def refresh_beam() -> int:
    """Rafraîchit le faisceau synthétique pour peakwin."""
    return cdifmap.native_refresh_beam()

def restore() -> int:
    cdef int ret = cdifmap.native_restore()
    if ret != 0:
        raise RuntimeError("Échec de la restauration (restore) dans le moteur C.")
    return ret

def wfits(filepath: str) -> int:
    cdef bytes filepath_bytes = filepath.encode('utf-8')
    return cdifmap.native_wfits(filepath_bytes)

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
    """Récupère le nom de la source astronomique observée avec sécurité mémoire."""
    cdef const char* name = cdifmap.get_native_source_name()
    if name == NULL:
        return "UNKNOWN"
        
    # Sécurité anti-segfault : on limite la lecture à 32 octets max (largeur FITS standard)
    cdef bytes raw_bytes = name[:32]
    cdef bytes b_name = raw_bytes.split(b'\x00')[0]
    return b_name.decode('utf-8', errors='replace').strip()

def get_header() -> dict:
    """Extrait la taille des pixels (en mas)."""
    return {
        "CDELT": 1.0,  # On utilise 1 car les pixels sont carrés
        "UNIT": "mas",
        "NX": cdifmap.get_native_map_nx(),
        "NY": cdifmap.get_native_map_ny()
    }

def get_beam_info() -> dict:
    """Extrait les paramètres de la fonction de pointage (PSF) et le bruit de carte."""
    return {
        "BMAJ": cdifmap.get_native_bmaj(),
        "BMIN": cdifmap.get_native_bmin(),
        "BPA": cdifmap.get_native_bpa(),
        "RMS": cdifmap.native_get_map_rms()
    }

def get_estimated_beam_info() -> dict:
    """Extrait le beam estimé par invert(), celui utilisé par peakwin()."""
    return {
        "BMAJ": cdifmap.get_native_estimated_bmaj(),
        "BMIN": cdifmap.get_native_estimated_bmin(),
        "BPA": cdifmap.get_native_estimated_bpa(),
        "RMS": cdifmap.native_get_map_rms()
    }


def get_telescope_name(int isub, int itel) -> str:
    """Demande au moteur C le nom textuel d'une antenne."""
    cdef const char* c_name = cdifmap.get_native_telescope_name(isub, itel)
    
    # Sécurité supplémentaire au cas où le C renvoie NULL
    if c_name == NULL:
        return "INCONNU"
        
    # On force la lecture à 16 octets maximum (taille max d'un nom Difmap)
    # Cela évite de lire le reste de la RAM si le '\0' est manquant en C.
    cdef bytes raw_bytes = c_name[:16]
    
    # On coupe la chaîne au premier caractère nul (s'il existe)
    cdef bytes b_name = raw_bytes.split(b'\x00')[0]
    
    return b_name.decode('utf-8', errors='replace').strip()

def get_uv_data() -> dict:
    """Récupère u, v, amp, weight ET les métadonnées filtrées, incluant le modèle."""
    if cdifmap.l_extract_uv() != 0:
        raise RuntimeError("Erreur lors de l'extraction des données UV.")
        
    cdef int n = cdifmap.get_native_uv_count()
    if n <= 0:
        return {}

    # 1. On récupère TOUS les pointeurs bruts d'abord
    cdef float* u_ptr = cdifmap.get_native_u()
    cdef float* v_ptr = cdifmap.get_native_v()
    cdef float* amp_ptr = cdifmap.get_native_vis_amp()
    cdef float* wgt_ptr = cdifmap.get_native_vis_wgt()
    cdef int* tel_a_ptr = cdifmap.get_native_tel_a()
    cdef int* tel_b_ptr = cdifmap.get_native_tel_b()
    cdef double* time_ptr = cdifmap.get_native_time()
    cdef int* sub_ptr = cdifmap.get_native_subarray()
    cdef int* if_ptr = cdifmap.get_native_if()
    cdef float* phs_ptr = cdifmap.get_native_vis_phs()
    
    # 2. Sécurité anti-Segfault absolue : on s'assure que le C a bien alloué la mémoire
    if u_ptr == NULL or v_ptr == NULL or amp_ptr == NULL or wgt_ptr == NULL or \
       tel_a_ptr == NULL or tel_b_ptr == NULL or time_ptr == NULL or \
       sub_ptr == NULL or if_ptr == NULL or phs_ptr == NULL:
        raise RuntimeError("CRITICAL: Le moteur C a renvoyé un pointeur NULL. Extraction impossible.")

    # 3. Création des Memoryviews (100% sécurisée maintenant)
    cdef float[:] u = <float[:n]> u_ptr
    cdef float[:] v = <float[:n]> v_ptr
    cdef float[:] amp = <float[:n]> amp_ptr
    cdef float[:] wgt = <float[:n]> wgt_ptr
    cdef int[:] tel_a = <int[:n]> tel_a_ptr
    cdef int[:] tel_b = <int[:n]> tel_b_ptr
    cdef double[:] time = <double[:n]> time_ptr
    cdef int[:] subarray = <int[:n]> sub_ptr
    cdef int[:] if_no = <int[:n]> if_ptr
    cdef float[:] phs = <float[:n]> phs_ptr
    
    # 4. Pointeurs optionnels (Modèle - qui sont NULL sur une session vierge)
    cdef float* modamp_ptr = cdifmap.get_native_mod_amp()
    cdef float* modphs_ptr = cdifmap.get_native_mod_phs()
    
    if modamp_ptr != NULL:
        modamp_arr = np.array(<float[:n]> modamp_ptr, copy=True)
    else:
        modamp_arr = np.zeros(n, dtype=np.float32)
        
    if modphs_ptr != NULL:
        modphs_arr = np.array(<float[:n]> modphs_ptr, copy=True)
    else:
        modphs_arr = np.zeros(n, dtype=np.float32)

    return {
        "u": np.array(u, copy=True), 
        "v": np.array(v, copy=True),
        "amp": np.array(amp, copy=True), 
        "weight": np.array(wgt, copy=True),
        "modamp": modamp_arr,
        "modphs": modphs_arr,
        "tel_a": np.array(tel_a, copy=True),
        "tel_b": np.array(tel_b, copy=True),
        "time": np.array(time, copy=True),
        "phase": np.array(phs, copy=True),
        "subarray": np.array(subarray, copy=True),
        "if_no": np.array(if_no, copy=True)
    }

def flag_data(int[:] indices):
        """
        Envoie une liste d'index au moteur C pour marquer ces visibilités comme 'bad'.
        L'action est persistante en RAM pour toute l'observation.
        """
        cdef int num_indices = indices.shape[0]
        if num_indices == 0:
            return 0
            
        # On passe le pointeur du premier élément du tableau Numpy directement au C
        cdef int status = cdifmap.flag_native_data(&indices[0], num_indices)
        
        if status != 0:
            raise RuntimeError("Erreur lors du flagging des données dans le moteur C.")
            
        return num_indices

def unflag_data(int[:] indices):
    cdef int num_indices = indices.shape[0]
    if num_indices == 0: return 0
    cdef int status = cdifmap.unflag_native_data(&indices[0], num_indices)
    return num_indices

def save_wobs(str filepath):
    """Demande au moteur C de sauvegarder l'observation actuelle."""
    # En Cython, il faut encoder la string Python en bytes (UTF-8) pour le C
    cdef bytes filepath_bytes = filepath.encode('utf-8')
    cdef const char* c_filepath = filepath_bytes
    
    cdef int status = cdifmap.save_native_wobs(c_filepath)
    if status != 0:
        raise RuntimeError(f"Erreur lors de la sauvegarde du fichier : {filepath}")
    return True


############# POLARISATION ######################

def get_polarization() -> str:
  """Récupère la polarisation et décode les octets C en string Python."""
  return cdifmap.get_observation_polarization().decode('utf-8')

################################################


# =====================================================================
# STATISTIQUES DU PIC ET DU BRUIT
# =====================================================================

def get_peak_info(bint doabs=True) -> dict:
    """Retourne le pic de flux, sa position et le bruit RMS de la carte courante."""
    cdef float flux
    cdef float x
    cdef float y
    if doabs:
        flux = cdifmap.native_get_peak_flux()
        x = cdifmap.native_get_peak_x()
        y = cdifmap.native_get_peak_y()
    else:
        flux = cdifmap.native_get_positive_peak_flux()
        x = cdifmap.native_get_positive_peak_x()
        y = cdifmap.native_get_positive_peak_y()
    cdef float rms  = cdifmap.native_get_map_rms()
    return {
        "flux": flux,
        "x": x,
        "y": y,
        "rms": rms,
        "snr": flux / rms if rms > 0.0 else 0.0
    }

# =====================================================================
# GESTION DES FENÊTRES CLEAN
# =====================================================================

def addwin(float xa, float xb, float ya, float yb) -> int:
    """Ajoute une fenêtre CLEAN rectangulaire (coordonnées en mas)."""
    cdef int ret = cdifmap.native_addwin(xa, xb, ya, yb)
    if ret != 0:
        raise RuntimeError("Erreur lors de l'ajout d'une fenêtre CLEAN.")
    return ret

def delwin() -> int:
    """Supprime toutes les fenêtres CLEAN."""
    return cdifmap.native_delwin()

def peakwin(float size=1.0, int doabs=0) -> int:
    """Ajoute une fenêtre CLEAN autour du pic de flux (équivalent à 'peakwin' difmap)."""
    cdef int ret = cdifmap.native_peakwin(size, doabs)
    if ret != 0:
        raise RuntimeError("Erreur lors de la création de la fenêtre peakwin.")
    return ret

def get_windows() -> list:
    """Retourne les fenêtres CLEAN natives en mas: [(xmin, xmax, ymin, ymax), ...]."""
    cdef int n = cdifmap.native_get_window_count()
    cdef int i
    windows = []
    for i in range(n):
        windows.append((
            cdifmap.native_get_window_xmin(i),
            cdifmap.native_get_window_xmax(i),
            cdifmap.native_get_window_ymin(i),
            cdifmap.native_get_window_ymax(i),
        ))
    return windows

# =====================================================================
# AUTO-CALIBRATION
# =====================================================================

def get_model_components() -> list:
    """
    Retourne la liste des composantes CLEAN du modèle courant.

    Agrège les composantes de ``vlbob->model`` (établi) et ``vlbob->newmod``
    (tentatives du dernier ``clean()``).

    Returns
    -------
    list of dict
        Chaque dict contient :
        - ``'flux'``  : flux en Jy
        - ``'x'``     : décalage RA en mas (positif = Est)
        - ``'y'``     : décalage Dec en mas (positif = Nord)
        - ``'major'`` : grand axe en mas (0 pour delta)
        - ``'ratio'`` : rapport axial minor/major
        - ``'phi'``   : angle de position en radians (N→E)
        - ``'type'``  : ``'delta'``, ``'gaussian'``, ``'disk'``, etc.
    """
    _TYPE_NAMES = ['delta', 'gaussian', 'disk', 'ellipsoid', 'ring', 'rectangle', 'sz']

    if cdifmap.native_extract_model() != 0:
        return []

    cdef int n = cdifmap.native_get_model_ncmp()
    if n == 0:
        return []

    cdef float* flux  = cdifmap.native_get_model_flux()
    cdef float* x     = cdifmap.native_get_model_x()
    cdef float* y     = cdifmap.native_get_model_y()
    cdef float* major = cdifmap.native_get_model_major()
    cdef float* ratio = cdifmap.native_get_model_ratio()
    cdef float* phi   = cdifmap.native_get_model_phi()
    cdef int*   typ   = cdifmap.native_get_model_type()

    result = []
    for i in range(n):
        t = typ[i]
        result.append({
            'flux':  float(flux[i]),
            'x':     float(x[i]),
            'y':     float(y[i]),
            'major': float(major[i]),
            'ratio': float(ratio[i]),
            'phi':   float(phi[i]),
            'type':  _TYPE_NAMES[t] if 0 <= t < len(_TYPE_NAMES) else 'unknown',
        })
    return result


def selfcal(int doamp=0, int dofloat=0, float solint=0.0) -> int:
    """Applique une auto-calibration (phase seule par défaut, équivalent à 'selfcal' difmap)."""
    cdef int ret = cdifmap.native_selfcal(doamp, dofloat, solint)
    if ret != 0:
        raise RuntimeError("Échec de l'auto-calibration dans le moteur C.")
    return ret


def staper(float gauval=0.0, float gaurad_wav=0.0) -> int:
    """Configure le taper gaussien pour l'auto-calibration (équivalent 'staper' difmap).

    gauval      : amplitude du filtre (0..1). 0 = désactivé.
    gaurad_wav  : rayon en unités UV courantes (Mλ par défaut), identique à uvtaper().
    """
    return cdifmap.native_staper(gauval, gaurad_wav)
