from difmap_wrapper import DifmapSession
from difmap_wrapper.uv import DifmapUV

# Remplace par ton vrai chemin
fichier_fits = "tests/test_data/0003-066_X.SPLIT.1"

with DifmapSession() as session:
    print(f"Chargement de {fichier_fits}...")
    session.load_observation(fichier_fits)
    
    print("Extraction Zéro-Copie des visibilités...")
    data = session.get_uv_data()
    
    print(f"Génération des graphiques pour {len(data['u'])} points...")
    DifmapUV.plot_coverage(data)
    DifmapUV.plot_radplot(data)