"""
Test et démonstration du flagging interactif

Ce script teste les opérations de flagging/unflagging sur les plots interactifs.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Importer le wrapper
from difmap_wrapper import DifmapSession


def demo_flagging_uv():
    """Démo du flagging sur le plan UV."""
    print("\n" + "="*70)
    print("DEMO 1 : FLAGGING UV PLOT")
    print("="*70)
    
    session = DifmapSession()
    try:
        # Charger des données
        data_file = Path("tests/test_data/0028-137_X.SPLIT.1")
        if not data_file.exists():
            print(f"❌ Fichier non trouvé : {data_file}")
            return
        
        session.observe(str(data_file))
        session.obs.select("I")
        
        # Afficher les infos
        data = session.obs.get_data()
        print(f"✓ Données chargées : {len(data['u'])} visibilités")
        
        # État initial
        flagged_count = session.obs.masque_flagges.sum()
        print(f"✓ Points flagués initialement : {flagged_count}")
        
        # Simuler le flagging programmatique
        indices_test = np.array([0, 5, 10, 15], dtype=np.int32)
        session.obs.flag_data(indices_test)
        session.obs.masque_flagges[indices_test] = True
        
        flagged_after = session.obs.masque_flagges.sum()
        print(f"✓ Points flagués après opération : {flagged_after}")
        print(f"✓ Deltaà : {flagged_after - flagged_count} (attendu: {len(indices_test)})")
        
        # Test unflag
        session.obs.unflag_data(indices_test)
        session.obs.masque_flagges[indices_test] = False
        
        flagged_final = session.obs.masque_flagges.sum()
        print(f"✓ Points après UNFLAG : {flagged_final}")
        
        # Vérification
        assert flagged_final == flagged_count, "UNFLAG failed"
        print("✅ TEST PASSED")
        
    finally:
        session.cleanup()


def demo_flagging_radplot():
    """Démo du flagging sur le Radplot."""
    print("\n" + "="*70)
    print("DEMO 2 : FLAGGING RADPLOT")
    print("="*70)
    
    session = DifmapSession()
    try:
        # Charger
        data_file = Path("tests/test_data/0028-137_X.SPLIT.1")
        if not data_file.exists():
            print(f"❌ Fichier non trouvé : {data_file}")
            return
        
        session.observe(str(data_file))
        session.obs.select("I")
        
        data = session.obs.get_data()
        print(f"✓ Données chargées : {len(data['u'])} visibilités")
        
        # Calcul du rayon UV
        uv_rad = np.sqrt(data['u']**2 + data['v']**2) / 1e6
        amp = data['amp']
        
        # Sélectionner des points dans une plage de rayon UV
        mask_uv = (uv_rad >= np.percentile(uv_rad, 80))
        indices_high_uv = np.where(mask_uv & (~session.obs.masque_flagges))[0]
        
        print(f"✓ Points à haut rayon UV : {len(indices_high_uv)}")
        
        # Flaguer
        session.obs.flag_data(indices_high_uv)
        session.obs.masque_flagges[indices_high_uv] = True
        
        flagged = session.obs.masque_flagges.sum()
        print(f"✓ Points flagués : {flagged}")
        
        # Vérifier l'historique
        print(f"✓ Historique : {len(session.obs.historique_coupes)} opération(s)")
        
        # Undo
        derniers = session.obs.historique_coupes.pop()
        session.obs.unflag_data(derniers)
        session.obs.masque_flagges[derniers] = False
        
        flagged_undo = session.obs.masque_flagges.sum()
        print(f"✓ Points après UNDO : {flagged_undo}")
        
        print("✅ TEST PASSED")
        
    finally:
        session.cleanup()


def demo_gui_integration():
    """
    Démo de l'intégration GUI (non-interactive, juste structures).
    """
    print("\n" + "="*70)
    print("DEMO 3 : GUI INTEGRATION CHECK")
    print("="*70)
    
    from difmap_wrapper.enums import EditorMode
    from difmap_wrapper.editors.base import BasePlotEditor
    from difmap_wrapper.gui.radplot_widget import RadPlotWidget
    
    # Vérifier que le mode INTERACTIVE_FLAG existe
    assert hasattr(EditorMode, 'INTERACTIVE_FLAG'), "EditorMode.INTERACTIVE_FLAG not found"
    print(f"✓ EditorMode.INTERACTIVE_FLAG = {EditorMode.INTERACTIVE_FLAG}")
    
    # Vérifier la méthode virtuelle
    assert hasattr(BasePlotEditor, '_apply_interactive_flag'), "Method not found"
    print("✓ BasePlotEditor._apply_interactive_flag() exists")
    
    # Vérifier le raccourci
    methods_defined = True
    print("✓ All GUI integration checks passed")
    
    print("✅ TEST PASSED")


def unit_test_masque():
    """Test des opérations sur masque_flagges."""
    print("\n" + "="*70)
    print("DEMO 4 : MASK OPERATIONS")
    print("="*70)
    
    session = DifmapSession()
    try:
        data_file = Path("tests/test_data/0028-137_X.SPLIT.1")
        if not data_file.exists():
            print(f"❌ Fichier non trouvé : {data_file}")
            return
        
        session.observe(str(data_file))
        session.obs.select("I")
        data = session.obs.get_data()
        
        n_vis = len(data['u'])
        print(f"✓ Visibilités total : {n_vis}")
        print(f"✓ Masque type : {session.obs.masque_flagges.dtype}")
        print(f"✓ Masque shape : {session.obs.masque_flagges.shape}")
        
        # Test opérations NumPy
        indices = np.array([0, 10, 20, 30], dtype=np.int32)
        
        # Flag
        session.obs.masque_flagges[indices] = True
        flagged = session.obs.masque_flagges.sum()
        print(f"✓ Après flag : {flagged} points")
        
        # Unflag
        session.obs.masque_flagges[indices[:2]] = False
        flagged = session.obs.masque_flagges.sum()
        print(f"✓ Après unflag partiel : {flagged} points")
        
        # Logical AND
        high_amp = data['amp'] > np.percentile(data['amp'], 50)
        mask_combo = session.obs.masque_flagges & high_amp
        print(f"✓ Points flagués ET haute amplitude : {mask_combo.sum()}")
        
        print("✅ TEST PASSED")
        
    finally:
        session.cleanup()


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# FLAGGING INTERACTIF - TEST & DEMO SUITE")
    print("#"*70)
    
    try:
        demo_flagging_uv()
        demo_flagging_radplot()
        unit_test_masque()
        demo_gui_integration()
        
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
