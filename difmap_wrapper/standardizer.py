import numpy as np
from astropy.io import fits
import difmap_native

def extract_uvfits_standardized(filepath: str) -> dict:
    """
        Extrait et standardise les visibilités depuis un fichier FITS de référence.

        Cette fonction lit un fichier UVFITS, applique les corrections complexes 
        de fréquences multi-IF (via la table AIPS FQ), et convertit les coordonnées 
        spatiales en longueurs d'onde. Les données sont ensuite alignées par un 
        tri lexicographique absolu pour garantir une comparaison parfaite.

        Parameters
        ----------
        filepath : str
            Le chemin absolu ou relatif vers le fichier UVFITS à analyser.

        Returns
        -------
        dict
            Un dictionnaire contenant les tableaux Numpy triés :
            - 'u' : Coordonnées U en longueurs d'onde (λ).
            - 'v' : Coordonnées V en longueurs d'onde (λ).
            - 'amp' : Amplitudes des visibilités (Jy).
            - 'uv_radius' : Rayon UV en Méga-longueurs d'onde (Mλ).

        Examples
        --------
        >>> from difmap_wrapper import standardizer
        >>> data_fits = standardizer.extract_uvfits_standardized("reference.fits")
        >>> print(data_fits['uv_radius'].max())
        """
    with fits.open(filepath) as hdul:
        d = hdul[0].data
        h = hdul[0].header
        
        # 1. Extraction des véritables fréquences via l'extension binaire FITS
        fq_data = hdul['AIPS FQ'].data
        if_offsets = fq_data['IF FREQ'][0]
        freqs = h['CRVAL4'] + if_offsets
        
        # 2. Conversion spatio-fréquentielle (Sec -> Longueurs d'onde)
        u_2d = d['UU'][:, None] * freqs[None, :]
        v_2d = d['VV'][:, None] * freqs[None, :]
        
        # 3. Extraction des amplitudes et filtrage des visibilités supprimées (poids = 0)
        d_sq = d['DATA'].squeeze()
        amp_2d = np.sqrt(d_sq[..., 0]**2 + d_sq[..., 1]**2)
        masque = d_sq[..., 2] > 0
        
        u, v, amp = u_2d[masque], v_2d[masque], amp_2d[masque]
        
    # 4. Alignement absolu par tri lexicographique (arrondi pour la stabilité float32)
    idx = np.lexsort((np.round(v).astype(np.int64), np.round(u).astype(np.int64)))
    
    u_tri, v_tri, amp_tri = u[idx], v[idx], amp[idx]
    
    # 5. Calcul du rayon UV (en Méga-longueurs d'onde)
    uv_radius = np.sqrt(u_tri**2 + v_tri**2) / 1e6
    
    return {
        'u': u_tri, 
        'v': v_tri, 
        'amp': amp_tri, 
        'uv_radius': uv_radius
    }

def extract_ram_standardized() -> dict:
    """
    Extrait et standardise les visibilités directement depuis la mémoire (RAM).

    Récupère les données actives du moteur C (Zéro-Copie) et les trie de manière 
    strictement identique au lecteur FITS. Indispensable pour prouver que 
    les données manipulées par le wrapper sont mathématiquement exactes.

    Returns
    -------
    dict
        Un dictionnaire contenant les tableaux Numpy triés ('u', 'v', 'amp', 'uv_radius').

    Raises
    ------
    ValueError
        Si aucune donnée n'est trouvée en RAM (nécessite un appel à `select()` au préalable).

    Examples
    --------
    >>> with DifmapSession() as session:
    >>>     session.observe("data.fits")
    >>>     session.obs.select()
    >>>     data_ram = standardizer.extract_ram_standardized()
    """
    data = difmap_native.get_uv_data()
    
    if not data or len(data.get('u', [])) == 0:
        raise ValueError("Aucune donnée en RAM. L'appel à select() est requis au préalable.")
        
    u, v, amp = data['u'], data['v'], data['amp']
    
    # Alignement absolu
    idx = np.lexsort((np.round(v).astype(np.int64), np.round(u).astype(np.int64)))
    
    u_tri, v_tri, amp_tri = u[idx], v[idx], amp[idx]
    
    # Calcul du rayon UV (en Méga-longueurs d'onde)
    uv_radius = np.sqrt(u_tri**2 + v_tri**2) / 1e6
    
    return {
        'u': u_tri, 
        'v': v_tri, 
        'amp': amp_tri, 
        'uv_radius': uv_radius
    }

def compare_uv_datasets(data_ref: dict, data_ram: dict) -> dict:
    """
    Compare deux jeux de données UV et génère les statistiques d'erreur.

    Calcule les résidus (différences) point par point entre une référence (FITS) 
    et une cible (RAM). Utilisé pour valider la précision géométrique et 
    photométrique du wrapper.

    Parameters
    ----------
    data_ref : dict
        Le jeu de données de référence (généralement issu de `extract_uvfits_standardized`).
    data_ram : dict
        Le jeu de données cible (généralement issu de `extract_ram_standardized`).

    Returns
    -------
    dict
        Dictionnaire des métriques contenant :
        - 'delta_u_max', 'delta_v_max' : Erreur géométrique maximale (λ).
        - 'delta_amp_max' : Divergence maximale d'amplitude (Jy).
        - 'amp_rmse' : Erreur quadratique moyenne sur l'amplitude.
        - 'points_valides' : Le nombre total de visibilités comparées.
        - 'diff_u', 'diff_v', 'diff_amp' : Tableaux Numpy des résidus bruts.

    Raises
    ------
    ValueError
        Si les deux jeux de données n'ont pas le même nombre de points (désalignement).

    Examples
    --------
    >>> metrics = standardizer.compare_uv_datasets(data_fits, data_ram)
    >>> print(f"Erreur Max Amplitude : {metrics['delta_amp_max']} Jy")
    """
    if len(data_ref['u']) != len(data_ram['u']):
        raise ValueError(f"Désalignement : FITS a {len(data_ref['u'])} points, RAM a {len(data_ram['u'])} points.")
        
    diff_u = data_ram['u'] - data_ref['u']
    diff_v = data_ram['v'] - data_ref['v']
    diff_amp = data_ram['amp'] - data_ref['amp']
    
    return {
        'delta_u_max': np.max(np.abs(diff_u)),
        'delta_v_max': np.max(np.abs(diff_v)),
        'delta_amp_max': np.max(np.abs(diff_amp)),
        'amp_rmse': np.sqrt(np.mean(diff_amp**2)),
        'points_valides': len(data_ref['u']),
        'diff_u': diff_u,
        'diff_v': diff_v,
        'diff_amp': diff_amp
    }

def compare_images(img_ref: np.ndarray, img_cible: np.ndarray) -> dict:
    """
    Compare deux matrices d'images pixel par pixel et génère les statistiques.

    Calcule la carte des résidus (Dirty Map FITS vs Dirty Map RAM) pour 
    vérifier l'intégrité de la Transformée de Fourier inverse.

    Parameters
    ----------
    img_ref : numpy.ndarray
        La matrice 2D de l'image de référence (ex: vérité terrain FITS).
    img_cible : numpy.ndarray
        La matrice 2D de l'image à valider (ex: image extraite de la RAM).

    Returns
    -------
    dict
        Dictionnaire des métriques contenant :
        - 'diff_map' : La matrice 2D des différences (cible - référence).
        - 'err_max' : L'erreur maximale absolue observée sur un pixel (Jy/beam).
        - 'rmse' : L'erreur quadratique moyenne globale de l'image.
        - 'std_err' : L'écart-type des résidus.

    Raises
    ------
    ValueError
        Si les dimensions (shape) des deux images ne sont pas strictement identiques.

    Examples
    --------
    >>> metrics = standardizer.compare_images(img_fits, img_ram)
    >>> assert metrics['err_max'] < 1e-4
    """
    if img_ref.shape != img_cible.shape:
        raise ValueError(f"Dimensions différentes : {img_ref.shape} vs {img_cible.shape}")
        
    difference = img_cible - img_ref
    
    return {
        'diff_map': difference,
        'err_max': np.max(np.abs(difference)),
        'rmse': np.sqrt(np.mean(difference**2)),
        'std_err': np.std(difference)
    }