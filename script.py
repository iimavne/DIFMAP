from difmap_wrapper.session import DifmapSession

# Utilisation du context manager pour gérer la mémoire
with DifmapSession() as session:
    print("Chargement des données...")
    session.observe("tests/test_data/0003-066_X.SPLIT.1")
    
    print("Génération du plan UV...")
    # C'est cette ligne qui va ouvrir la fenêtre Matplotlib !
    session.obs.uvplot()

print("Terminé !")