# ANALYSE TECHNIQUE - Architecture DIFMAP

**Référence détaillée des internals DIFMAP et décomposition modulaire**

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Décomposition des modules](#décomposition-des-modules)
4. [Structures de données clés](#structures-de-données-clés)
5. [Interfaces critiques](#interfaces-critiques)
6. [Langage macro SPHERE](#langage-macro-sphere)
7. [Points problématiques & solutions](#points-problématiques--solutions)
8. [Tables de référence](#tables-de-référence)

---

## VUE D'ENSEMBLE

### Qu'est-ce que DIFMAP?

**DIFMAP** (Difference Mapping Program) est un logiciel d'astronomie spécialisé développé à Caltech pour:
- Lire des fichiers FITS UV (visibilités) d'observations VLBI
- Construire des modèles de composantes (sources ponctuelles, gaussiennes, structures étendues)
- Fitter des modèles à des données de visibilité radio avec Levenberg-Marquardt
- Effectuer l'auto-calibration sur résidus
- Déconvoluer des images avec l'algorithme CLEAN
- Générer des cartes de qualité publication

### Statistiques Clés

| Métrique | Valeur |
|----------|--------|
| **Lignes de code totales** | ~100,000 |
| **Langage primaire** | C |
| **Langage secondaire** | Fortran (point d'entrée f77main.f) |
| **Système de build** | Meson + Ninja |
| **Fichiers source** | 150+ |
| **Librairies externes** | PGPLOT 5.0.2+, GSL, FITS I/O, X11 |
| **Variables globales** | 50+ (problématique pour threading!) |

### Workflow Fondamental

```
1. Lire fichier FITS UV
   └─→ Charger amplitudes/phases/flags de visibilité
   
2. Créer modèle de source
   └─→ Ajouter composantes point/gaus/disque
   
3. Fitter modèle aux données
   └─→ Optimisation Levenberg-Marquardt
   
4. Déconvoluer (optionnel)
   └─→ Itérations CLEAN sur résidus
   
5. Auto-calibrer (optionnel)
   └─→ Résoudre gains/phases stations
   
6. Sauvegarder résultats
   └─→ Carte FITS + paramètres modèle
```

---

## ARCHITECTURE

### Système de Construction

```
meson.build (config racine)
├── Détecte Fortran GNU, compilateur GCC C
├── Vérifie disponibilité librairie PGPLOT
├── Configure optimisations:
│   ├─ C: -O2 (optimisation standard)
│   └─ Fortran: -O0 (éviter instabilités numériques)
├── Active code indépendant de position (-fPIC)
└── Génère exécutable builddir/difmap

Séquence build Ninja:
├── Librairies statiques: libsphere.a, libfits.a, libslalib.a, ...
├── Relie toutes librairies
└── Exécutable final: builddir/difmap
```

### Flux de Processus

```
┌──────────────────────────────────────────┐
│ Python subprocess.Popen() lance difmap   │
├──────────────────────────────────────────┤
│ f77main.f (point d'entrée Fortran)       │
│ └─→ Appelle main_difmap() C              │
├──────────────────────────────────────────┤
│ sphere.c initialise interpréteur SPHERE  │
│ └─→ Enregistre descripteurs fonction C   │
│     └─→ read_uv, model, add, fit, clean, │
│         selfcal, wmap, etc.              │
├──────────────────────────────────────────┤
│ SPHERE lit commandes desde stdin         │
│ └─→ Lexical → Parse → Compile → Execute │
├──────────────────────────────────────────┤
│ Commandes utilisateur (ou script Python) │
│ exécutent algos C                        │
│ └─→ Modifient observation/modèle statics │
├──────────────────────────────────────────┤
│ Output écrit à:                          │
│ ├─ difmap.log (sortie commandes)        │
│ ├─ *.fits (fichiers données)            │
│ └─ *.ps (graphiques PostScript)         │
└──────────────────────────────────────────┘
```

---

## DÉCOMPOSITION DES MODULES

### 1. difmap_src/ - Application Principale (85 fichiers)

**Objectif:** Algorithmes d'imagerie VLBI et structures de données

#### Sous-modules:

**Gestion Données UV**
- `obs.c`, `obs.h`: Struct Observation (antennes, sources, données visibilité)
- `uvf_read.c`, `uvf_write.c`: I/O FITS pour données UV
- `subarray.c`: Support multi-subarray
- `obhead.c`: Parse en-têtes FITS

**Modélisation Composantes**
- `model.c`, `model.h`: Définitions composantes (point, gaus, disque, anneau, ellipse)
- `modeltab.c`: Gestion table modèle
- `modfit.c`: Fitting Levenberg-Marquardt
- `modvis.c`: Calcul visibilités synthétiques du modèle

**Calibration**
- `slfcal.c`: Algorithme auto-calibration (résoudre gains/phases station)
- `telcor.c`: Corrections télescope-spécifiques
- `clphs.c`: Calculs phase de fermeture
- `obutil.c`: Utilitaires Observation

**Déconvolution**
- `mapclean.c`: Implémentation algorithme CLEAN
- `mapcln.h`: Structures état CLEAN
- `newfft.c`: FFT transformer Fourier

**Visualisation**
- `maplot.c`: Traçage carte (utilise PGPLOT)
- `uvplot.c`: Graphiques couverture UV
- `modplot.c`: Graphiques composantes modèle
- `specplot.c`: Graphiques spectraux

**Noyau Mathématique**
- `lmfit.c`: Levenberg-Marquardt least-squares fitting
- `matinv.c`: Opérations matrice (inversion, multiplication)
- `besj.c`, `besj.h`: Fonctions Bessel J_n
- `dnint.c`: Conversion double-précision entier
- `minmax.c`: Opérations min/max
- `fnint.c`: Conversion float entier

**Transformations**
- `uvrotate.c`: Rotation plan UV
- `uvtrans.c`: Transformations coordonnées UV
- `costran.c`: Transformations système coordonnées
- `uvaver.c`: Moyennage UV
- `uvinvert.c`: Inversion vecteur

**Cadre Commandes**
- `difmap.c` (7778 lignes!): Processeur commandes principal, tables variables, registration fonctions
- `if.c`: Traitement IF/conditions
- `startup.c`: Initialisation
- `version.h`: Info version

**UI/Affichage**
- `ifpage.c`, `ifpage.h`: Affichage IF/fenêtre
- `uvpage.c`, `uvpage.h`: Gestion page UV
- `mapwin.c`, `mapwin.h`: Gestion fenêtre carte
- `dpage.c`, `dpage.h`: Gestionnaire page affichage
- `vedit.c`, `vedit.h`: Éditeur visibilité

**Utilitaires**
- `symtab.c`: Gestion table symboles
- `cksum.c`, `cksum.h`: Calcul checksum
- `color.c`, `color.h`: Gestion couleurs
- `units.c`, `units.h`: Conversions unités
- `freelist.c`, `freelist.h`: Gestion mémoire
- `markerlist.c`: Gestion marqueurs
- `planet.c`: Positions planètes
- `pb.c`, `pb.h`: Faisceau primaire

#### Structures de Données Clés:

```c
// In obs.h
typedef struct {
    char name[32];      // Source name
    double epoch, ra, dec;
    double app_ra, app_dec; // Apparent coords
    double tot_flux;
    // ... (20+ more fields)
} Source;

typedef struct {
    char name[16];      // Station name
    int antno;
    double x, y, z;     // Earth coordinates (meters)
    float maxamp, maxphs;
    // ... (more fields)
} Station;

typedef struct {
    int nbas;           // Number of baselines
    float *u, *v, *w;   // Baseline coordinates (lambda)
    float *amp, *phs;   // Visibility magnitudes/phases
    float *weight;      // Statistical weights
    int *flags;         // Data quality flags
    // ... integration times, etc.
} UVData;

// In model.h
typedef enum {
    M_DELT,      // Point source (delta function)
    M_GAUS,      // Gaussian
    M_DISK,      // Uniform disk
    M_RING,      // Elliptical ring
    M_RECT,      // Rectangle
    // ... others
} Modtyp;

typedef struct {
    Modtyp type;
    int freepar;    // Which params are free (bitmap)
    float flux, x, y;
    float major, ratio, phi;  // FWHM major axis, axial ratio, position angle
    float spcind;             // Spectral index
    // ... error values
} Modcmp;

// In mapcln.h
typedef struct {
    int nx, ny;         // Map dimensions
    float *map;         // Map pixels
    float *residuals;   // Residual map
    float bmaj, bmin;   // Beam size (arcsec)
    // ... restoration info
} Mapcln;
```

---

### 2. sphere_src/ - Interpréteur Macro (20 fichiers)

**But:** Langage scripting Turing-complet pour orchestrer algorithmes DIFMAP

#### Composants:

```
sphere.c         ← Point d'entrée principal
├── lex.c        - Scanner lexical (tokenization)
├── compile.c    - Parser & compilateur (tokens → bytecode)
├── run.c        - Interpréteur bytecode
├── func.c       - Fonctions intégrées (read_uv, clean, fit, etc.)
├── table.c      - Table symboles (variables, tableaux)
├── ops.c        - Opérateurs (arith, comparaison, logique)
├── var.c        - Gestion variables
├── plotlib.c    - Wrapper interface PGPLOT
└── help.c       - Système aide
```

#### Caractéristiques Langage SPHERE:

```sphere
# Variables
set flux 1.5
set x_off 0.001

# Tableaux
array src[10]
array data[256, 256]

# Contrôle flux
for i=1 to 100
  if i > 50
    print "Itération $i"
    add $flux $x_off 0 gaussian
    fit
  else
    print "Début"
  endif
end

while condition
  # ... corps boucle
end

# Opérations arithmétiques
set result = (flux * 2.0) + offset

# Appels fonctions (invoque algorithmes C)
read_uv "data.fits"
model
add 1.0 0 0 point
fit
clean 1000 0.1
wmap "output.fits"

# Manipulation chaînes
set filename = "resultats_" & date & ".fits"
```

#### Comment SPHERE Connecte C:

```c
// Dans difmap.c
static USER_FN_PROTO my_functions[] = {
    {NULL, "read_uv", 1, uvf_input},        // read_uv file
    {NULL, "model", 0, model_init},         // model
    {NULL, "add", 5, add_to_model},         // add flux x y type params...
    {NULL, "fit", 0, lm_fit},               // fit
    {NULL, "clean", 4, map_clean},          // clean niter gain threshold method
    {NULL, "selfcal", 2, selfcal_fit},      // selfcal solution_interval...
    {NULL, "wmap", 1, uvf_output},          // wmap filename
    {NULL, "observ", 0, print_obs},         // observ (print observation)
    {NULL, "modelpars", 0, print_model},    // modelpars (print model)
    // ... ~100 plus de fonctions
    {NULL, NULL, 0, NULL}
};

static Variable vars[] = {
    {"uvhwhm", R_ONLY, &invpar.uvhwhm, ...},
    {"uvmin", R_ONLY, &invpar.uvmin, ...},
    {"clean_gain", R_WRITE, &mc->gain, ...},
    // ... ~200 plus de variables
};

// Enregistrement SPHERE (dans sphere.c):
for each function in my_functions:
    register_function(function.name, function.nargs, function.ptr)
for each variable in vars:
    register_variable(variable.name, variable.ptr, variable.flags)
```

**Insight clé:** SPHERE est le **SEUL** moyen d'invoquer algorithmes C. Python n'appelle pas C directement—il génère scripts SPHERE.

---

### 3. fits_src/ - Support Format FITS (10 fichiers)

**But:** Lire/écrire fichiers FITS (standard astronomie format binaire données)

#### Fichiers Clés:

- `fits.c`, `fits.h`: Routines FITS principales
- `fits_util.c`: Fonctions utilitaires
- `fitline.c`: Lecture lignes
- `fitkey.c`: Parsing mots-clés FITS

#### Structure Données FITS:

```c
// Simplifié
typedef struct {
    int nhdu;           // Nombre HDUs (extensions)
    HDU **hdu;
} Fits;

typedef struct {
    Hdutype type;       // PRIMARY, TABLE, IMAGE, BINTAB
    int naxis;
    long *naxes;        // Dimensions
    Bitpix bitpix;      // Type données
    char **keywords;    // Mots-clés FITS
    void *data;         // Tableau données brutes
} HDU;
```

#### Format FITS UV (Standard):

```
HDU PRINCIPAL:
  ├─ GROUPS= T (format table groupée)
  ├─ PSCAL, PZERO (facteurs mise à l'échelle)
  └─ PARANGLE, données source

Extensions RANDOM GROUP:
  ├─ Visibilité complexe (coordonnées u, v, w)
  ├─ Amplitude, phase, poids
  ├─ Temps, information station
  └─ ~200 paramètres par visibilité
```

---

### 4. slalib_src/ - Bibliothèque Astronomique (35 fichiers)

**But:** Standard Low-Level Astronomy Library (SLA)

```
ephem/
  ├─ planet.c: Éphémérides planètes
  ├─ refco.c: Corrections réfraction atmosphérique
  └─ geod.c: Transformations géodésiques

coords/
  ├─ eqecl.c: Équatorial ↔ Écliptique
  ├─ prec.c: Transformations précession
  ├─ fk4_fk5.c: Conversions époque catalogue
  └─ hms.c: Parsing heure-minute-seconde

math/
  ├─ dvn.c: Normalisation vecteur
  ├─ dmat.c: Opérations matrice
  └─ euler.c: Transformations angle Euler
```

---

### 5. libtecla_src/ - Éditeur Terminal (20 fichiers)

**But:** Édition ligne de commande interactive (comme GNU Readline mais plus portable)

Caractéristiques:
- Historique commandes (flèches haut/bas)
- Complétion tab
- Modes édition Vi/Emacs
- Appariement parenthèses

Non critique pour wrapper (peut être désactivé mode interactif).

---

### 6. Bibliothèques Soutien

**logio_src/**: Utilitaires logging et I/O
- `logio.c`: Buffering sortie
- `page.c`: Pagination

**pager_src/**: Pagination texte (pour affichage sorties larges)
- `pager.c`: Pagination terminal

**recio_src/**: I/O Record
- `recio.c`: Lecture record fixe

**scrfil_src/**: Gestion fichier scratch
- `scrfil.c`: Gestion fichier temporaire

**sphere_src/**: (Voir section 2 ci-dessus)

**cpg_src/**: Wrapper PGPLOT C
- `cpgplot.h`: Bindings langage C pour bibliothèque PGPLOT Fortran

---

## STRUCTURES DE DONNÉES CLÉS

### Pattern Singleton Global

DIFMAP utilise extensions globales statiques plutôt que de passer contextes:

```c
// Dans fichiers différents .c, marqués static

static Observation *ob = NULL;   // Observation courante
static Model *model = NULL;      // Modèle courant
static Mapcln *mc = NULL;        // État CLEAN courant

// Callbacks pour les modifier:
void read_uv(char *filename) {
    // Charger dans ob global
    ob = load_obs_from_fits(filename);
}

void add_component(float flux, ...) {
    // Ajouter au modèle global
    if (model == NULL) model = create_model();
    model->components[model->ncmp++] = ...;
}
```

**Problème:** Cela rend bibliothèque C intrinsèquement non-rentrante.
**Solution:** Utiliser isolation subprocess (processus = globals séparés).

### Structure Observation

```c
typedef struct {
    Source *source;        // Info source cible
    Station *tel;          // Tableau télescopes
    int ntel;             // Nombre télescopes
    
    UVData *data;         // Données visibilité
    int nbas;             // Nombre baselines
    
    float freqoff;        // Offset fréquence
    double mjd;           // Modified Julian Date
    char project[32];     // Code projet
    
    // ... 30+ champs plus
} Observation;
```

### Composante Modèle

```c
typedef struct {
    float flux;           // Jy
    float x, y;           // arcseconde (RA, Dec décalage centre phase)
    
    // Pour Gaussiennes/modèles étendus:
    float major;          // FWHM axe majeur (arcsec)
    float ratio;          // Ratio axial mineur/majeur
    float phi;            // Angle position (degrees)
    
    // Pour fitting:
    int freepar;          // Bitmap: quels paramètres libres pour fit?
    float dflux, dx, dy;  // Incertitudes après fitting
    float dmajor, dratio, dphi;
    
    Modtyp type;          // POINT, GAUS, DISK, RING, etc.
} Modcmp;
```

### État CLEAN

```c
typedef struct {
    float *map;           // Tableau image 2D (nx × ny floats)
    float *residuals;     // Carte résiduelle
    int nx, ny;           // Dimensions pixel
    
    float bmaj, bmin;     // Faisceau majeur/mineur (arcsec)
    float bpa;            // Angle position faisceau (degrees)
    
    int n_clean_iter;     // Itérations complétées
    float gain;           // Gain boucle (0-1)
    float threshold;      // Seuil arrêt (Jy/beam)
    
    // Liste composantes CLEAN trouvées:
    struct {
        float flux;
        int ix, iy;       // Localisation pixel
    } *clean_comps;
    int n_comps;
} Mapcln;
```

---

## INTERFACES CRITIQUES

### Vers DIFMAP depuis SPHERE:

Voici points d'entrée principaux que vous utiliserez dans scripts SPHERE:

```sphere
# Chargement Données
read_uv "filename.fits"     # Charger UV FITS
write_uv "filename.fits"    # Sauvegarder UV FITS

# Modélisation
model                       # Initialiser modèle
add flux x y type major ratio pa   # Ajouter composante
delete_component index      # Supprimer composante
modelpars                   # Afficher modèle courant

# Fitting
fit                         # Levenberg-Marquardt fit
selfcal interval           # Auto-calibration

# Nettoyage
clean niter gain threshold method   # Déconvolution CLEAN

# Sortie
wmap "filename.fits"        # Écrir image FITS

# Inspection
observ                      # Afficher info observation
uvstat                      # Statistiques UV
mapstat                     # Statistiques carte

# Traçage (utilise PGPLOT → fichiers image)
uvplot                      # Tracer couverture UV
modplot                     # Tracer composantes modèle
mapplot                     # Tracer carte CLEAN
```

---

## LANGAGE MACRO SPHERE

### Pourquoi SPHERE?

**Alternative:** Wrapper chaque fonction C individuellement
- Résultat: 500+ fonctions à wrapper
- Maintenance: Cauchemar (bris API update DIFMAP)

**Mieux:** Utiliser SPHERE (déjà là!)
- SPHERE orchestrat déjà algorithmes intelligemment
- Python juste génère scripts SPHERE dynamiquement
- Changements C internes n'affectent pas Python

### Bases SPHERE

```sphere
# Commentaires
# Ceci est un commentaire

# Variables
set myvar 3.14
set name "test"

# Concaténation chaîne
set path "resultats/" & name & ".fits"

# Opérations arithmétiques
set result = (10 + 5) * 2 - 3 / 0.5

# Tableaux
array data[1000]
set data[5] = 3.14

# Contrôle flux
for i=1 to 10
  print "Itération " & i
  if i > 5
    print "  Plus que 5!"
  else
    print "  Toujours construction"
  endif
end

# Boucles while
set x = 1
while x < 100
  set x = x * 2
end

# Appels fonctions
read_uv "data.fits"
observ              # Afficher observation

# Création modèle
model               # Initialiser
add 1.0 0 0 point   # flux x y type
add 0.5 0.001 0 gaussian 0.001 0.8 45
fit                 # Fitting modèle

clean 1000 0.1      # niter gain

# Sauvegarde
wmap "output.fits"

# Sortie
exit
```

---

## POINTS PROBLÉMATIQUES & SOLUTIONS

### Problème #1: Globals Statiques (Sécurité Mémoire)

**Problème:** Globals empêchent sessions multiples simultanées
```c
static Observation *ob = NULL;  // Un seul!
static Model *model = NULL;     // Un seul!
```

**Solution:** Isolation subprocess (un processus = un ensemble globals)

---

### Problème #2: Dépendance PGPLOT (Affichage)

**Problème:** PGPLOT nécessite X11 graphics sur serveurs

**Solution:** Utiliser modes headless
- Device PDF: `/pdf` (PostScript → PDF)
- Device PS: `/ps` (Fichier PostScript)
- Pas d'affichage nécessaire

**Depuis Python:** Utiliser matplotlib pour visualisation (pas PGPLOT)

---

### Problème #3: Fichiers FITS (Synchronisation I/O)

**Problème:** Comment Python sait quand DIFMAP est terminé?

**Solution:** I/O basé fichier
```python
# 1. Envoyer commandes
proc.stdin.write("read_uv data.fits\nfit\nexit\n")

# 2. Attendre complétion
stdout, stderr = proc.communicate()

# 3. Lire résultats FITS
from astropy.io import fits
hdul = fits.open('output.fits')
```

---

### Problème #4: Compatibilité Version

**Problème:** DIFMAP peut changer entre releases

**Solution:** API SPHERE est stable (20+ ans)
- Python juste génère scripts SPHERE
- Mises à jour C internes transparentes
- Compatibilité rétroactive garantie

---

## TABLEAUX RÉFÉRENCE

### Types Composantes DIFMAP

| Type | Syntaxe | Paramètres | Cas Usage |
|------|---------|-----------|----------|
| **Point** | `add flux x y point` | flux, x, y | Sources non-résolues |
| **Gaussienne** | `add flux x y gaussian major ratio pa` | major, ratio, pa | Sources résolues |  
| **Disque** | `add flux x y disk radius` | radius | Disque uniforme |
| **Anneau** | `add flux x y ring radius` | radius | Anneau elliptique |
| **Rectangle** | `add flux x y rect major ratio pa` | (voir Gaussienne) | Rectangle |

**Paramètres:**
- `flux`: Jy (émission ou absorption)
- `x, y`: Décalages arcseconde centre phase
- `major`: FWHM axe majeur (arcsec)
- `ratio`: Ratio axial mineur/majeur (0-1)
- `pa`: Angle position (degrees, Est depuis Nord)

### Paramètres CLEAN

| Paramètre | Défaut | Plage | Sens |
|-----------|--------|-------|------|
| `niter` | 1000 | 1-∞ | Itérations max |
| `gain` | 0.1 | 0-1 | Gain boucle (fraction pic ôtée par itération) |
| `threshold` | auto | Jy/beam | Arrêter quand résidu pic < seuil |
| `method` | "normal" | "normal", "sdiff" | Variante algorithme |

### Paramètres Auto-Calibration

| Paramètre | Sens |
|-----------|------|
| `solution_interval` | Intervalle temps solutions gain (secondes) |
| Algorithme | Résout gain complexe par station par intervalle |

### Mots-clés FITS (Données UV)

| Mot-clé | Type | Sens |
|---------|------|------|
| `OBJECT` | char | Nom source |
| `CRVAL1, CRVAL2` | float | RA, Dec (degrees) |
| `CRPIX1, CRPIX2` | float | Pixel référence |
| `CDELT1, CDELT2` | float | Échelle pixel (degrees) |
| `DATE-OBS` | char | Date observation (ISO) |
| `TELESCOP` | char | Nom tableau |
| `INSTRUME` | char | Instrument/projet |

---

## PROCHAINES ÉTAPES

Pour détails implémentation, voir [GUIDE_IMPLEMENTATION.md](GUIDE_IMPLEMENTATION.md).

Pour code spécifique Python wrapper, voir [GUIDE_IMPLEMENTATION.md](GUIDE_IMPLEMENTATION.md) section "Code Complet: DifmapSession".

---

*Dernière Mise à Jour: 4 Mars 2026*
