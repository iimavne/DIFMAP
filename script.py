import os
import glob
import multiprocessing
import matplotlib.pyplot as plt
from difmap_wrapper import DifmapSession

# ==========================================
# Configuration global
# ==========================================
DATA_DIR = "tests/test_data/"
OUTPUT_DIR = "results/"
REQUESTED_POL = "RR"

# ==========================================
#  Traitement à faire pour chaque fichier
# ==========================================
def process_file(filepath: str) -> None:
    """
    Traite un fichier UV/FITS individuel, sauvegarde les images 
    et ouvre les fenêtres d'inspection visuelle.
    """
    filename = os.path.basename(filepath)
    print(f"[{filename}] Début du traitement...")
    
    with DifmapSession() as session:
        try:
            # 1. Chargement des données
            session.observe(filepath)
            source_name = session.obs.source
            session.obs.select(pol=REQUESTED_POL)
            
            # 2. Plan UV : Sauvegarde ET Affichage
            uv_path = os.path.join(OUTPUT_DIR, f"{source_name}_uvplot.png")
            print(f"[{filename}] Affichage du plan UV. Fermez la fenêtre pour continuer.")
            
            session.vis.uvplot(
                figsize=(7, 7),
                title=f"Plan UV - {source_name} ({REQUESTED_POL})",
                save_path=uv_path, # Sauvegarde de la figure
                show=True  # Active l'ouverture de la fenêtre
            )
            
            # 3. Configuration de l'imagerie
            session.imager.mapsize(512, 0.1)
            session.imager.invert()
            
            # 4. Dirty Map : Sauvegarde ET Affichage
            map_path = os.path.join(OUTPUT_DIR, f"{source_name}_dirtymap.png")
            print(f"[{filename}] Affichage de la Dirty Map. Fermez la fenêtre pour continuer.")
            
            session.vis.mapplot(
                title=f"Dirty Map - {source_name} ({REQUESTED_POL})", 
                cmap="inferno",
                save_path=map_path, # Sauvegarde de la figure
                show=True  # Active l'ouverture de la fenêtre
            )
            
            print(f"[{filename}] Traitement terminé avec succès. \n")
            
        except Exception as e:
            print(f"[{filename}] Erreur lors du traitement : {e}")

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fits_files = glob.glob(os.path.join(DATA_DIR, "*SPLIT*"))
    total_files = len(fits_files)
    
    print("\n \n INITIALISATION DU PIPELINE DE TRAITEMENT.")
    print(f"Nombre de fichiers détectés : {total_files}\n")
    
    for index, filepath in enumerate(fits_files, start=1): # Itération sur les fichiers avec suivi de progression
        print(f"\n \n--- PROGRESSION : {index}/{total_files} ---")
        
        process = multiprocessing.Process(target=process_file, args=(filepath,)) # Création d'un processus pour chaque fichier
        process.start() # Démarrage du processus
        process.join() # Attente de la fin du processus avant de passer au suivant
        
    print("\n \n Fin de l'exécution du pipeline.")