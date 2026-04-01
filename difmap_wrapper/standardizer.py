import numpy as np
from astropy.io import fits
import difmap_native

def extract_uvfits_standardized(filepath: str) -> dict:
    """
    Lit un fichier UVFITS, applique les corrections de fréquences multi-IF (table AIPS FQ),
    et renvoie les données (U, V, Amplitude, Rayon UV) converties en longueurs d'onde et alignées.
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
    Récupère les données de la RAM (Zero-Copy) et les trie de manière
    strictement identique au lecteur FITS pour une comparaison ou un export.
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
    Compare deux jeux de données UV alignés et renvoie les statistiques d'erreur
    ainsi que les tableaux de différences pour l'affichage graphique.
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
    Compare deux images (ex: Dirty Maps) et renvoie les statistiques d'erreur
    et la carte des différences.
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