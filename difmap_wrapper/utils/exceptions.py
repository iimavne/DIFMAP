# difmap_wrapper/exceptions.py

class DifmapError(Exception):
    """
    Exception de base pour toutes les erreurs du moteur C de Difmap.

    Levée quand le code natif (C/Cython) échoue : allocation mémoire,
    FFT invalide, fichier FITS corrompu, argument hors plage. Toutes
    les exceptions du paquet en héritent — un seul ``except DifmapError``
    suffit pour tout intercepter.

    Examples
    --------
    >>> from difmap_wrapper import DifmapSession
    >>> from difmap_wrapper.exceptions import DifmapError
    >>> with DifmapSession() as session:
    ...     try:
    ...         session.observe("fichier_inexistant.fits")
    ...     except DifmapError as e:
    ...         print(f"Erreur moteur : {e}")
    """
    pass


class DifmapStateError(DifmapError):
    """
    Levée quand une opération est appelée dans le mauvais ordre.

    Le moteur C est un automate d'état strict. Cette exception bloque
    les appels illogiques côté Python avant qu'ils n'atteignent le C
    et causent un segfault. Elle hérite de ``DifmapError``.

    Cas typiques :
    - ``invert()`` appelé avant ``mapsize()``
    - ``get_map()`` appelé avant ``invert()``
    - ``select()`` appelé avant ``observe()``
    - Tentative de créer une deuxième ``DifmapSession`` dans le même processus

    Examples
    --------
    >>> from difmap_wrapper import DifmapSession
    >>> from difmap_wrapper.exceptions import DifmapStateError
    >>> with DifmapSession() as session:
    ...     try:
    ...         session.imager.invert()   # observe() non appelé → DifmapStateError
    ...     except DifmapStateError as e:
    ...         print(f"Ordre incorrect : {e}")
    """
    pass
