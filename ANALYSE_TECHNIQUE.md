# ANALYSE TECHNIQUE - Architecture DIFMAP

**Detailed reference for DIFMAP internals and module breakdown**

---

## TABLE OF CONTENTS

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Module Breakdown](#module-breakdown)
4. [Key Data Structures](#key-data-structures)
5. [Critical Interfaces](#critical-interfaces)
6. [SPHERE Macro Language](#sphere-macro-language)
7. [Problem Points & Solutions](#problem-points--solutions)
8. [Reference Tables](#reference-tables)

---

## PROJECT OVERVIEW

### What is DIFMAP?

**DIFMAP** (Difference Mapping Program) is a specialized astronomy software developed at Caltech for:
- Reading UV (visibility) FITS files from VLBI observations
- Building component models (point sources, Gaussians, extended structures)
- Fitting models to radio visibility data using Levenberg-Marquardt
- Performing self-calibration on model residuals
- Deconvolving images using CLEAN algorithm
- Generating publication-quality maps

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total lines of code** | ~100,000 |
| **Primary language** | C |
| **Secondary language** | Fortran (f77main.f entry point) |
| **Build system** | Meson + Ninja |
| **Source files** | 150+ |
| **External libs** | PGPLOT 5.0.2+, GSL, FITS I/O, X11 |
| **Global variables** | 50+ (problem for threading!) |

### Core Workflow

```
1. Read UV FITS file
   └─→ Load visibility amplitudes/phases/flags
   
2. Create model of source
   └─→ Add point/Gaussian/disk components
   
3. Fit model to data
   └─→ Levenberg-Marquardt optimization
   
4. Deconvolve (optional)
   └─→ CLEAN iterations on residuals
   
5. Self-calibrate (optional)
   └─→ Re-solve for station gains/phases
   
6. Save result
   └─→ Output FITS map + model parameters
```

---

## ARCHITECTURE

### Build System

```
meson.build (root config)
├── Detects GNU Fortran, GCC C compiler
├── Checks for PGPLOT library availability
├── Configures optimizations:
│   ├─ C: -O2 (standard optimization)
│   └─ Fortran: -O0 (avoid numerical instabilities)
├── Enables position-independent code (-fPIC)
└── Generates builddir/difmap executable

Ninja build sequence:
├── Static libraries: libsphere.a, libfits.a, libslalib.a, ...
├── Link all libraries
└── Final executable: builddir/difmap
```

### Process Flow

```
┌──────────────────────────────────────────┐
│ Python subproces.Popen() starts difmap   │
├──────────────────────────────────────────┤
│ f77main.f (Fortran entry)                │
│ └─→ Calls C main_difmap()                │
├──────────────────────────────────────────┤
│ sphere.c initializes SPHERE interpreter  │
│ └─→ Registers C function descriptors     │
│     └─→ read_uv, model, add, fit, clean, │
│         selfcal, wmap, etc.              │
├──────────────────────────────────────────┤
│ SPHERE reads commands from stdin         │
│ └─→ Lexical → Parse → Compile → Execute │
├──────────────────────────────────────────┤
│ User commands (or Python script)         │
│ execute C algorithms                     │
│ └─→ Modifies static observation/model    │
├──────────────────────────────────────────┤
│ Output written to:                       │
│ ├─ difmap.log (command output)           │
│ ├─ *.fits (data files)                   │
│ └─ *.ps (PostScript plots)               │
└──────────────────────────────────────────┘
```

---

## MODULE BREAKDOWN

### 1. difmap_src/ - Core Application (85 files)

**Purpose:** Main VLBI imaging algorithms and data structures

#### Sub-modules:

**UV Data Management**
- `obs.c`, `obs.h`: Observation struct (antennae, sources, visibility data)
- `uvf_read.c`, `uvf_write.c`: FITS I/O for UV data
- `subarray.c`: Multi-subarray support
- `obhead.c`: FITS header parsing

**Component Modeling**
- `model.c`, `model.h`: Component definitions (point, Gaussian, disk, ring, ellipse)
- `modeltab.c`: Model table management
- `modfit.c`: Levenberg-Marquardt fitting
- `modvis.c`: Compute synthetic visibilities from model

**Calibration**
- `slfcal.c`: Self-calibration algorithm (solve station gains/phases)
- `telcor.c`: Telescope-specific corrections
- `clphs.c`: Closure phase calculations
- `obutil.c`: Observation utilities

**Deconvolution**
- `mapclean.c`: CLEAN algorithm implementation
- `mapcln.h`: CLEAN state structures
- `newfft.c`: FFT for Fourier transforms

**Visualization**
- `maplot.c`: Map plotting (uses PGPLOT)
- `uvplot.c`: UV coverage plots
- `modplot.c`: Model component plots
- `specplot.c`: Spectral plots

**Mathematical Core**
- `lmfit.c`: Levenberg-Marquardt least-squares fitting
- `matinv.c`: Matrix operations (inversion, multiplication)
- `besj.c`, `besj.h`: Bessel functions J_n
- `dnint.c`: Double-precision integer conversion
- `minmax.c`: Min/max operations
- `fnint.c`: Float integer conversion

**Transformations**
- `uvrotate.c`: UV plane rotation
- `uvtrans.c`: UV coordinate transformations
- `costran.c`: Coordinate system transformations
- `uvaver.c`: UV averaging
- `uvinvert.c`: Vector inversion

**Command Framework**
- `difmap.c` (7778 lines!): Main command processor, variable tables, function registration
- `if.c`: IF/condition processing
- `startup.c`: Initialization
- `version.h`: Version info

**UI/Display**
- `ifpage.c`, `ifpage.h`: IF/window display
- `uvpage.c`, `uvpage.h`: UV page handling
- `mapwin.c`, `mapwin.h`: Map window management
- `dpage.c`, `dpage.h`: Display page handler
- `vedit.c`, `vedit.h`: Visibility editor

**Utilities**
- `symtab.c`: Symbol table management
- `cksum.c`, `cksum.h`: Checksum computation
- `color.c`, `color.h`: Color management
- `units.c`, `units.h`: Unit conversions
- `freelist.c`, `freelist.h`: Memory management
- `markerlist.c`: Marker management
- `planet.c`: Planetary positions
- `pb.c`, `pb.h`: Primary beam

#### Key Data Structures:

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

### 2. sphere_src/ - Macro Interpreter (20 files)

**Purpose:** Turing-complete scripting language for orchestrating DIFMAP algorithms

#### Components:

```
sphere.c         ← Main entry point
├── lex.c        - Lexical scanner (tokenization)
├── compile.c    - Parser & compiler (tokens → bytecode)
├── run.c        - Bytecode interpreter
├── func.c       - Built-in functions (read_uv, clean, fit, etc.)
├── table.c      - Symbol table (variables, arrays)
├── ops.c        - Operators (arithmetic, comparison, logical)
├── var.c        - Variable management
├── plotlib.c    - PGPLOT interface wrapper
└── help.c       - Help system
```

#### SPHERE Language Features:

```sphere
# Variables
set flux 1.5
set x_off 0.001

# Arrays
array src[10]
array data[256, 256]

# Control flow
for i=1 to 100
  if i > 50
    print "Iteration $i"
    add $flux $x_off 0 gaussian
    fit
  else
    print "Early stage"
  endif
end

while condition
  # ... loop body
end

# Arithmetic
set result = (flux * 2.0) + offset

# Function calls (calling C algorithms)
read_uv "data.fits"
model
add 1.0 0 0 point
fit
clean 1000 0.1
wmap "output.fits"

# String manipulation
set filename = "results_" & date & ".fits"
```

#### How SPHERE Connects to C:

```c
// In difmap.c
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
    // ... ~100 more functions
    {NULL, NULL, 0, NULL}
};

static Variable vars[] = {
    {"uvhwhm", R_ONLY, &invpar.uvhwhm, ...},
    {"uvmin", R_ONLY, &invpar.uvmin, ...},
    {"clean_gain", R_WRITE, &mc->gain, ...},
    // ... ~200 more variables
};

// SPHERE registration (in sphere.c):
for each function in my_functions:
    register_function(function.name, function.nargs, function.ptr)
for each variable in vars:
    register_variable(variable.name, variable.ptr, variable.flags)
```

**Key insight:** SPHERE is the **only** way to invoke C algorithms. Python doesn't call C directly—it generates SPHERE scripts.

---

### 3. fits_src/ - FITS Format Support (10 files)

**Purpose:** Read/write FITS files (astronomy standard binary data format)

#### Key Files:

- `fits.c`, `fits.h`: Main FITS routines
- `fits_util.c`: Utility functions
- `fitline.c`: Line reading
- `fitkey.c`: FITS keyword parsing

#### FITS Data Structure:

```c
// Simplified
typedef struct {
    int nhdu;           // Number of HDUs (extensions)
    HDU **hdu;
} Fits;

typedef struct {
    Hdutype type;       // PRIMARY, TABLE, IMAGE, BINTAB
    int naxis;
    long *naxes;        // Dimensions
    Bitpix bitpix;      // Data type
    char **keywords;    // FITS keywords
    void *data;         // Raw data array
} HDU;
```

#### UV FITS Format (Standard):

```
PRIMARY HDU:
  ├─ GROUPS= T (grouped table format)
  ├─ PSCAL, PZERO (scaling factors)
  └─ PARANGLE, source data

RANDOM GROUP Extensions:
  ├─ Complex visibility (u, v, w coordinates)
  ├─ Amplitude, phase, weight
  ├─ Time, station info
  └─ ~200 parameters per visibility
```

---

### 4. slalib_src/ - Astronomical Library (35 files)

**Purpose:** Standard Low-Level Astronomy Library (SLA)

```
ephem/
  ├─ planet.c: Planetary ephemerides
  ├─ refco.c: Atmospheric refraction corrections
  └─ geod.c: Geodetic transformations

coords/
  ├─ eqecl.c: Equatorial ↔ Ecliptic
  ├─ prec.c: Precession transformations
  ├─ fk4_fk5.c: Catalog epoch conversions
  └─ hms.c: Hour-minute-second parsing

math/
  ├─ dvn.c: Vector normalization
  ├─ dmat.c: Matrix operations
  └─ euler.c: Euler angle transformations
```

---

### 5. libtecla_src/ - Terminal Editor (20 files)

**Purpose:** Interactive command-line editing (like GNU Readline but more portable)

Features:
- Command history (up/down arrows)
- Tab completion
- Vi/Emacs editing modes
- Parenthesis matching

Not critical for wrapper (can be disabled in interactive mode).

---

### 6. Supporting Libraries

**logio_src/**: Logging and I/O utilities
- `logio.c`: Output buffering
- `page.c`: Pagination

**pager_src/**: Text paging (for viewing large outputs)
- `pager.c`: Terminal paging

**recio_src/**: Record I/O
- `recio.c`: Fixed-record reading

**scrfil_src/**: Scratch file management
- `scrfil.c`: Temporary file handling

**sphere_src/**: (Covered above)

**cpg_src/**: PGPLOT C wrapper
- `cpgplot.h`: C-language bindings for Fortran PGPLOT library

---

## KEY DATA STRUCTURES

### Global Singleton Pattern

DIFMAP uses extensive static globals instead of passing contexts:

```c
// In different .c files, marked static

static Observation *ob = NULL;   // Current observation
static Model *model = NULL;      // Current model
static Mapcln *mc = NULL;        // Current CLEAN state

// Callbacks to modify them:
void read_uv(char *filename) {
    // Load into global ob
    ob = load_obs_from_fits(filename);
}

void add_component(float flux, ...) {
    // Add to global model
    if (model == NULL) model = create_model();
    model->components[model->ncmp++] = ...;
}
```

**Problem:** This makes the C library inherently non-reentrant.
**Solution:** Use subprocess isolation (process = separate globals).

### Observation Structure

```c
typedef struct {
    Source *source;        // Target source info
    Station *tel;          // Array of telescopes
    int ntel;             // Number of telescopes
    
    UVData *data;         // Visibility data
    int nbas;             // Number of baselines
    
    float freqoff;        // Frequency offset
    double mjd;           // Modified Julian Date
    char project[32];     // Project code
    
    // ... 30+ more fields
} Observation;
```

### Model Component

```c
typedef struct {
    float flux;           // Jy
    float x, y;           // arcseconds (RA, Dec offset from phase center)
    
    // For Gaussians/extended models:
    float major;          // FWHM major axis (arcsec)
    float ratio;          // Minor/major axial ratio
    float phi;            // Position angle (degrees)
    
    // For fitting:
    int freepar;          // Bitmap: which params are free to fit?
    float dflux, dx, dy;  // Uncertainties after fitting
    float dmajor, dratio, dphi;
    
    Modtyp type;          // POINT, GAUS, DISK, RING, etc.
} Modcmp;
```

### CLEAN State

```c
typedef struct {
    float *map;           // 2D image array (nx × ny floats)
    float *residuals;     // Residual map
    int nx, ny;           // Pixel dimensions
    
    float bmaj, bmin;     // Beam major/minor (arcsec)
    float bpa;            // Beam position angle (degrees)
    
    int n_clean_iter;     // Iterations done
    float gain;           // Loop gain (0-1)
    float threshold;      // Stopping threshold (Jy/beam)
    
    // List of CLEAN components found:
    struct {
        float flux;
        int ix, iy;       // Pixel location
    } *clean_comps;
    int n_comps;
} Mapcln;
```

---

## CRITICAL INTERFACES

### To DIFMAP from SPHERE:

These are the main "entry points" you'll use in SPHERE scripts:

```sphere
# Data Loading
read_uv "filename.fits"     # Load UV FITS
write_uv "filename.fits"    # Save UV FITS

# Modeling
model                       # Initialize model
add flux x y type major ratio pa   # Add component
delete_component index      # Remove component
modelpars                   # Print current model

# Fitting
fit                         # Levenberg-Marquardt fit
selfcal interval           # Self-calibration

# Cleaning
clean niter gain threshold method   # CLEAN deconvolution

# Output
wmap "filename.fits"        # Write image FITS

# Inspection
observ                      # Print observation info
uvstat                      # UV statistics
mapstat                     # Map statistics

# Plotting (uses PGPLOT → image files)
uvplot                      # Draw UV coverage
modplot                     # Draw model components
mapplot                     # Draw CLEAN map
```

---

## SPHERE MACRO LANGUAGE

### Why SPHERE?

**Alternative:** Wrap every C function individually
- Result: 500+ functions to wrap
- Maintenance: Nightmare (API breakage in DIFMAP update)

**Better:** Use SPHERE (already there!)
- SPHERE already orchestrates algorithms intelligently
- Python just generates SPHERE scripts dynamically
- Changes to C internals don't affect Python

### SPHERE Basics

```sphere
# Comments
# This is a comment

# Variables
set myvar 3.14
set name "test"

# String concatenation
set path "results/" & name & ".fits"

# Arithmetic
set result = (10 + 5) * 2 - 3 / 0.5

# Arrays
array data[1000]
set data[5] = 3.14

# Control flow
for i=1 to 10
  print "Iteration " & i
  if i > 5
    print "  More than 5!"
  else
    print "  Still building up"
  endif
end

# While loops
set x = 1
while x < 100
  set x = x * 2
end

# Function calls
read_uv "data.fits"
observ              # Print observation

# Model creation
model               # Initialize
add 1.0 0 0 point   # flux x y type
add 0.5 0.001 0 gaussian 0.001 0.8 45
fit                 # Fit model

# Cleaning
clean 1000 0.1      # niter gain

# Save
wmap "output.fits"

# Exit
exit
```

---

## PROBLEM POINTS & SOLUTIONS

### Problem #1: Static Globals (Memory Safety)

**Issue:** Globals prevent multiple simultaneous sessions
```c
static Observation *ob = NULL;  // Only one!
static Model *model = NULL;     // Only one!
```

**Solution:** Subprocess isolation (one process = one set of globals)

---

### Problem #2: PGPLOT Dependency (Display)

**Issue:** PGPLOT requires X11 graphics on servers

**Solution:** Use headless modes
- PDF device: `/pdf` (PostScript → PDF)
- PS device: `/ps` (PostScript file)
- No display needed

**From Python:** Use matplotlib for visualization (not PGPLOT)

---

### Problem #3: FITS Files (I/O Synchronization)

**Issue:** How does Python know when DIFMAP is done?

**Solution:** File-based IPC
```python
# 1. Send commands
proc.stdin.write("read_uv data.fits\nfit\nexit\n")

# 2. Wait for completion
stdout, stderr = proc.communicate()

# 3. Read FITS results
from astropy.io import fits
hdul = fits.open('output.fits')
```

---

### Problem #4: Version Compatibility

**Issue:** DIFMAP may change between releases

**Solution:** SPHERE API is stable (20+ years)
- Python just generates SPHERE scripts
- Updates to C internals transparent
- Backwards compatibility guaranteed

---

## REFERENCE TABLES

### DIFMAP Component Types

| Type | Syntax | Parameters | Use Case |
|------|--------|------------|----------|
| **Point** | `add flux x y point` | flux, x, y | Unresolved sources |
| **Gaussian** | `add flux x y gaussian major ratio pa` | major, ratio, pa | Resolved sources |  
| **Disk** | `add flux x y disk radius` | radius | Uniform disk |
| **Ring** | `add flux x y ring radius` | radius | Elliptical ring |
| **Rectangle** | `add flux x y rect major ratio pa` | (see Gaussian) | Rectangular |

**Parameters:**
- `flux`: Jy (emission or absorption)
- `x, y`: arcsecond offsets from phase center
- `major`: FWHM major axis (arcsec)
- `ratio`: Minor/major axial ratio (0-1)
- `pa`: Position angle (degrees, East from North)

### CLEAN Parameters

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `niter` | 1000 | 1-∞ | Max iterations |
| `gain` | 0.1 | 0-1 | Loop gain (fraction of peak removed per iteration) |
| `threshold` | auto | Jy/beam | Stop when peak residual < threshold |
| `method` | "normal" | "normal", "sdiff" | Algorithm variant |

### Self-Calibration Parameters

| Parameter | Meaning |
|-----------|---------|
| `solution_interval` | Time interval for gain solutions (seconds) |
| Algorithm | Solves for complex gain per station per interval |

### FITS Keywords (UV Data)

| Keyword | Type | Meaning |
|---------|------|---------|
| `OBJECT` | char | Source name |
| `CRVAL1, CRVAL2` | float | RA, Dec (degrees) |
| `CRPIX1, CRPIX2` | float | Reference pixel |
| `CDELT1, CDELT2` | float | Pixel scale (degrees) |
| `DATE-OBS` | char | Observation date (ISO) |
| `TELESCOP` | char | Array name |
| `INSTRUME` | char | Instrument/project |

---

## NEXT STEPS

For implementation details, see [GUIDE_IMPLEMENTATION.md](GUIDE_IMPLEMENTATION.md).

For specific Python wrapper code, see [GUIDE_IMPLEMENTATION.md](GUIDE_IMPLEMENTATION.md) section "Code Complete: DifmapSession".

---

*Last Updated: 4 March 2026*
