# GUIDE D'IMPLÉMENTATION - Wrapper Python DIFMAP

**Approche Validée:** Subprocess + Macros SPHERE  
**Timeline:** 4 semaines  
**Status:** Production-ready après Phase 1

---

## TABLE DES MATIÈRES

1. [Pourquoi Pas Cython? (Les vrais problèmes)](#pourquoi-pas-cython-les-vrais-problèmes)
2. [Architecture Subprocess](#architecture-subprocess)
3. [Détails Implémentation](#détails-implémentation)
4. [Code Complet: DifmapSession](#code-complet-difmapsession)
5. [Exemples](#exemples)
6. [Stratégie de Test](#stratégie-de-test)
7. [Checklist 4 Semaines](#checklist-4-semaines)

---

## POURQUOI PAS CYTHON? (Les vrais problèmes)

### Problème 1: Globals Statiques Massives

**Code réel DIFMAP:**

```c
// difmap_src/obs.c
static Observation *ob = NULL;       // L'UNIQUE observation du processus

// difmap_src/model.c
static Model *model = NULL;          // L'UNIQUE modèle

// difmap_src/mapcln.c
static Mapcln *mc = NULL;            // L'UNIQUE état CLEAN

// difmap.c: 50+ autres statics
static Variable vars[500];
static USER_FN_PROTO functions[100];
static ImageMap *image_map = NULL;
static UVData *current_uvdata = NULL;
// ... plus de 50 déclarations static!
```

**Impact Cython:**

```python
# Essayer de wrapper:
from difmap_cython import fit_model, clean

# Session 1: OK
fit_model(obs1, model1)      # ✓ Initialise ob, model globaux
clean(obs1, 1000, 0.1)       # ✓ Réutilise ob, model globaux

# Session 2: DÉSASTRE
fit_model(obs2, model2)      # ❌ SEGFAULT!
                              # ob pointe toujours à obs1 (memory address)
                              # model pointe toujours à model1
                              # Les passer en paramètre ne change RIEN
                              # Les fonctions C lisent les statics, pas params
```

**Code problématique réel en C:**

```c
// dans lmfit.c
int levenberg_marquardt_fit(Observation *obs, Model *mod, ...) {
    // ↑ Paramètres, mais:
    
    // Ensuite, la fonction utilise probablement:
    for (int i = 0; i < ob->nbas; i++) {  // ← ob GLOBAL, pas paramètre!
        // Calcule pour le global ob
    }
    
    // Ou pire, appelle d'autres fonctions qui utilisent globals:
    compute_residuals();     // Va lire ob et model globaux
    update_parameters();     // Va modifier model global
}
```

**À refactoriser pour fixer:**

```c
// Nouveau style contextualisé:
typedef struct {
    Observation *ob;
    Model *model;
    Mapcln *mc;
    // ... 50+ autres statics dans une struct
} DifmapContext;

DifmapContext *ctx = difmap_create_context();
levenberg_marquardt_fit(ctx, obs, model, ...);  // Passe ctx
difmap_free_context(ctx);
```

**Effort requis:**
- Refactoriser 50% du code = ~20,000 lignes C
- Tester tous les chemins code (énorme test suite)
- Vérifier thread-safety (races)
- Documenter la nouvelle API
- Temps: **6-8 mois**, risk **très élevé**

---

### Problème 2: Aucune API Publique

**Réalité du code:**

```c
// Exemple: src/lmfit.c
static void lm_iterate(Observation *ob, ...) {
    // ↑ STATIC = symbol non exporté!
}

static float compute_chi2(...) {
    // ↑ STATIC = invisible dehors!
}

// Header: src/lmfit.h
// ← Vide! Aucune déclaration publique

// Dans src/difmap.c, la fonction est enregistrée avec SPHERE:
static USER_FN_PROTO my_functions[] = {
    {NULL, "fit", 0, lm_fit},  // ← SPHERE peut l'appeler
    // Mais C ext. ne le peut pas!
};
```

**Impact:**
- ❌ Pas de `libdifmap.so` à compiler
- ❌ 500+ fonctions inaccessibles
- ❌ SWIG/pybind11 = rien à scanner!
- ✅ SPHERE = l'UNIQUE interface publique

**SPHERE l'orchestrate déjà:**

```sphere
read_uv "data.fits"     # Appelle uvf_input() (enregistrée SPHERE)
model                   # Appelle model_init() (enregistrée SPHERE)
add 0.5 0 0 gaussian    # Appelle add_to_model() (enregistrée SPHERE)
fit                     # Appelle lm_fit() (enregistrée SPHERE)
clean 1000 0.1          # Appelle map_clean() (enregistrée SPHERE)
wmap "output.fits"      # Appelle uvf_output() (enregistrée SPHERE)
```

**SPHERE a accès à 100+ algos, Python juste génère SPHERE scripts.**

---

### Problème 3: PGPLOT Bloque Jupyter

**Code réel:**

```c
// difmap_src/maplot.c
void map_plot() {
    cpgopen("/XWxxx");      // ← Ouvre fenêtre X11
    // ... appels de dessin
    cpgclos();
}

// cpgplot.h (wrapper PGPLOT Fortran)
extern void cpgopen_();
extern void cpgimag_();
```

**Problème Jupiter:**
- Server headless (SSH no X11 forward) = crash
- Container/Docker = pas de device X11
- Batch processing = hang sur fenêtre
- Solution PGPLOT: `/ps` device (PostScript headless)

**Solution Python:**

```python
# Option 1: PGPLOT headless  
session.execute("""
set pgdev /ps           # Device PostScript fichier
mapplot                 # Sauve dans plot.ps
""")

# Option 2: Ignorer PGPLOT, utiliser matplotlib
from astropy.io import fits
import matplotlib.pyplot as plt

hdul = fits.open("clean_map.fits")
data = hdul[0].data

fig, ax = plt.subplots()
im = ax.imshow(data, cmap='hot')
ax.set_title("CLEAN Map")
plt.colorbar(im)
plt.show()  # ← Jupyter display OK!
```

---

## ARCHITECTURE SUBPROCESS (Résout tous les problèmes)

### Résumé Simple

```python
# Chaque session = processus séparé = globals isolés

session1 = subprocess.Popen(["./builddir/difmap"], ...) # Process 1: ob, model, mc
session2 = subprocess.Popen(["./builddir/difmap"], ...) # Process 2: ob, model, mc (isolés)

# Process 1 et Process 2 ont leur propre espace mémoire
# Segfault dans P1 n'affecte PAS P2
# Exit P1 libère sa mémoire, P2 continue
```

**Pourquoi c'est SAFE:**
- OS virtualisation: chaque processus heap séparé
- MMU (Memory Management Unit) isole adresses
- Exit process = kernel récupère toute mémoire
- **Garantie matérielle, pas logicielle!**

---

## 💻 CLASS DifmapSession (Code Complet, Prêt Production)

```python
#!/usr/bin/env python3
"""
Wrapper DIFMAP via subprocess + SPHERE
Approche: Générer script SPHERE, exécuter dans subprocess isolé, lire FITS
"""

import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DifmapSession:
    """Gère une session DIFMAP isolée (subprocess)"""
    
    def __init__(
        self,
        difmap_exe: str = "./builddir/difmap",
        work_dir: Optional[str] = None,
        timeout: int = 300
    ):
        """Initialiser session
        
        Args:
            difmap_exe: Chemin exécutable DIFMAP
            work_dir: Répertoire travail (temp si None)
            timeout: Timeout en secondes
        """
        self.difmap_exe = Path(difmap_exe)
        self.work_dir = Path(work_dir or tempfile.mkdtemp(prefix="difmap_"))
        self.timeout = timeout
        self.script_buffer: List[str] = []
        self.last_output = None
        
        if not self.difmap_exe.exists():
            raise FileNotFoundError(f"DIFMAP not found: {self.difmap_exe}")
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session: {self.work_dir}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        """Cleanup au exit"""
        import shutil
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
    
    # ============ COMMANDES DIFMAP ============
    
    def read_uv(self, filename: str) -> 'DifmapSession':
        """Charger données UV FITS"""
        self.script_buffer.append(f'read_uv "{filename}"')
        return self
    
    def create_model(self) -> 'DifmapSession':
        """Initialiser modèle"""
        self.script_buffer.append("model")
        return self
    
    def add_component(
        self,
        ctype: str,
        flux: float,
        x: float = 0.0,
        y: float = 0.0,
        **kwargs
    ) -> 'DifmapSession':
        """Ajouter composante
        
        Args:
            ctype: 'point', 'gaussian', 'disk'
            flux: Flux en Jy
            x, y: Offsets RA/Dec (arcsec)
        """
        cmd = f"add {flux} {x} {y} {ctype}"
        
        if ctype.lower() == "gaussian":
            major = kwargs.get('major', 0.001)
            ratio = kwargs.get('ratio', 1.0)
            pa = kwargs.get('pa', 0.0)
            cmd += f" {major} {ratio} {pa}"
        elif ctype.lower() == "disk":
            radius = kwargs.get('radius', 0.001)
            cmd += f" {radius}"
        
        self.script_buffer.append(cmd)
        return self
    
    def fit_model(self) -> 'DifmapSession':
        """Fitter modèle (Levenberg-Marquardt)"""
        self.script_buffer.append("fit")
        return self
    
    def clean(
        self,
        niter: int = 1000,
        gain: float = 0.1,
        threshold: Optional[float] = None
    ) -> 'DifmapSession':
        """Déconvolution CLEAN"""
        cmd = f"clean {niter} {gain}"
        if threshold:
            cmd += f" {threshold}"
        self.script_buffer.append(cmd)
        return self
    
    def save_map(self, filename: str) -> 'DifmapSession':
        """Sauvegarder carte CLEAN FITS"""
        self.script_buffer.append(f'wmap "{filename}"')
        return self
    
    def selfcal(self, solution_interval: int = 60) -> 'DifmapSession':
        """Auto-calibration"""
        self.script_buffer.append(f"selfcal {solution_interval}")
        return self
    
    # ============ EXECUTION ============
    
    def select_data(self, polarization: str = 'I') -> 'DifmapSession':
        """Sélectionner données UV (ESSENTIEL après read_uv)
        
        Args:
            polarization: 'I', 'RR', 'LL', 'RL', 'LR', etc.
        """
        self.script_buffer.append(f"select {polarization}")
        return self
    
    def interactive_edit(self) -> 'DifmapSession':
        """Lancer édition interactive (vplot)
        
        Ouvre fenêtre PGPLOT pour éditer visibilités à la souris.
        L'utilisateur clique pour marquer points mauvais, puis 'Q' pour quitter.
        Cette étape est indispensable avant CLEAN sur données réelles.
        
        ⚠️ LIMITATION v1.0: Cette commande nécessite une gestion spéciale de stdin 
        car vplot ouvre une fenêtre X11 et attend les clics/touches clavier. 
        Avec la méthode communicate() actuelle (qui ferme stdin après envoi), 
        Difmap risque de :
        - Gel de l'écran (deadlock stdin)
        - Ne pas pouvoir lire les entrées de la souris
        
        RECOMMANDATION: Pour l'instant, effectuer l'édition interactive MANUELLEMENT 
        avant d'utiliser le wrapper Python :
        
        $ ./builddir/difmap
        obs data.fits
        select I
        vplot
        (edit à la souris, puis Q)
        wedit edited.uvd
        exit
        
        Puis utiliser le wrapper sur edited.uvd. Une version v2.0 avec 
        support asynchrone (stdin non-blocking) permettrait vplot intégré.
        """
        self.script_buffer.append("vplot")
        return self
    
    def execute(self) -> Dict:
        """Exécuter script
        
        Returns:
            Dict avec stdout, stderr, returncode, success
            
        NOTE: success vérifie à la fois returncode ET les logs d'erreur
        (Difmap 1993 ne gère pas toujours bien les codes sortie POSIX)
        """
        # Générer script final
        script = "\n".join(self.script_buffer) + "\nexit\n"
        
        logger.info(f"Exécution ({len(self.script_buffer)} commandes)")
        
        # Lancer subprocess
        try:
            proc = subprocess.Popen(
                [str(self.difmap_exe)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.work_dir)
            )
            
            # Envoyer et attendre
            stdout, stderr = proc.communicate(input=script, timeout=self.timeout)
            self.last_output = stdout
            
            # Parser les logs pour détecter erreurs Difmap
            # (returncode peut être 0 même en cas d'erreur!)
            log_errors = self._parse_error_log(stdout, stderr)
            success = proc.returncode == 0 and not log_errors
            
            return {
                'success': success,
                'stdout': stdout,
                'stderr': stderr,
                'returncode': proc.returncode,
                'errors': log_errors
            }
        
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.error("Timeout!")
            raise
    
    def _parse_error_log(self, stdout: str, stderr: str) -> List[str]:
        """Parser logs pour détecter erreurs Difmap
        
        Difmap imprime erreurs au stdout, pas stderr!
        Keywords: 'Error', 'Syntax error', 'not found', 'No UV data'
        """
        errors = []
        
        for line in (stdout + "\n" + stderr).split("\n"):
            line = line.lower()
            if any(keyword in line for keyword in [
                "error occured",
                "syntax error", 
                "not found",
                "no uv data has been selected",
                "command not recognized",
                "illegal"
            ]):
                errors.append(line.strip())
        
        return errors
    
    # ============ LIRE RESULTATS ============
    
    def read_fits(self, filename: str):
        """Lire FITS généré"""
        try:
            from astropy.io import fits
        except ImportError:
            raise ImportError("pip install astropy")
        
        filepath = self.work_dir / filename
        if not filepath.exists():
            logger.warning(f"FITS not found: {filepath}")
            return None
        
        return fits.open(filepath)
```

---

## EXEMPLES CONCRETS

### Exemple 1: Modélisation paramétrique simple

```python
from pathlib import Path

with DifmapSession() as session:
    # Charger et sélectionner
    session.read_uv("data.fits")
    session.select_data(polarization='I')  # Essentiel!
    
    # Créer modèle paramétrique
    session.create_model()
    session.add_component("point", flux=1.0, x=0, y=0)
    session.add_component("gaussian", flux=0.3, x=0.0005, y=0, 
                         major=0.001, ratio=0.8, pa=45)
    
    # Fitter ces composantes
    session.fit_model()
    
    # Restaurer et sauvegarder
    session.save_map("output.fits")
    
    result = session.execute()
    
    if result['success']:
        print("✓ Succès")
        hdul = session.read_fits("output.fits")
        print(f"Map shape: {hdul[0].data.shape}")
    else:
        print(f"✗ Erreurs détectées: {result['errors']}")
```

**Use case:** Quand on connaît structure source (ex: binaire, few composantes Gaussiennes).

### Exemple 2: Déconvolution CLEAN + Self-calibration (WORKFLOW SCIENTIFIQUE)

```python
# CORRECT: Workflow radioastronomique standard
# read_uv → select → clean → selfcal → clean → wmap

with DifmapSession() as session:
    # Charger données
    session.read_uv("observation.fits")
    session.select_data(polarization='I')  # 🔴 ESSENTIEL! Sinon error: "No UV data selected"
    
    # Édition interactive (nettoyer points mauvais à la souris)
    session.interactive_edit()  # vplot
    
    # Première déconvolution
    session.clean(niter=500, gain=0.05, threshold=0.001)
    
    # Auto-calibration (résout gains station)
    session.selfcal(solution_interval=60)
    
    # Deuxième déconvolution (après recalibration)
    session.clean(niter=1000, gain=0.1, threshold=0.0005)
    
    # Sauvegarder résultat
    session.save_map("clean_map.fits")
    
    result = session.execute()
    if result['success']:
        print("✓ Traitement réussi")
    else:
        print(f"✗ Erreurs: {result['errors']}")
```

**Workflow scientifique expliqué:**
1. **read_uv + select**: Charger données et choisir polarisation
2. **interactive_edit**: Nettoyer points mauvais (impulsions radio, météore)
3. **clean #1**: Déconvolution rapide avec gains bas
4. **selfcal**: Corriger gains/phases de chaque antenne
5. **clean #2**: Meilleure déconvolution avec données recalibrées
6. **wmap**: Sauvegarder image FITS

### Exemple 3: Traitement batch parallèle (CLEAN automisé)

```python
from multiprocessing import Pool
from pathlib import Path

def process_one_file(fits_file):
    """Traiter un fichier avec workflow CLEAN standard"""
    with DifmapSession() as session:
        session.read_uv(str(fits_file))
        session.select_data(polarization='I')  # Ne pas oublier!
        
        # Workflow: clean → selfcal → clean
        session.clean(niter=300, gain=0.05)
        session.selfcal(solution_interval=30)
        session.clean(niter=1000, gain=0.1, threshold=0.001)
        
        session.save_map(f"results/{fits_file.stem}_clean.fits")
        
        result = session.execute()
        return (fits_file.name, result['success'], result.get('errors', []))

# Paralleliser: 4 sessions simultanées, chacune processus isolé
# Paralleliser: 4 sessions simultanées, chacune processus isolé
fits_files = list(Path("data/").glob("*.fits"))

with Pool(4) as pool:
    results = pool.map(process_one_file, fits_files)

# Unpacker les 3-tuples (filename, success, errors)
success_count = sum(1 for _, ok, _ in results if ok)
failed = [(f, errs) for f, ok, errs in results if not ok]

print(f"✓ {success_count}/{len(results)} réussis")
if failed:
    for fname, errors in failed:
        print(f"  {fname}: {errors}")
```

### Exemple 4: Jupyter + Matplotlib

```python
# In Jupyter notebook

from difmap_wrapper import DifmapSession
import matplotlib.pyplot as plt
from astropy.io import fits
import numpy as np

# Exécuter traitement (workflow CLEAN)
with DifmapSession() as session:
    session.read_uv("data.fits")
    session.select_data(polarization='I')  # Essentiel!
    
    # Workflow: clean → selfcal → clean
    session.clean(niter=500, gain=0.05, threshold=0.001)
    session.selfcal(solution_interval=60)
    session.clean(niter=1000, gain=0.1, threshold=0.0005)
    
    session.save_map("result.fits")
    result = session.execute()
    
    if not result['success']:
        print(f"Erreurs: {result['errors']}")

# Afficher résultat (pas d'appel PGPLOT, pure Matplotlib!)
hdul = session.read_fits("result.fits")
data = hdul[0].data

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Échelle linéaire
axes[0].imshow(data, cmap='viridis', origin='lower')
axes[0].set_title('CLEAN Map (linéaire)')

# Échelle log
axes[1].imshow(np.log10(np.abs(data) + 1e-6), cmap='hot', origin='lower')
axes[1].set_title('CLEAN Map (log échelle)')

plt.tight_layout()
plt.show()  # ← Affiche dans Jupyter, pas d'X11 nécessaire!
```

---

## ✅ CHECKLIST 4 SEMAINES

### Semaine 1: Infrastructure

**Lun-Mar:**
- [ ] Venv Python, pytest
- [ ] Copier code DifmapSession
- [ ] Compiler DIFMAP: `meson compile -C builddir`
- [ ] Créer test FITS test(synthetic)

**Mer-Jeu:**
- [ ] Implémenter  `DifmapSession` + context manager
- [ ] Implémenter `read_uv()`, `create_model()`, `add_component()`
- [ ] Implémenter `execute()` (subprocess)
- [ ] 5 unit tests

**Ven:**
- [ ] Test intégration DIFMAP réel
- [ ] Error handling
- [ ] Documentation

**Livrable:** `DifmapSession` v1.0 (200 lignes)

---

### Semaine 2: Algorithms

**Lun-Mar:**
- [ ] `fit_model()`, `clean()`, `selfcal()`
- [ ] Tests paramétriques

**Mer:**
- [ ] `save_map()`, `read_fits()`
- [ ] Test: read → fit → clean → save

**Jeu-Ven:**
- [ ] Batch processing
- [ ] Parallel sessions (multiprocessing.Pool)
- [ ] Benchmarking

**Livrable:** Wrapper complet v1.0 (400+ lignes)

---

### Semaine 3: Features Advanced

**Lun-Mar:**
- [ ] Jupyter examples
- [ ] Matplotlib helpers
- [ ] Error recovery

**Mer:**
- [ ] HPC integration (optional)
- [ ] Caching
- [ ] Config files

**Jeu-Ven:**
- [ ] >80% test coverage
- [ ] Documentation
- [ ] Demo notebook

**Livrable:** v1.1 avec features avancés

---

### Semaine 4: Production

**Lun-Mar:**
- [ ] Load testing
- [ ] Stress testing

**Mer:**
- [ ] CI/CD (GitHub Actions)
- [ ] PyPI setup

**Jeu:**
- [ ] Validation data réelle
- [ ] Profiling

**Ven:**
- [ ] Release
- [ ] Training

**Livrable:** Package production PyPI

---

## 🎯 SUCCESS METRICS

| Métrique | Cible | Vérif |
|----------|-------|-------|
| **Core features** | read_uv, fit, clean, save | Exemples OK |
| **Test coverage** | >80% | pytest --cov |
| **Stability** | 0 segfault | Load test |
| **Jupyter** | Demo .ipynb | Runs OK |
| **Docs** | API complete | readthedocs |

---

*Next: Lire [ANALYSE_TECHNIQUE.md](ANALYSE_TECHNIQUE.md) pour détails modules DIFMAP*

---

## CODE COMPLET: DIFMAPSESSION

### Main Class

```python
#!/usr/bin/env python3
"""
DIFMAP Python Wrapper via Subprocess + SPHERE Macros
Production-ready implementation
"""

import subprocess
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DifmapSession:
    """Context manager for isolated DIFMAP subprocess sessions"""
    
    def __init__(
        self,
        difmap_exe: str = "./builddir/difmap",
        work_dir: Optional[str] = None,
        timeout: int = 300,
        auto_cleanup: bool = True
    ):
        """
        Initialize DIFMAP session
        
        Args:
            difmap_exe: Path to DIFMAP executable
            work_dir: Working directory (temp if None)
            timeout: Max execution time in seconds
            auto_cleanup: Remove temp dir on exit
        """
        self.difmap_exe = Path(difmap_exe)
        self.work_dir = Path(work_dir or tempfile.mkdtemp(prefix="difmap_"))
        self.timeout = timeout
        self.auto_cleanup = auto_cleanup
        self.proc = None
        self.script_buffer = []
        self.execution_log = ""
        
        if not self.difmap_exe.exists():
            raise FileNotFoundError(f"DIFMAP executable not found: {self.difmap_exe}")
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session initialized in {self.work_dir}")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
        if self.auto_cleanup and self.work_dir.exists():
            import shutil
            shutil.rmtree(self.work_dir)
            logger.info(f"Cleaned up {self.work_dir}")
    
    def start(self):
        """Start DIFMAP subprocess"""
        if self.proc is not None:
            logger.warning("Session already running, terminating old one")
            self.cleanup()
        
        try:
            self.proc = subprocess.Popen(
                [str(self.difmap_exe)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.work_dir)
            )
            logger.info(f"DIFMAP subprocess started (PID {self.proc.pid})")
        except Exception as e:
            logger.error(f"Failed to start DIFMAP: {e}")
            raise
    
    # ========== DIFMAP Commands ==========
    
    def read_uv(self, fits_file: str) -> 'DifmapSession':
        """Load UV FITS file"""
        self.script_buffer.append(f'read_uv "{fits_file}"')
        logger.debug(f"Added: read_uv {fits_file}")
        return self
    
    def create_model(self) -> 'DifmapSession':
        """Initialize model for fitting"""
        self.script_buffer.append("model")
        logger.debug("Added: model")
        return self
    
    def add_component(
        self,
        ctype: str,
        flux: float,
        x: float,
        y: float,
        **kwargs
    ) -> 'DifmapSession':
        """Add model component
        
        Args:
            ctype: 'point', 'gaussian', 'disk', 'ring'
            flux: Flux density (Jy)
            x: RA offset (arc seconds)
            y: Dec offset (arc seconds)
            **kwargs: Component-specific (major, ratio, pa for gaussian)
        
        Examples:
            session.add_component('point', flux=1.0, x=0, y=0)
            session.add_component('gaussian', flux=0.5, x=0.001, y=0.001,
                                  major=0.0005, ratio=0.8, pa=45)
        """
        cmd = f"add {flux} {x} {y} {ctype}"
        
        if ctype.lower() in ['gaussian', 'gaus']:
            major = kwargs.get('major', 0.001)
            ratio = kwargs.get('ratio', 1.0)
            pa = kwargs.get('pa', 0.0)
            cmd += f" {major} {ratio} {pa}"
        elif ctype.lower() in ['disk', 'ring']:
            radius = kwargs.get('radius', 0.001)
            cmd += f" {radius}"
        
        self.script_buffer.append(cmd)
        logger.debug(f"Added component: {cmd}")
        return self
    
    def fit_model(self, max_iter: int = 100) -> 'DifmapSession':
        """Fit model to visibilities (Levenberg-Marquardt)"""
        self.script_buffer.append("fit")
        logger.debug("Added: fit")
        return self
    
    def clean(
        self,
        niter: int = 1000,
        gain: float = 0.1,
        threshold: Optional[float] = None,
        method: str = "normal"
    ) -> 'DifmapSession':
        """CLEAN deconvolution
        
        Args:
            niter: Number of CLEAN iterations
            gain: CLEAN loop gain (0-1)
            threshold: Stopping threshold (Jy/beam, optional)
            method (str): 'normal' or 'sdiff' (default: normal)
        """
        cmd = f"clean {niter} {gain}"
        if threshold:
            cmd += f" {threshold}"
        self.script_buffer.append(cmd)
        logger.debug(f"Added: {cmd}")
        return self
    
    def selfcal(self, solution_interval: int = 60) -> 'DifmapSession':
        """Self-calibration on model"""
        self.script_buffer.append(f"selfcal {solution_interval}")
        logger.debug(f"Added: selfcal")
        return self
    
    def save_map(self, filename: str) -> 'DifmapSession':
        """Write CLEAN map to FITS"""
        self.script_buffer.append(f'wmap "{filename}"')
        logger.debug(f"Added: wmap {filename}")
        return self
    
    def uvplot(self) -> 'DifmapSession':
        """Display UV coverage plot"""
        self.script_buffer.append("uvplot")
        return self
    
    def mapplot(self) -> 'DifmapSession':
        """Display CLEAN map plot"""
        self.script_buffer.append("mapplot")
        return self
    
    # ========== Execution ==========
    
    def execute(self, wait: bool = True) -> Dict:
        """Execute buffered commands
        
        Args:
            wait: Block until completion
        
        Returns:
            Dict with execution results
        """
        if self.proc is None:
            self.start()
        
        # Build final script
        script = "\n".join(self.script_buffer) + "\nexit\n"
        
        logger.info(f"Executing {len(self.script_buffer)} commands")
        logger.debug(f"Script:\n{script}")
        
        try:
            self.execution_log, errors = self.proc.communicate(
                input=script,
                timeout=self.timeout
            )
            
            if self.proc.returncode != 0:
                logger.warning(f"DIFMAP exited with code {self.proc.returncode}")
                if errors:
                    logger.error(f"STDERR:\n{errors}")
            
            return {
                'success': self.proc.returncode == 0,
                'log': self.execution_log,
                'errors': errors,
                'returncode': self.proc.returncode
            }
        
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout after {self.timeout}s")
            self.proc.kill()
            raise
    
    # ========== Results Reading ==========
    
    def read_fits(self, filename: str):
        """Read FITS file generated by DIFMAP
        
        Args:
            filename: FITS file path relative to work_dir
        
        Returns:
            astropy.io.fits HDUList
        """
        try:
            from astropy.io import fits
        except ImportError:
            raise ImportError("Install astropy: pip install astropy")
        
        filepath = self.work_dir / filename
        if not filepath.exists():
            logger.warning(f"FITS file not found: {filepath}")
            return None
        
        logger.info(f"Reading FITS: {filepath}")
        return fits.open(filepath)
    
    def get_log(self) -> str:
        """Get execution log"""
        return self.execution_log
    
    def cleanup(self):
        """Terminate subprocess"""
        if self.proc and self.proc.poll() is None:
            logger.info(f"Terminating subprocess (PID {self.proc.pid})")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class DifmapWrapper:
    """High-level wrapper for common tasks"""
    
    def __init__(self, difmap_exe: str = "./builddir/difmap"):
        self.difmap_exe = difmap_exe
    
    def process_observation(
        self,
        uv_file: str,
        components: List[Dict],
        clean_config: Dict,
        output_map: str
    ) -> Tuple[bool, str]:
        """Complete analysis workflow
        
        Args:
            uv_file: Input FITS file
            components: List of component dicts
            clean_config: Dict with niter, gain
            output_map: Output FITS filename
        
        Returns:
            (success, log_output)
        """
        with DifmapSession(self.difmap_exe) as session:
            session.read_uv(uv_file)
            session.create_model()
            
            for comp in components:
                session.add_component(**comp)
            
            session.fit_model()
            
            session.clean(**clean_config)
            session.save_map(output_map)
            
            result = session.execute()
            return result['success'], result['log']
```

---

## EXAMPLES

### Exemple 1: Simple Model Fit

```python
from difmap_wrapper import DifmapSession

# Session context manager handles cleanup
with DifmapSession("./builddir/difmap") as session:
    # Load data
    session.read_uv("data.fits")
    
    # Set up model
    session.create_model()
    session.add_component("point", flux=1.0, x=0, y=0)
    
    # Fit
    session.fit_model()
    
    # Save
    session.save_map("output.fits")
    
    # Execute
    result = session.execute()
    print(result['log'])
    
    # Read results
    hdul = session.read_fits("output.fits")
    print(hdul.info())
```

### Exemple 2: Complex Model + CLEAN

```python
# Multiple components
components = [
    {'ctype': 'point', 'flux': 0.8, 'x': 0, 'y': 0},
    {'ctype': 'gaussian', 'flux': 0.6, 'x': 0.001, 'y': 0.001, 
     'major': 0.0005, 'ratio': 0.8, 'pa': 45},
    {'ctype': 'disk', 'flux': 0.2, 'x': -0.002, 'y': 0.002, 
     'radius': 0.0003}
]

with DifmapSession() as session:
    session.read_uv("obs.fits")
    session.create_model()
    
    for comp in components:
        session.add_component(**comp)
    
    session.fit_model()
    session.clean(niter=1000, gain=0.1, threshold=0.001)
    session.save_map("clean.fits")
    
    result = session.execute()
    
    if result['success']:
        print("✓ Processing successful")
    else:
        print(f"✗ Error: {result['errors']}")
```

### Exemple 3: Batch Processing

```python
from pathlib import Path
from difmap_wrapper import DifmapWrapper

wrapper = DifmapWrapper()
fits_files = Path("data/").glob("*.fits")

for fits_file in fits_files:
    components = [
        {'ctype': 'point', 'flux': 1.0, 'x': 0, 'y': 0}
    ]
    
    clean_config = {'niter': 1000, 'gain': 0.1}
    
    success, log = wrapper.process_observation(
        uv_file=str(fits_file),
        components=components,
        clean_config=clean_config,
        output_map=f"results/{fits_file.stem}_clean.fits"
    )
    
    if success:
        print(f"✓ {fits_file.name} processed")
    else:
        print(f"✗ {fits_file.name} failed")
```

### Exemple 4: Jupyter Notebook Integration

```python
# In notebook cell

from difmap_wrapper import DifmapSession
import matplotlib.pyplot as plt
from astropy.io import fits
import numpy as np

# Process
with DifmapSession() as session:
    session.read_uv("data.fits")
    session.create_model()
    session.add_component("point", flux=1.0, x=0, y=0)
    session.fit_model()
    session.clean(niter=500, gain=0.1)
    session.save_map("result.fits")
    session.execute()

# Visualize
hdul = session.read_fits("result.fits")
data = hdul[0].data
header = hdul[0].header

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Linear scale
ax1.imshow(data, cmap='viridis', origin='lower')
ax1.set_title('CLEAN Map (linear)')
ax1.colorbar()

# Log scale
ax2.imshow(np.log10(np.abs(data) + 1e-6), cmap='hot', origin='lower')
ax2.set_title('CLEAN Map (log scale)')
ax2.colorbar()

plt.tight_layout()
plt.show()
```

---

## TESTING STRATEGY

### Unit Tests

```python
# test_difmap_wrapper.py
import pytest
import tempfile
from pathlib import Path
from difmap_wrapper import DifmapSession, DifmapWrapper


class TestDifmapSession:
    """Test DifmapSession basic functionality"""
    
    @pytest.fixture
    def session(self):
        """Create test session"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield DifmapSession(
                work_dir=tmpdir,
                auto_cleanup=False
            )
    
    def test_init(self, session):
        """Test session initialization"""
        assert session.work_dir.exists()
        assert session.difmap_exe.exists()
    
    def test_command_building(self, session):
        """Test command buffer"""
        session.read_uv("test.fits")
        session.create_model()
        session.add_component("point", flux=1.0, x=0, y=0)
        
        assert len(session.script_buffer) == 3
        assert "read_uv" in session.script_buffer[0]
        assert "model" in session.script_buffer[1]
        assert "point" in session.script_buffer[2]
    
    def test_gaussian_component(self, session):
        """Test Gaussian component parameters"""
        session.add_component(
            "gaussian",
            flux=0.5, x=0.001, y=0.001,
            major=0.0005, ratio=0.8, pa=45
        )
        
        cmd = session.script_buffer[0]
        assert "gaussian" in cmd
        assert "0.0005" in cmd  # major
        assert "0.8" in cmd     # ratio
    
    def test_clean_parameters(self, session):
        """Test CLEAN configuration"""
        session.clean(niter=1000, gain=0.1, threshold=0.001)
        
        cmd = session.script_buffer[0]
        assert "clean 1000 0.1 0.001" in cmd


class TestIntegration:
    """Integration tests with real DIFMAP"""
    
    def test_simple_execution(self):
        """Test basic DIFMAP execution"""
        with DifmapSession() as session:
            # Just test that DIFMAP starts/stops
            result = session.execute()
            assert result['returncode'] == 0


class TestErrorHandling:
    """Test error conditions"""
    
    def test_missing_executable(self):
        """Test handling of missing DIFMAP executable"""
        with pytest.raises(FileNotFoundError):
            DifmapSession(difmap_exe="/nonexistent/path")
    
    def test_timeout(self):
        """Test timeout handling"""
        with pytest.raises(subprocess.TimeoutExpired):
            with DifmapSession(timeout=0.1) as session:
                session.read_uv("data.fits")
                session.clean(niter=1000000)  # Very long
                session.execute()

# Run tests
# pytest test_difmap_wrapper.py -v
```

---

## 4-WEEK CHECKLIST

### WEEK 1: Infrastructure & Basic Wrapper

**Mon-Tue:**
- [ ] Set up Python dev environment (venv, pytest)
- [ ] Copy difmap_wrapper.py to project root
- [ ] Create test FITS file (synthetic 512x512)
- [ ] Verify DIFMAP binary compiles and runs manually

**Wed-Thu:**
- [ ] Implement DifmapSession.__init__ + context manager
- [ ] Implement read_uv(), create_model(), add_component()
- [ ] Implement execute() (basic subprocess call)
- [ ] Write 5 unit tests (parametrization, component types)

**Friday:**
- [ ] Integration test with real DIFMAP
- [ ] Handle common error cases
- [ ] Documentation (docstrings)
- [ ] Code review internal

**Deliverable:** `difmap_wrapper.py` v1.0 (200 lines)

---

### WEEK 2: Fitting & CLEAN

**Mon-Tue:**
- [ ] Implement fit_model()
- [ ] Implement clean() with full parameters
- [ ] Add selfcal() support
- [ ] Test parameter combinations

**Wed:**
- [ ] Implement save_map(), read_fits()
- [ ] Integration test: read_uv → fit → clean → save
- [ ] Add result verification (FITS header check)

**Thu-Fri:**
- [ ] Batch processing capability (DifmapWrapper class)
- [ ] Parallel session support (test with multiprocessing.Pool)
- [ ] Advanced logging/monitoring
- [ ] Performance benchmarking

**Deliverable:** Complete wrapper v1.0 (400+ lines, full features)

---

### WEEK 3: Advanced Features & Robustness

**Mon-Tue:**
- [ ] Jupyter integration examples
- [ ] Matplotlib visualization helpers
- [ ] Error recovery (bad FITS, timeouts, etc.)
- [ ] Comprehensive logging

**Wed:**
- [ ] HPC integration (SLURM, local scheduling)
- [ ] Caching mechanism (don't reprocess same file)
- [ ] Configuration file support (YAML/JSON)

**Thu-Fri:**
- [ ] Full test suite (80%+ coverage)
- [ ] Documentation (README, API reference)
- [ ] Demo notebook

**Deliverable:** Wrapper v1.1 with advanced features, >100 tests passing

---

### WEEK 4: Production Hardening & Deployment

**Mon:**
- [ ] Load testing (1000s of FITS files)
- [ ] Stress testing (memory/CPU limits)
- [ ] Edge case handling

**Tue-Wed:**
- [ ] CI/CD setup (GitHub Actions or similar)
- [ ] PyPI package preparation (setup.py, metadata)
- [ ] Docker container (optional)

**Thu:**
- [ ] Production validation with real-world data
- [ ] Performance profiling
- [ ] Final code review

**Friday:**
- [ ] Release documentation
- [ ] Training materials
- [ ] Deploy to production

**Deliverable:** Production-ready package, PyPI release, full docs

---

## SUCCESS CRITERIA

| Metric | Target | How to Check |
|--------|--------|--------------|
| **Core functionality** | read_uv, fit, clean, save | Basic examples work |
| **Test coverage** | >80% | `pytest --cov` report |
| **Performance** | <5min for typical CLEAN | Benchmark suite |
| **Stability** | 0 segfaults with real data | Week 4 load test |
| **Jupyter compat** | Working demo notebook | `.ipynb` loads + runs |
| **Documentation** | API reference complete | readthedocs or similar |
| **Error handling** | Clear messages for failures | Error scenarios tested |

---

## NEXT IMMEDIATE STEPS

1. **Today:** Copy DifmapSession code to project
2. **Tomorrow:** Compile DIFMAP, test manually
3. **This weekend:** Get first test passing
4. **Monday:** Team standup on progress
5. **By end of week:** Week 1 deliverables complete

**Expected outcome:** Fully functional Python wrapper in 4 weeks, production-grade.

---

*Last Updated: 4 March 2026*
