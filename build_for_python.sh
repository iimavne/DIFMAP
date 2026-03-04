#!/bin/bash
echo "Nettoyage..."
rm -rf builddir

echo "Configuration Meson pour Python..."
meson setup builddir

echo "Compilation de la bibliothèque partagée (.so)..."
meson compile -C builddir

echo "Terminé ! Le noyau Difmap est prêt pour Python :"
ls -l builddir/libdifmap_core.so