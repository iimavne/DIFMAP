import sys
import os
import locale
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from difmap_wrapper.gui.main_window import MainWindow


def _setup_c_capture():
    """
    Redirige fd 1 (stdout) et fd 2 (stderr) du processus vers un pipe OS,
    de façon à capturer la sortie C de lprintf() dans le GUI.

    Retourne le file descriptor de lecture du pipe (à passer à MainWindow).
    Python sys.stdout / sys.stderr sont rebouclés sur les fd originaux pour
    que les print() Python continuent d'aller sur le terminal de démarrage.
    """
    r_fd, w_fd = os.pipe()

    orig_stdout = os.dup(1)
    orig_stderr = os.dup(2)

    os.dup2(w_fd, 1)
    os.dup2(w_fd, 2)
    os.close(w_fd)

    # Python écrit toujours sur le terminal original
    sys.stdout = open(orig_stdout, 'w', closefd=True, buffering=1,
                      errors='replace')
    sys.stderr = open(orig_stderr, 'w', closefd=True, buffering=1,
                      errors='replace')

    return r_fd


def main():
    # 1. Capturer la sortie C avant toute initialisation Qt/difmap_native
    c_capture_fd = _setup_c_capture()

    import difmap_native  # noqa: E402 — import après redirection fd

    # 2. Initialisation Qt
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # 3. Locale numérique C pour éviter les problèmes de parsing float
    try:
        locale.setlocale(locale.LC_NUMERIC, 'C')
    except Exception as e:
        print(f"Avertissement locale : {e}")

    # 4. Lancement de l'interface
    try:
        window = MainWindow(c_capture_fd=c_capture_fd)
        window.show()
    except Exception as e:
        os.close(c_capture_fd)
        print(f"Erreur fatale au lancement : {e}")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
