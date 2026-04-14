from difmap_wrapper.session import DifmapSession

def main():
    print("Démarrage de la session Difmap...")
    session = DifmapSession()
    
    # 1. Chargement des données
    fichier_fits = "tests/test_data/0028-137_X.SPLIT.1"  # Remplace par le chemin de ton fichier FITS de test
    session.observe(fichier_fits)
    session.obs.select("RR")
    print("Données chargées en RAM.")

    # 2. Test du UVPlot Interactif
    print("\n--- TEST UVPLOT ---")
    session.vis.uvplot(title="Test UVPlot Interactif", interactive=True)
    

if __name__ == "__main__":
    main()