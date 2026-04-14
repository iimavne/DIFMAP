import sys
import os
import locale
from PyQt6.QtWidgets import QApplication

# --- ASTUCE PRO : Forcer Python à lire les fichiers sources directement ---
# On ajoute le dossier parent au "PATH" pour qu'il comprenne ce qu'est "difmap_wrapper"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import DEPUIS le package racine (très important)
from difmap_wrapper.gui.main_window import MainWindow

def main():
    # 1. Initialisation de l'application Qt
    app = QApplication(sys.argv)

    # 2. CORRECTIF CRITIQUE : Standardisation numérique
    # On force le moteur C à utiliser le point '.' comme séparateur décimal.
    # On le fait APRÈS la création de QApplication car Qt réinitialise 
    # parfois les paramètres régionaux lors de son démarrage.
    try:
        locale.setlocale(locale.LC_NUMERIC, 'C')
    except Exception as e:
        print(f"Avertissement : Impossible de forcer le locale 'C' : {e}")

    # 3. Chemin du fichier de test par défaut
    # (Plus tard, ce chemin pourra être récupéré via un argument de ligne de commande)
    chemin_test = "tests/test_data/0028-137_X.SPLIT.1"
    
    print(f"Démarrage de Difmap SmartEdit avec : {chemin_test}")

    # 4. Lancement de l'interface
    try:
        window = MainWindow(chemin_test)
        window.show()
    except Exception as e:
        print(f"Erreur fatale lors du lancement de l'interface : {e}")
        sys.exit(1)

    # 5. Exécution de la boucle d'événements
    # Le programme reste ici tant que la fenêtre n'est pas fermée.
    sys.exit(app.exec())

if __name__ == "__main__":
    main()