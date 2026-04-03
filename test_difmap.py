import os
import subprocess
import shutil

# 1. Configuration
fichier_uv_original = "tests/test_data/0003-066_X.SPLIT.1"
dossier_tmp = "tests"

print(f"🛠️  Préparation du test dans le dossier : {dossier_tmp}/")
os.makedirs(dossier_tmp, exist_ok=True)

# On copie le fichier avec un nom court pour éviter les bugs du C
shutil.copy(fichier_uv_original, os.path.join(dossier_tmp, "data.uvf"))

# 2. Le script Difmap exact
# (Ici on teste wmap et wdmap pour voir lequel passe vraiment)
script_difmap = """observe data.uvf
select RR
mapsize 512,0.1
invert
wdmap map_standard.fits
quit
"""

print("🚀 Lancement de l'exécutable 'difmap'...")

# 3. Exécution
try:
    res = subprocess.run(
        ["difmap"], 
        input=script_difmap, 
        text=True, 
        capture_output=True, 
        cwd=dossier_tmp
    )
    
    print("\n" + "="*50)
    print("📜 LOG STANDARD DE DIFMAP (STDOUT)")
    print("="*50)
    print(res.stdout)
    
    print("\n" + "="*50)
    print("🚨 ERREURS DE DIFMAP (STDERR)")
    print("="*50)
    print(res.stderr if res.stderr else "(Aucune erreur stderr)")
    print("="*50)
    
    print(f"\n⚙️  Code de retour de la commande : {res.returncode}")
    
    # 4. Vérification des fichiers
    fichiers_crees = os.listdir(dossier_tmp)
    print(f"\n📂 Fichiers présents dans le dossier après exécution : {fichiers_crees}")
    
    if "map_standard.fits" in fichiers_crees:
        print("✅ SUCCÈS TOTAL : Difmap a réussi à créer le fichier FITS !")
    else:
        print("❌ ÉCHEC : Difmap a tourné mais n'a pas généré le fichier FITS.")

except FileNotFoundError:
    print("\n❌ ERREUR CRITIQUE : Python ne trouve pas l'exécutable 'difmap'.")
    print("Le programme Difmap n'est pas installé ou n'est pas dans le PATH du système.")
except Exception as e:
    print(f"\n❌ ERREUR INCONNUE : {e}")