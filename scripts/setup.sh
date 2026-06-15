#!/bin/bash

# Arrêter le script si une commande échoue
set -e

echo "==================================================="
echo " Initialisation de l'environnement Difmap - Compilation et Installation "
echo "==================================================="

echo "[1/4] Vérification et installation des dépendances système..."
# Installation des paquets requis (nécessite les droits sudo)
sudo apt-get update
sudo apt-get install -y gcc gfortran pkg-config libgsl-dev pgplot5 libx11-dev libncurses-dev libtecla-dev meson ninja-build

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