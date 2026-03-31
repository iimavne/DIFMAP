################################################################################
# Configuration du projet Meson - DIFMAP 2.5q_mod
################################################################################

project('difmap_smartedit', ['c', 'fortran'],
  version : '2.5q_mod',
  default_options : ['warning_level=1', 'c_std=gnu99'])

cc = meson.get_compiler('c')
fc = meson.get_compiler('fortran')

################################################################################
# SECTION 1: CONFIGURATION DES DRAPEAUX DE COMPILATION (FLAGS)
################################################################################

add_project_arguments(
  '-Dlinux_i486_gcc',
  '-fPIC',
  '-D_DEFAULT_SOURCE',
  '-DUSE_TECLA',
  '-DHAVE_CURSES_H',
  '-DHAVE_TERM_H',
  '-DHAVE_SELECT',
  '-DHAVE_SYS_SELECT_H',
  '-D_XOPEN_SOURCE=600',
  language : 'c'
)

add_project_arguments('-O0', '-g', language : 'fortran')

################################################################################
# SECTION 2: DÉPENDANCES SYSTÈME EXTERNES
################################################################################

m_dep = cc.find_library('m', required : true)
gsl_dep = dependency('gsl', required : true)
x11_dep = dependency('x11', required : true)
curses_dep = dependency('ncurses', required : true)
tinfo_dep = cc.find_library('tinfo', required : true) 
pgplot_dep = cc.find_library('pgplot', required : true)
cpgplot_dep = cc.find_library('cpgplot', required : true)
py3 = import('python').find_installation()
py3_dep = py3.dependency()
cython = find_program('cython')
numpy_inc_dir = run_command(py3, '-c', 'import numpy; print(numpy.get_include())', check : true).stdout().strip()

################################################################################
# SECTION 3: CONFIGURATION DES RÉPERTOIRES D'INCLUSION (INCLUDE PATHS)
################################################################################

inc = include_directories(
  'logio_src', 'pager_src', 'recio_src', 'scrfil_src',
  'fits_src', 'slalib_src', 'sphere_src', 'difmap_src', 'libtecla_src'
)

conf_data = configuration_data()
conf_data.set('HELP_DIR', '"' + join_paths(meson.project_source_root(), 'help') + '/"')
configure_file(output : 'helpdir.h', configuration : conf_data)

inc_build = include_directories('.')

libfits_h = custom_target('libfits.h', output : 'libfits.h',
  input : ['fits_src/fits.h', 'fits_src/thdu.h', 'fits_src/phdu.h', 'fits_src/fitkey.h'],
  command : ['cat', '@INPUT@'], 
  capture : true)

################################################################################
# SECTION 4: CONSTRUCTION DES BIBLIOTHÈQUES STATIQUES INTERNES (.a)
################################################################################

liblogio = static_library('logio', 
  ['logio_src/logio.c', 'logio_src/print.c'], 
  include_directories : inc)

libpager = static_library('pager', 
  ['pager_src/pager.c'],
  include_directories : inc)

librecio = static_library('recio', 
  ['recio_src/recio.c'],
  include_directories : inc)

libscrfil = static_library('scrfil', 
  ['scrfil_src/scrfile.c', 'scrfil_src/exist.c', 'scrfil_src/edfile.c'],
  include_directories : inc)

libslalib = static_library('slalib', 
  ['slalib_src/dcc2s.c', 'slalib_src/preces.c', 'slalib_src/nut.c', 'slalib_src/dmxv.c', 
   'slalib_src/dvdv.c', 'slalib_src/epj.c', 'slalib_src/prebn.c', 'slalib_src/eqeqx.c', 
   'slalib_src/dt.c', 'slalib_src/planet.c', 'slalib_src/dranrm.c', 'slalib_src/prenut.c', 
   'slalib_src/dmxm.c', 'slalib_src/geoc.c', 'slalib_src/dmoon.c', 'slalib_src/dat.c', 
   'slalib_src/djcl.c', 'slalib_src/gmst.c', 'slalib_src/map.c', 'slalib_src/deuler.c', 
   'slalib_src/dvn.c', 'slalib_src/fk45z.c', 'slalib_src/prec.c', 'slalib_src/dcs2c.c', 
   'slalib_src/cldj.c', 'slalib_src/nutc.c', 'slalib_src/epb2d.c', 'slalib_src/mappa.c', 
   'slalib_src/evp.c', 'slalib_src/mapqk.c'],
  include_directories : inc)

libsphere = static_library('sphere', 
  ['sphere_src/lex.c', 'sphere_src/func.c', 'sphere_src/table.c', 'sphere_src/closedown.c', 
   'sphere_src/mathlib.c', 'sphere_src/iolib.c', 'sphere_src/run.c', 'sphere_src/compile.c', 
   'sphere_src/matrix_blocks.c', 'sphere_src/plotlib.c', 'sphere_src/four.c', 'sphere_src/sig.c', 
   'sphere_src/help.c', 'sphere_src/rand.c', 'sphere_src/hart.c', 'sphere_src/sphere.c', 
   'sphere_src/ops.c', 'sphere_src/userio.c', 'sphere_src/match.c', 'sphere_src/utils.c'], 
  include_directories : inc)

libfits = static_library('fits', 
  ['fits_src/fits.c', 'fits_src/sysfits.c', 'fits_src/hdu.c', 'fits_src/ahdu.c', 
   'fits_src/bhdu.c', 'fits_src/phdu.c', 'fits_src/thdu.c', 'fits_src/uhdu.c', 
   'fits_src/fitkey.c', 'fits_src/conv.c', libfits_h], 
  include_directories : [inc, inc_build])

libtecla = static_library('tecla', 
  ['libtecla_src/getline.c', 'libtecla_src/keytab.c', 'libtecla_src/direader.c', 
   'libtecla_src/history.c', 'libtecla_src/stringrp.c', 'libtecla_src/freelist.c', 
   'libtecla_src/cplfile.c', 'libtecla_src/cplmatch.c', 'libtecla_src/pcache.c', 
   'libtecla_src/version.c', 'libtecla_src/ioutil.c', 'libtecla_src/homedir.c', 
   'libtecla_src/strngmem.c', 'libtecla_src/chrqueue.c', 'libtecla_src/errmsg.c', 
   'libtecla_src/expand.c', 'libtecla_src/pathutil.c', 'libtecla_src/hash.c'], 
  include_directories : inc, 
  dependencies : [curses_dep, tinfo_dep]
)

################################################################################
# SECTION 5: EXÉCUTABLE PRINCIPAL - DIFMAP
################################################################################

difmap_sources = [
  'difmap_src/uvf_read.c', 'difmap_src/uvf_write.c', 'difmap_src/obs.c', 'difmap_src/subarray.c',
  'difmap_src/obutil.c', 'difmap_src/binan.c', 'difmap_src/dpage.c', 'difmap_src/if.c',
  'difmap_src/ifpage.c', 'difmap_src/intrec.c', 'difmap_src/obedit.c', 'difmap_src/obhead.c',
  'difmap_src/uvpage.c', 'difmap_src/chlist.c', 'difmap_src/obpol.c', 'difmap_src/chlist.h',
  'difmap_src/telcor.c', 'difmap_src/visaver.c', 'difmap_src/utbin.c', 'difmap_src/intlist.c',
  'difmap_src/intlist.h', 'difmap_src/obshift.c', 'difmap_src/resoff.c', 'difmap_src/winmod.c',
  'difmap_src/subamphs.c', 'difmap_src/addamphs.c', 'difmap_src/nextif.c', 'difmap_src/wtscal.c',
  'difmap_src/units.c', 'difmap_src/scans.c', 'difmap_src/mapwin.c', 'difmap_src/stokes.c',
  'difmap_src/visstat.c', 'difmap_src/pb.c', 'difmap_src/mapcor.c', 'difmap_src/model.c',
  'difmap_src/modvis.c', 'difmap_src/besj.c', 'difmap_src/addmod.c', 'difmap_src/modfit.c',
  'difmap_src/modeltab.c', 'difmap_src/hms.c', 'difmap_src/termstr.c', 'difmap_src/visflags.c',
  'difmap_src/telspec.c', 'difmap_src/ellips.c', 'difmap_src/uvrange.c', 'difmap_src/baselist.c',
  'difmap_src/spectra.c', 'difmap_src/pollist.c', 'difmap_src/freelist.c', 'difmap_src/planet.c',
  'difmap_src/cksum.c', 'difmap_src/fnint.c', 'difmap_src/dnint.c', 'difmap_src/frange.c',
  'difmap_src/imran.c', 'difmap_src/minmax.c', 'difmap_src/lmfit.c', 'difmap_src/matinv.c',
  'difmap_src/newfft.c', 'difmap_src/startup.c', 'difmap_src/f77main.f', 'difmap_src/difmap.c',
  'difmap_src/slfcal.c', 'difmap_src/wmapbeam.c', 'difmap_src/maplot.c', 'difmap_src/moddif.c',
  'difmap_src/vlbhead.c', 'difmap_src/uvaver.c', 'difmap_src/mapmem.c', 'difmap_src/mapclean.c',
  'difmap_src/mapres.c', 'difmap_src/costran.c', 'difmap_src/uvinvert.c', 'difmap_src/clphs.c',
  'difmap_src/clplot.c', 'difmap_src/vlbhist.c', 'difmap_src/enumpar.c', 'difmap_src/symtab.c',
  'difmap_src/plbeam.c', 'difmap_src/uvrotate.c', 'difmap_src/stnstr.c', 'difmap_src/uvtrans.c',
  'difmap_src/corplt.c', 'difmap_src/modplot.c', 'difmap_src/uvradplt.c', 'difmap_src/vedit.c',
  'difmap_src/vplot.c', 'difmap_src/color.c', 'difmap_src/uvplot.c', 'difmap_src/timplt.c',
  'difmap_src/specplot.c', 'difmap_src/markerlist.c', 'difmap_src/mc.c', libfits_h
]

# ==============================================================================
# 1. INSTALLATION DU WRAPPER PYTHON (Couche de haut niveau)
# ==============================================================================
# Copie les fichiers purement Python du module orienté objet vers le 
# répertoire d'installation (site-packages). Cela permet à l'utilisateur 
# de faire `import difmap_wrapper` proprement.
py3.install_sources(
    'difmap_wrapper/__init__.py',
    'difmap_wrapper/session.py',
    'difmap_wrapper/imaging.py',
    'difmap_wrapper/exceptions.py',
    'difmap_wrapper/observation.py',
    subdir: 'difmap_wrapper'
)

# ==============================================================================
# 2. PIPELINE DE TRANSPILATION CYTHON -> C
# ==============================================================================
# Définition d'un générateur Meson personnalisé pour invoquer le compilateur Cython.
# Il dicte comment transformer n'importe quel fichier source '.pyx' en fichier '.c'.
cython_gen = generator(cython,
  output : '@BASENAME@.c',
  # Ajout du flag '-3' pour forcer le mode Python 3 et supprimer le warning
  arguments : ['-3', '@INPUT@', '--output-file', '@OUTPUT@', '--fast-fail'])
  
# Application du générateur sur notre fichier de binding principal.
# Produit le fichier intermédiaire C qui contiendra l'API CPython.
binding_c = cython_gen.process('binding/difmap_native.pyx')

# ==============================================================================
# 3. COMPILATION DE L'EXTENSION NATIVE PYTHON (.so)
# ==============================================================================
# Assemble le code C généré par Cython avec les sources historiques de Difmap
# pour créer la bibliothèque partagée importable depuis Python (difmap_native.so).
py3.extension_module('difmap_native',
  [binding_c] + difmap_sources,               # Fichier C généré + Sources du moteur Difmap
  include_directories : [inc, inc_build],
  c_args : ['-I' + numpy_inc_dir],            # Inclusion des headers NumPy pour le Zero-Copy (Memoryviews)
  
  # Édition de liens (Linkage) avec les bibliothèques statiques internes de Difmap
  link_with : [
    libsphere, liblogio, libpager, libfits, 
    librecio, libslalib, libscrfil
  ],
  link_whole : [libtecla],
  
  # Édition de liens avec les dépendances système externes (X11, PGPLOT) et l'API Python
  dependencies : [
    m_dep, gsl_dep, pgplot_dep, cpgplot_dep, 
    x11_dep, curses_dep, tinfo_dep, py3_dep
  ],
  install : true
)

# ==============================================================================
# 4. COMPILATION DE L'EXÉCUTABLE STANDALONE (Héritage)
# ==============================================================================
# Maintient la compilation du programme autonome original (CLI).
# Garantit que l'outil classique reste disponible pour les tests de régression, 
# la validation scientifique croisée ou l'usage historique, sans impacter le module Python.
executable('difmap',
  difmap_sources,
  include_directories : [inc, inc_build],
  link_with : [
    libsphere, liblogio, libpager, libfits, 
    librecio, libslalib, libscrfil
  ],
  link_whole : [libtecla],
  dependencies : [
    m_dep, gsl_dep, pgplot_dep, cpgplot_dep, 
    x11_dep, curses_dep, tinfo_dep
  ],
  install : true
)