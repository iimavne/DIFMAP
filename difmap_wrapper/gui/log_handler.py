# difmap_wrapper/gui/log_handler.py
"""
Handler de logging Python qui émet un signal PyQt6.

Architecture :
    Éditeur Matplotlib  → logger.info(msg) ou logger.info(msg, extra={'difmap_level': 'success'})
    DifmapLogHandler    → pyqtSignal(str, str) émis dans le thread courant
    ImprovedLogConsole  → _dispatch(level, msg) → _append_styled()

Le signal Qt garantit la thread-safety si les éditeurs tournent hors du
thread Qt principal. Niveaux personnalisés (success, inspect, stats) sont
passés via extra={'difmap_level': '...'} — les niveaux Python standard
(INFO, WARNING, ERROR) sont mappés automatiquement.
"""
import logging
from PyQt6.QtCore import QObject, pyqtSignal


class _LogSignalEmitter(QObject):
    """QObject minimal portant le signal (séparé du Handler pour éviter le double héritage)."""
    log_emitted = pyqtSignal(str, str)   # (level, message)


class DifmapLogHandler(logging.Handler):
    """
    Intercepte les logs du namespace 'difmap' et les route vers ImprovedLogConsole.

    Niveaux supportés
    -----------------
    Standard Python → mapping automatique :
        logging.DEBUG    → 'debug'
        logging.INFO     → 'info'
        logging.WARNING  → 'warning'
        logging.ERROR / CRITICAL → 'error'

    Niveaux personnalisés via extra dict (prioritaires sur le mapping standard) :
        logger.info(msg, extra={'difmap_level': 'success'})
        logger.info(msg, extra={'difmap_level': 'inspect'})
        logger.info(msg, extra={'difmap_level': 'stats'})

    Utilisation
    -----------
    >>> handler = DifmapLogHandler()
    >>> logging.getLogger('difmap').addHandler(handler)
    >>> console.connect_handler(handler)          # ImprovedLogConsole
    """

    _LEVEL_MAP = {
        logging.DEBUG:    'debug',
        logging.INFO:     'info',
        logging.WARNING:  'warning',
        logging.ERROR:    'error',
        logging.CRITICAL: 'error',
    }

    def __init__(self):
        """Initialise le handler et crée le ``QObject`` porteur du signal PyQt6."""
        super().__init__()
        self._emitter = _LogSignalEmitter()
        self.log_emitted = self._emitter.log_emitted
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        """
        Formate et émet le log vers la console Qt via le signal PyQt6.

        Priorité au champ ``difmap_level`` de ``record.extra`` ; sinon mappe
        le niveau Python standard (DEBUG/INFO/WARNING/ERROR) via ``_LEVEL_MAP``.

        Parameters
        ----------
        record : logging.LogRecord
            Enregistrement de log Python à traiter.
        """
        try:
            # Priorité au niveau difmap personnalisé (success, inspect, stats…)
            level = getattr(record, 'difmap_level', None)
            if level is None:
                level = self._LEVEL_MAP.get(record.levelno, 'info')
            msg = self.format(record)
            self._emitter.log_emitted.emit(level, msg)
        except Exception:
            self.handleError(record)
