# difmap_wrapper/observation.py
import logging
import re
import numpy as np
import difmap_native

from .exceptions import DifmapStateError, DifmapError

logger = logging.getLogger("difmap.observation")


class Observation:
    """
    Accès aux données UV chargées : sélection, flagging et extraction.

    Accessible via ``session.obs``. Centralise l'état du masque de flagging
    et propose les opérations courantes sur les visibilités.

    Attributes
    ----------
    masque_flagges : np.ndarray of bool or None
        Tableau de la taille du nombre de visibilités. ``True`` = point exclu.
        Initialisé automatiquement au premier appel à ``get_data()`` ou ``select()``.

    Examples
    --------
    >>> session.obs.select(pol="RR")
    >>> data = session.obs.get_data()
    >>> print(data["amp"].shape)
    (11560,)
    """

    def __init__(self, session):
        self._session = session
        self._native = difmap_native

        # C3 : Propriété des données de flagging — centralisée ici
        self.masque_flagges: np.ndarray | None = None
        self.historique_coupes: list = []

        # Observer pattern : liste des éditeurs Matplotlib enregistrés
        self._editors: list = []

    # =========================================================
    # Observer pattern
    # =========================================================

    def register_editor(self, editor) -> None:
        """Enregistre un éditeur Matplotlib comme observateur de ces données."""
        if editor not in self._editors:
            self._editors.append(editor)

    def unregister_editor(self, editor) -> None:
        """Retire l'éditeur de la liste (appelé par cleanup())."""
        self._editors = [e for e in self._editors if e is not editor]

    def notify_data_changed(self) -> None:
        """
        Notifie tous les éditeurs enregistrés que les données C ont changé.

        Appeler après toute calibration ou modification des données côté C
        (ex : après un self-cal, un apply_gains, etc.) pour que les graphiques
        ouverts se mettent à jour automatiquement.
        """
        for editor in list(self._editors):
            try:
                editor.refresh_data()
            except Exception:
                logger.exception("Erreur lors du rafraîchissement de %s", editor)

    # =========================================================
    # C3 / M6 : API données
    # =========================================================

    def reset_flags(self, n_visibilities: int) -> None:
        """
        Remet tous les flags à zéro (aucune visibilité exclue).

        Appelé automatiquement par ``get_data()`` et ``select()``
        quand le nombre de visibilités change. Peut aussi être appelé
        manuellement pour annuler l'ensemble des flags.

        Parameters
        ----------
        n_visibilities : int
            Nombre total de visibilités dans le jeu de données courant.
        """
        self.masque_flagges = np.zeros(n_visibilities, dtype=bool)
        self.historique_coupes = []

    def get_data(self) -> dict:
        """
        Retourne toutes les visibilités de la sélection active.

        Chaque clé du dictionnaire est un tableau NumPy de même longueur
        (nombre de visibilités). Appeler ``select()`` avant ``get_data()``
        pour choisir la polarisation et les IFs.

        Returns
        -------
        dict
            ``'u'``, ``'v'`` : coordonnées UV en longueurs d'onde (float32).

            ``'amp'`` : amplitude en Jansky (float32).

            ``'phase'`` : phase en degrés, wrappée dans [-180, 180] (float32).

            ``'modamp'``, ``'modphs'`` : amplitude et phase du modèle courant.

            ``'weight'`` : poids statistique de chaque visibilité. Valeur
            négative ou nulle = visibilité flaguée.

            ``'tel_a'``, ``'tel_b'`` : indices des antennes formant la baseline.

            ``'subarray'`` : indice du sous-réseau (0-based).

            ``'if_no'`` : indice de la fréquence IF.

            ``'time'`` : temps UTC en jours juliens.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée (appeler ``session.observe()`` d'abord).

        Examples
        --------
        >>> session.obs.select(pol="RR")
        >>> data = session.obs.get_data()
        >>> import numpy as np
        >>> good = data["weight"] > 0
        >>> print(f"{good.sum()} visibilités valides sur {len(good)}")
        11200 visibilités valides sur 11560
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        data = self._native.get_uv_data()
        n = len(data.get('u', []))
        if self.masque_flagges is None or len(self.masque_flagges) != n:
            self.reset_flags(n)
        return data

    # =========================================================
    # API existante 
    # =========================================================

    @property
    def source(self) -> str:
        """Nom de la source astronomique active. Retourne ``'Inconnue'`` si rien n'est chargé."""
        if not self._session.uv_loaded:
            return "Inconnue"
        return self._native.get_source()

    def get_polarization(self) -> str:
        """Retourne la polarisation active (ex: ``'RR'``, ``'LL'``). Retourne ``'Unknown'`` si rien n'est chargé."""
        return self._native.get_polarization()

    def nsub(self) -> int:
        """
        Retourne le nombre de sous-réseaux (subarrays) dans l'observation.

        Un sous-réseau correspond à un groupe d'antennes qui observent ensemble.
        La plupart des observations n'en ont qu'un seul.

        Returns
        -------
        int
            Nombre de sous-réseaux.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si le moteur C rencontre une erreur interne.

        Examples
        --------
        >>> print(session.obs.nsub())
        1
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        res = self._native.nsub()
        if res < 0:
            raise DifmapError("Erreur lors de la lecture des sous-réseaux.")
        logger.info("Nombre de sous-réseaux (Subarrays) : %d", res)
        return res

    def select(self, pol: str = "I", ifs: tuple = (1, 0), channels: tuple = (1, 0)) -> str:
        """
        Sélectionne la polarisation, les IFs et les canaux à analyser.

        Cette commande doit être appelée après ``session.observe()`` et avant
        tout accès aux données. Elle remet à zéro le masque de flagging.

        Parameters
        ----------
        pol : str, optional
            Polarisation souhaitée : ``"I"``, ``"RR"``, ``"LL"``, ``"Q"``, etc.
            Si la polarisation demandée n'existe pas dans le fichier, le moteur
            bascule sur la plus proche disponible. Par défaut ``"I"``.
        ifs : tuple of int, optional
            ``(premier_if, dernier_if)``. ``0`` signifie "jusqu'au dernier".
            Par défaut ``(1, 0)`` = tous les IFs.
        channels : tuple of int, optional
            ``(premier_canal, dernier_canal)``. Par défaut ``(1, 0)`` = tous.

        Returns
        -------
        str
            La polarisation réellement sélectionnée par le moteur C
            (peut différer de ``pol`` si elle n'était pas disponible).

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si la sélection échoue côté moteur C.

        Examples
        --------
        >>> session.obs.select(pol="RR")
        'RR'
        >>> session.obs.select(pol="I", ifs=(1, 2))
        'I'
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        
        pol = pol.upper()
        if self._native.select(pol, ifs[0], ifs[1], channels[0], channels[1]) != 0:
            raise DifmapError(f"Échec de la sélection (Pol: {pol})")
            
        # Réinitialisation du masque (comme on l'a corrigé tout à l'heure)
        self.masque_flagges = None
        self.historique_coupes.clear()

        # On demande au C sur quelle polarisation il est vraiment ---
        try:
            pol_reelle = self._native.get_polarization() 
        except AttributeError:
            # Sécurité au cas où la fonction C n'est pas encore implémentée
            pol_reelle = pol 
            
        # Si le moteur a forcé une autre polarisation, on le loggue
        if pol_reelle != pol:
            logger.warning(
                f"Polarisation {pol} indisponible. Le moteur a basculé sur {pol_reelle}.",
                extra={'difmap_level': 'warning'}
            )
            
        return pol_reelle # On retourne la vraie valeur à l'interface

    def set_if_range(self, if_beg: int, if_end: int) -> None:
        """
        Restreint l'extraction UV à la plage d'IFs ``[if_beg, if_end]``
        **sans** relire le fichier scratch (pas de ``ob_select``).

        À utiliser quand seul le filtre IF change — beaucoup plus rapide que
        ``select()``. Appeler ``get_data()`` ensuite pour obtenir les données
        filtrées.

        Parameters
        ----------
        if_beg : int
            Premier IF souhaité (1-indexed). ``1`` = début.
        if_end : int
            Dernier IF souhaité (1-indexed). ``0`` = jusqu'au dernier.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si l'appel C échoue.
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        if self._native.set_if_range(if_beg, if_end) != 0:
            raise DifmapError(f"Échec de set_if_range({if_beg}, {if_end})")
        self.masque_flagges = None
        self.historique_coupes.clear()

    @property
    def nif(self) -> int:
        """Nombre total d'IFs dans l'observation courante (0 si rien de chargé)."""
        if not self._session.uv_loaded:
            return 0
        return self._native.get_nif()

    def header(self) -> str:
        """
        Retourne le header complet de l'observation sous forme de texte.

        Équivalent de la commande interactive ``header`` de difmap.
        Inclut : mots-clés FITS, sous-réseaux, table des IFs, source,
        polarisations disponibles, dimensions et paramètres temporels.

        Returns
        -------
        str
            Texte formaté du header, prêt à afficher ou à logger.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.

        Examples
        --------
        >>> print(session.obs.header())
        UV FITS miscellaneous header keyword values:
          OBSERVER = "..."
          ...
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        return self._native.get_header_text()

    def available_polarizations(self) -> list[str]:
        """
        Retourne les polarisations disponibles pour l'observation courante.

        La liste est extraite du header texte généré par le moteur Difmap,
        par exemple ``"RR"``, ``"RR LL"`` ou ``"RR, LL, RL, LR"``.
        """
        if not self._session.uv_loaded:
            return []

        match = re.search(r"^\s*Polarizations\s*:\s*(.+?)\s*$", self.header(), re.MULTILINE)
        if not match:
            return []

        tokens = [tok.strip().upper() for tok in re.split(r"[\s,]+", match.group(1)) if tok.strip()]
        seen = set()
        values = []
        for tok in tokens:
            if tok not in seen:
                seen.add(tok)
                values.append(tok)
        return values

    def flag_data(self, indices) -> int:
        """
        Marque les visibilités aux indices donnés comme exclues (flaguées).

        Le masque ``masque_flagges`` n'est **pas** mis à jour ici — c'est la
        responsabilité de l'éditeur graphique qui appelle cette méthode.
        Utilisez l'interface graphique ou ``BasePlotEditor._flag_indices()``
        pour une mise à jour cohérente.

        Parameters
        ----------
        indices : array-like of int
            Indices (0-based) des visibilités à flaguer.

        Returns
        -------
        int
            Nombre de visibilités effectivement flaguées.

        Examples
        --------
        >>> session.obs.flag_data([0, 5, 12])
        3
        """
        indices_c = np.asarray(indices, dtype=np.int32)
        if len(indices_c) > 0:
            return self._native.flag_data(indices_c)
        return 0

    def unflag_data(self, indices) -> int:
        """
        Restaure les visibilités précédemment flaguées.

        Parameters
        ----------
        indices : array-like of int
            Indices (0-based) des visibilités à restaurer.

        Returns
        -------
        int
            Nombre de visibilités restaurées.
        """
        indices_c = np.asarray(indices, dtype=np.int32)
        if len(indices_c) > 0:
            return self._native.unflag_data(indices_c)
        return 0

    def save_wobs(self, filepath: str) -> bool:
        """
        Sauvegarde les données avec les flags actuels dans un nouveau fichier FITS.

        Si l'extension ``'.fits'`` est absente du nom, elle est ajoutée automatiquement.

        Parameters
        ----------
        filepath : str
            Chemin de destination. Exemple : ``"sortie_editee.fits"``.

        Returns
        -------
        bool
            ``True`` si la sauvegarde a réussi.

        Examples
        --------
        >>> session.obs.save_wobs("data/source_flagged.fits")
        True
        """
        if not filepath.endswith('.fits'):
            filepath += '.fits'
        logger.info("Sauvegarde en cours via Difmap vers : %s", filepath)
        self._native.save_wobs(filepath)
        return True
