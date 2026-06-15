#!/usr/bin/env python3
"""
Test pour vérifier que les fenêtres CLEAN fonctionnent correctement.
Compare CLEAN avec fenêtre loin de la source vs sans fenêtre.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from difmap_wrapper.core.session import DifmapSession

def test_clean_windows():
    """Test du comportement des fenêtres CLEAN."""
    
    print("=" * 70)
    print("TEST : Comportement des fenêtres CLEAN")
    print("=" * 70)
    
    # Fichier de test
    test_file = "tests/test_data/0003-066_X.SPLIT.1"
    
    with DifmapSession() as session:
        # 1. Charger les données
        print("\n1. Chargement des données...")
        session.observe(test_file)
        session.obs.select(pol="RR")
        print(f"   Source : {session.obs.source}")
        
        # 2. Configurer la grille
        print("\n2. Configuration de la grille (512x512, 0.1 mas/pixel)...")
        session.imager.mapsize(512, 0.1)
        
        # 3. TEST 1 : Sans fenêtre (CLEAN sur toute la zone centrale)
        print("\n" + "=" * 70)
        print("TEST 1 : CLEAN SANS FENÊTRE (toute la zone centrale)")
        print("=" * 70)
        
        session.imager.invert()
        print("   Dirty Map calculée")
        
        # Trouver le pic de la Dirty Map
        peak_info = session.imager.peak()
        print(f"   Pic Dirty Map : {peak_info['flux']:.4f} Jy/beam à ({peak_info['x']:.2f}, {peak_info['y']:.2f}) mas")
        
        # CLEAN sans fenêtre
        print("\n   Lancement CLEAN (100 itérations)...")
        session.imager.clean(niter=100, gain=0.1)
        
        # Vérifier le pic résiduel
        residual_peak_1 = session.imager.peak()
        print(f"   Pic résiduel : {residual_peak_1['flux']:.4f} Jy/beam")
        
        # 4. TEST 2 : Avec fenêtre LOIN de la source
        print("\n" + "=" * 70)
        print("TEST 2 : CLEAN AVEC FENÊTRE LOIN DE LA SOURCE")
        print("=" * 70)
        
        # Réinitialiser
        session.imager.clrmod()
        session.imager.delwin()
        session.imager.invert()
        print("   Dirty Map recalculée")
        
        # Ajouter une fenêtre loin du pic (le pic est vers (0,0))
        # La zone CLEAN est le quart central : ±12.8 mas pour 512x512 à 0.1 mas/pixel
        # On met une fenêtre à (8, 12, 8, 12) mas - dans la zone mais loin du pic
        print("   Ajout d'une fenêtre à (8, 12, 8, 12) mas - loin du pic")
        session.imager.addwin(8, 12, 8, 12)
        
        # Vérifier que la fenêtre est bien enregistrée
        windows = session.imager._get_clean_windows()
        print(f"   Fenêtres actives : {windows}")
        
        # CLEAN avec cette fenêtre
        print("\n   Lancement CLEAN (100 itérations)...")
        session.imager.clean(niter=100, gain=0.1)
        
        # Vérifier le pic résiduel
        residual_peak_2 = session.imager.peak()
        print(f"   Pic résiduel : {residual_peak_2['flux']:.4f} Jy/beam")
        
        # 5. TEST 3 : Avec fenêtre SUR la source
        print("\n" + "=" * 70)
        print("TEST 3 : CLEAN AVEC FENÊTRE SUR LA SOURCE")
        print("=" * 70)
        
        # Réinitialiser
        session.imager.clrmod()
        session.imager.delwin()
        session.imager.invert()
        print("   Dirty Map recalculée")
        
        # Ajouter une fenêtre sur le pic (autour de 0,0)
        print("   Ajout d'une fenêtre à (-10, 10, -10, 10) mas - sur le pic")
        session.imager.addwin(-10, 10, -10, 10)
        
        # Vérifier que la fenêtre est bien enregistrée
        windows = session.imager._get_clean_windows()
        print(f"   Fenêtres actives : {windows}")
        
        # CLEAN avec cette fenêtre
        print("\n   Lancement CLEAN (100 itérations)...")
        session.imager.clean(niter=100, gain=0.1)
        
        # Vérifier le pic résiduel
        residual_peak_3 = session.imager.peak()
        print(f"   Pic résiduel : {residual_peak_3['flux']:.4f} Jy/beam")
        
        # 6. COMPARAISON
        print("\n" + "=" * 70)
        print("COMPARAISON DES RÉSULTATS")
        print("=" * 70)
        print(f"Pic Dirty Map initial : {peak_info['flux']:.4f} Jy/beam")
        print()
        print(f"Sans fenêtre        : pic résiduel = {residual_peak_1['flux']:.4f} Jy/beam")
        print(f"Fenêtre loin source : pic résiduel = {residual_peak_2['flux']:.4f} Jy/beam")
        print(f"Fenêtre sur source  : pic résiduel = {residual_peak_3['flux']:.4f} Jy/beam")
        
        # Vérification
        print("\n" + "=" * 70)
        print("ANALYSE :")
        
        # Si la fenêtre loin n'a rien nettoyé, le pic résiduel doit être proche du pic initial
        ratio_2 = residual_peak_2['flux'] / peak_info['flux']
        print(f"  Ratio pic résiduel / pic initial (fenêtre loin) : {ratio_2:.2%}")
        
        if ratio_2 > 0.9:
            print("  ✓ SUCCÈS : Fenêtre loin = presque rien nettoyé")
            print("    Les fenêtres CLEAN fonctionnent correctement !")
        else:
            print("  ✗ PROBLÈME : Fenêtre loin a nettoyé quelque chose")
            print("    Il y a peut-être un bug dans les fenêtres")
        
        # Si la fenêtre sur la source a bien nettoyé, le pic résiduel doit être faible
        ratio_3 = residual_peak_3['flux'] / peak_info['flux']
        print(f"\n  Ratio pic résiduel / pic initial (fenêtre sur source) : {ratio_3:.2%}")
        
        if ratio_3 < 0.05:
            print("  ✓ SUCCÈS : Fenêtre sur source a bien nettoyé")
            print("    Le comportement est cohérent")
        else:
            print("  ⚠ ATTENTION : Fenêtre sur source n'a pas tout nettoyé")
        
        print("=" * 70)

if __name__ == "__main__":
    test_clean_windows()
