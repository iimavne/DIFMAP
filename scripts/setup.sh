#!/bin/bash

# Arrêter le script si une commande échoue
set -e

echo "==================================================="
echo " Initialisation de l'environnement Difmap - Compilation et Installation "
echo "==================================================="

echo "[1/4] Vérification et installation des dépendances système..."
# Installation des paquets requis (nécessite les droits sudo)
sudo apt-get update
# Deps système (compilation C/Fortran) + deps de build Python requises par meson.build :
#   python3-dev   -> Python.h (py3.dependency())
#   python3-numpy -> numpy.get_include() pour le binding zero-copy
#   cython3       -> compilation du binding .pyx (python3 -m cython)
sudo apt-get install -y gcc gfortran pkg-config libgsl-dev pgplot5 libx11-dev libncurses-dev libtecla-dev meson ninja-build python3-dev python3-numpy cython3

echo "[2/4] Nettoyage des anciens fichiers de compilation..."
# Suppression de l'ancien dossier s'il existe pour une compilation propre
rm -rf builddir

echo "[3/4] Configuration du projet avec Meson..."
meson setup builddir

echo "[4/4] Compilation avec Ninja..."
meson compile -C builddir

echo "==================================================="
echo "Compilation terminée avec succès !"
echo "Vous pouvez lancer l'exécutable avec la commande :"
echo "   difmap"
echo ""
echo "Pour installer Difmap globalement sur le système, tapez :"
echo "   sudo meson install -C builddir"
echo "==================================================="