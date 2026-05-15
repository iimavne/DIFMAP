import sys
import os
import locale
import difmap_native
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

# --- Forcer Python à lire les fichiers sources directement ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import DEPUIS le package racine (très important)
from difmap_wrapper.gui.main_window import MainWindow

def main():
    # 1. Initialisation de l'application Qt
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # 2. Forcer le locale numérique à 'C' pour éviter les problèmes de parsing
    try:
        locale.setlocale(locale.LC_NUMERIC, 'C')
    except Exception as e:
        print(f"Avertissement : Impossible de forcer le locale 'C' : {e}")
    
    print("Démarrage de DIFMAP Modern (Session vierge)...")

    # 3. Lancement de l'interface
    try:
        # On lance MainWindow SANS fichier initial. 
        # C'est l'utilisateur qui chargera ses données via l'interface.
        window = MainWindow()
        window.show()
    except Exception as e:
        print(f"Erreur fatale lors du lancement de l'interface : {e}")
        sys.exit(1)

    # 4. Exécution de la boucle d'événements
    # Le programme reste ici tant que la fenêtre n'est pas fermée.
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
