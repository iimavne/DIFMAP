# GUIDE D'IMPLÉMENTATION - DIFMAP Python Wrapper

**Approche Validée:** Subprocess + Macros SPHERE  
**Timeline:** 4 semaines  
**Status:** Production-ready après Phase 1

---

## TABLE OF CONTENTS

1. [Pourquoi Pas Cython?](#pourquoi-pas-cython)
2. [Architecture Subprocess](#architecture-subprocess)
3. [Implementation Details](#implementation-details)
4. [Code Complet: DifmapSession](#code-complet-difmapsession)
5. [Examples](#examples)
6. [Testing Strategy](#testing-strategy)
7. [4-Week Checklist](#4-week-checklist)

---

## POURQUOI PAS CYTHON?

### Le Problème Fondamental

**Initial proposal (INCORRECT):**
```
Python → Cython Wrapper → libdifmap.so (API publique)
```

**Réalité du code DIFMAP:**
- Exécutable monolithique, pas une librairie
- Globals statiques partout = reentrancy impossible

```c
// Code réel dans difmap_src/
static Observation *ob = NULL;      // Une seule instance globale!
static Model *model = NULL;
static Mapcln *mc = NULL;

// Si on peut wrapper en Cython:
PyInit_cython.fit_model(obs1, model1);  // Init OK
PyInit_cython.fit_model(obs2, model2);  // ❌ SEGFAULT!
                                         // ob réutilisé, memory corruption
```

### Refonte Requise (Non-faisable)

Pour rendre thread-safe:
- Refactoriser 50% du code C
- Tester toutes regressions
- Créer API publique contextualisée
- **Effort:** 6+ mois, maintenance nécessaire
- **Risk:** Très élevé pour code 25 ans

**Verdict:** ❌ **À ignorer complètement.**

---

## ARCHITECTURE SUBPROCESS

### Vue d'Ensemble

```
                    Python Layer
        ┌──────────────────────────────┐
        │    DifmapSession class       │
        │  • read_uv()                 │
        │  • fit_model()               │
        │  • clean()                   │
        │  • save_map()                │
        └──────────────┬───────────────┘
                       │ Generate SPHERE scripts
                       ↓
        ┌──────────────────────────────┐
        │   SPHERE Macro Generator      │
        │  (Python → .scm files)       │
        │                              │
        │  read_uv "data.fits"         │
        │  model()                     │
        │  add 0.5 0 0 gaussian        │
        │  fit                         │
        │  clean 1000 0.1              │
        │  wmap "output.fits"          │
        │  exit                        │
        └──────────────┬───────────────┘
                       │ subprocess.Popen(stdin=PIPE)
                       ↓
        ┌──────────────────────────────┐
        │  DIFMAP Executable (./builddir/difmap)
        │                              │
        │  ✓ Runs in separate process  │
        │  ✓ Pure SPHERE interpreter   │
        │  ✓ C algorithms unchanged    │
        │  ✓ No memory corruption      │
        │  ✓ Full isolation            │
        └──────────────┬───────────────┘
                       │ FITS + Log output
                       ↓
        ┌──────────────────────────────┐
        │   Python Result Parsing       │
        │  • Read FITS (astropy)       │
        │  • Parse logs                │
        │  • Matplotlib visualization  │
        │  • Return to caller          │
        └──────────────────────────────┘
```

### Key Advantages

| Feature | Cython | Subprocess |
|---------|--------|-----------|
| **Refactoring needed** | 50% code | 0 lines |
| **Thread safety** | ❌ Risky | ✅ OS-level isolation |
| **Parallel sessions** | ❌ Crashes | ✅ Multiple processes OK |
| **DIFMAP modifications** | ✅ Yes, extensive | ✅ No, unchanged |
| **Timeline** | 6+ months | 4 weeks |
| **Maintenance burden** | High (API breakage) | Low (subprocess stable) |
| **Learning curve** | Cython + C deep knowledge | Python + SPHERE basics |
| **Debugging** | Complex (Cython layer) | Simple (pipe inspection) |
| **Testing** | Unit + integration hard | Easy (process isolation) |
| **Production risk** | **Very high** | **Low** |

---

## IMPLEMENTATION DETAILS

### What is SPHERE?

**SPHERE = Macro Language built into DIFMAP**

It's Turing-complete and orchestrates all C algorithms:

```sphere
# Variables
set flux 1.0
set x_offset 0.001

# Control flow
for i=1 to 10
  if i > 5
    add $flux $x_offset 0 gaussian
    fit
  else
    print "Iteration $i"
  endif
end

# Call C algorithms
read_uv "data.fits"
model
clean 1000 0.1
wmap "output.fits"
```

**Python's job:** Generate SPHERE scripts dynamically.

### File-Based IPC

**How synchronization works:**

```python
session.execute("""
read_uv "{uv_file}"
observ
write_log "{log_output}"
exit
""")

# Python monitors:
# 1. difmap.log grows (tail -f pattern)
# 2. When "exit" command arrives, log complete
# 3. Read FITS results via astropy.fits
```

### Process Lifecycle

```python
# 1. CREATE PROCESS
proc = subprocess.Popen(
    ["./builddir/difmap"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# 2. SEND SCRIPT
script = "read_uv data.fits\n..."
proc.stdin.write(script)
proc.stdin.flush()

# 3. WAIT FOR COMPLETION (monitor output)
stdout, stderr = proc.communicate(timeout=300)

# 4. CLOSE PROCESS (automatic on context exit)
proc.terminate()
```

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
