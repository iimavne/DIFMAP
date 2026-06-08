# Preuve scientifique : DIFMAP_SRC vs DIFMAP_WRAPPER

## Objectif

Ce dossier sert à produire une **preuve reproductible** que :

- **DIFMAP_SRC** (binaire `difmap` historique) produit les mêmes résultats scientifiques.
- **DIFMAP_WRAPPER** (API Python + Matplotlib) produit les mêmes résultats.

Les scripts génèrent des artefacts comparables et les comparent systématiquement.

## Jeux de données

Par défaut, on utilise les fichiers présents dans `tests/test_data/`.

## Ce qui est comparé

- UVPLOT (géométrie) : comparaison des tableaux (U,V) via export UVFITS.
- RADPLOT (amplitude) : comparaison des amplitudes via export UVFITS.
- Dirty map : comparaison pixel-à-pixel via FITS.
- Residual map : comparaison pixel-à-pixel via FITS.
- Clean map : comparaison pixel-à-pixel via FITS.
- Fenêtres CLEAN : comparaison des fichiers `.win`.

Tous les `print()` sont explicitement préfixés par `DIFMAP_SRC:` ou `DIFMAP_WRAPPER:`.

## Exécution

Depuis la racine du repo :

```bash
python -m preuve_scientifique.run_all
```

Sorties :

- `preuve_scientifique/out/difmap_src/`
- `preuve_scientifique/out/difmap_wrapper/`
- `preuve_scientifique/out/compare/`

## Benchmark batch

```bash
python -m preuve_scientifique.benchmark_batch
```

Le rapport est écrit dans `preuve_scientifique/out/benchmark/`.
