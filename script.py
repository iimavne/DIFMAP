import os
import glob
import multiprocessing
import matplotlib.pyplot as plt
from difmap_wrapper import DifmapSession

# ==========================================
# Configuration du pipeline
# ==========================================
DATA_DIR = "tests/test_data/"
OUTPUT_DIR = "results/"
REQUESTED_POL = "RR"

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
                save_path=uv_path,
                show=True  # Active l'ouverture de la fenêtre
            )
            
            # 3. Configuration de l'imagerie
            session.imager.uvweight(bin_size=2.0, err_power=0.0)
            session.imager.mapsize(512, 0.1)
            session.imager.invert()
            
            # 4. Dirty Map : Sauvegarde ET Affichage
            dirty = session.imager.get_map_package(cellsize=0.1)
            map_path = os.path.join(OUTPUT_DIR, f"{source_name}_dirtymap.png")
            print(f"[{filename}] Affichage de la Dirty Map. Fermez la fenêtre pour continuer.")
            
            session.vis.mapplot(
                dirty, 
                title=f"Dirty Map - {source_name} ({REQUESTED_POL})", 
                cmap="inferno",
                save_path=map_path,
                show=True  # Active l'ouverture de la fenêtre
            )
            
            print(f"[{filename}] Traitement terminé avec succès.")
            
        except Exception as e:
            print(f"[{filename}] Erreur lors du traitement : {e}")

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fits_files = glob.glob(os.path.join(DATA_DIR, "*SPLIT*"))
    total_files = len(fits_files)
    
    print("Initialisation du pipeline de traitement.")
    print(f"Nombre de fichiers détectés : {total_files}\n")
    
    for index, filepath in enumerate(fits_files, start=1):
        print(f"--- Progression : {index}/{total_files} ---")
        
        process = multiprocessing.Process(target=process_file, args=(filepath,))
        process.start()
        process.join() 
        
    print("\nFin de l'exécution du pipeline.")