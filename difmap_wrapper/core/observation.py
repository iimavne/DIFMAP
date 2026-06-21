# difmap_wrapper/observation.py
import logging
import re
import numpy as np
import difmap_native

from ..utils.exceptions import DifmapStateError, DifmapError
from ..enums import Polarization

logger = logging.getLogger("difmap.observation")


class Observation:
    """
    Accès aux données UV chargées : sélection, flagging et extraction.

    Accessible via ``session.obs``. Centralise l'état du masque de flagging
    et propose les opérations courantes sur les visibilités.

    Attributes
    ----------
    flag_mask : np.ndarray of bool or None
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
        self.flag_mask: np.ndarray | None = None
        self.undo_history: list = []
        self.reflag_history: list = []

        # Cache get_data() : évite de réappeler l_extract_uv() si rien n'a changé
        self._cached_raw_data: dict | None = None
        self._data_dirty: bool = True

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


    def invalidate_cache(self) -> None:
        """Force un réextraction UV au prochain appel à get_data()."""
        self._data_dirty = True
        self._cached_raw_data = None

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
        self.flag_mask = np.zeros(n_visibilities, dtype=bool)
        self.undo_history = []
        self.reflag_history = []

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
        if self._data_dirty or self._cached_raw_data is None:
            self._cached_raw_data = self._native.get_uv_data()
            self._data_dirty = False
        data = self._cached_raw_data
        n = len(data.get('u', []))
        if self.flag_mask is None or len(self.flag_mask) != n:
            if self.flag_mask is not None and len(self.flag_mask) != n:
                logger.warning(
                    "Taille du masque de flagging (%d) incohérente avec les données UV (%d) — "
                    "réinitialisation du masque. Les flags précédents sont perdus.",
                    len(self.flag_mask), n
                )
            self.reset_flags(n)
        return data

    # =========================================================
    # API existante 
    # =========================================================

    @property
    def source(self) -> str:
        """
        Nom de la source astronomique active.

        Extrait directement depuis le header FITS chargé en mémoire C.
        Retourne ``'Inconnue'`` si aucune observation n'est active.

        Examples
        --------
        >>> session.observe("data/M87.uvfits")
        >>> print(session.obs.source)
        'M87'
        """
        if not self._session.uv_loaded:
            return "Inconnue"
        return self._native.get_source()

    def get_polarization(self) -> str:
        """
        Retourne la polarisation actuellement sélectionnée par le moteur C.

        Reflète l'état réel après le dernier appel à ``select()``.
        Retourne ``'Unknown'`` si aucune observation n'est active.

        Returns
        -------
        str
            Chaîne de polarisation, ex. ``'RR'``, ``'LL'``, ``'I'``.

        Examples
        --------
        >>> session.obs.select(pol="RR")
        >>> print(session.obs.get_polarization())
        'RR'
        """
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

    def select(self, pol: Polarization = "I",
               ifs: "tuple | list" = (1, 0),
               channels: tuple = (1, 0)) -> str:
        """
        Sélectionne la polarisation et les IFs à analyser.

        Parameters
        ----------
        pol : Polarization, optional
            Polarisation souhaitée. Par défaut ``"I"``.
        ifs : tuple or list of int, optional
            - ``(premier_if, dernier_if)`` : range contigu (0 = dernier IF).
              Ex : ``(1, 0)`` = tous, ``(2, 3)`` = IFs 2 et 3.
            - ``[1, 3, 4]`` : liste d'IFs non-contigus (1-indexed).
              Ex : ``[1, 3]`` = IF 1 et IF 3 seulement.
            Par défaut ``(1, 0)`` = tous les IFs.
        channels : tuple of int, optional
            ``(premier_canal, dernier_canal)``. Par défaut ``(1, 0)`` = tous.

        Returns
        -------
        str
            La polarisation réellement sélectionnée par le moteur C.

        Examples
        --------
        >>> session.obs.select(pol="RR")
        >>> session.obs.select(pol="I", ifs=(2, 3))   # IFs 2→3
        >>> session.obs.select(pol="I", ifs=[1, 3])   # IFs 1 et 3
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")

        pol = pol.upper()
        # Détection : liste non-contiguë vs tuple range
        if isinstance(ifs, (list, tuple)) and len(ifs) >= 2 and isinstance(ifs[0], (list, tuple)):
            # Format [(beg1,end1),(beg2,end2),...] non supporté ici — à aplatir
            raise ValueError("Utilisez une liste plate d'IFs : [1, 3, 4]")

        is_list = isinstance(ifs, list)

        if is_list:
            if self._native.select_ifs(pol, ifs) != 0:
                raise DifmapError(f"Échec de la sélection IFs {ifs} (Pol: {pol})")
            # channels=(1,0) signifie "tous les canaux" — ne pas appeler select_channels
            # dans ce cas car select_ifs a déjà tout sélectionné.
            if channels != (1, 0):
                nchan = max(1, self._native.get_nchan())
                echan_eff = channels[1] if channels[1] != 0 else nchan
                pairs = [
                    ((cif - 1) * nchan + channels[0], (cif - 1) * nchan + echan_eff)
                    for cif in ifs
                ]
                if self._native.select_channels(pol, pairs) != 0:
                    raise DifmapError(
                        f"Échec de select_channels pour IFs {ifs}, canaux {channels} (Pol: {pol})"
                    )
        else:
            if self._native.select(pol, ifs[0], ifs[1], channels[0], channels[1]) != 0:
                raise DifmapError(f"Échec de la sélection (Pol: {pol})")

        # Réinitialisation du masque 
        self.flag_mask = None
        self.undo_history.clear()
        self.invalidate_cache()

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

    def get_nchan(self) -> int:
        """
        Retourne le nombre de canaux par IF.

        Utile pour calculer les indices globaux de canaux passés à
        ``select_channels()`` et ``parse_select_syntax()``.
        Retourne ``0`` si aucune observation n'est chargée.

        Returns
        -------
        int
            Nombre de canaux par fréquence intermédiaire (IF).

        Examples
        --------
        >>> session.observe("data/source.uvfits")
        >>> print(session.obs.get_nchan())
        32
        """
        if not self._session.uv_loaded:
            return 0
        return self._native.get_nchan()

    def select_channels(self, pol: str, pairs: list) -> None:
        """
        Sélectionne des canaux par paires (index global, 1-indexed).

        Reproduit exactement ``uvsel_fn`` de difmap_src : construit un ``Chlist``
        et appelle ``ob_select``.

        Parameters
        ----------
        pol : str
            Polarisation cible (ex: ``"I"``, ``"RR"``).
        pairs : list of (int, int)
            Paires ``(bchan, echan)`` en index global ``cif * nchan + lchan``.
            Liste vide = tous les canaux / IFs.

        Examples
        --------
        >>> # Sélectionner IF 1 entier (nchan=32) :
        >>> session.obs.select_channels("I", [(1, 32)])
        >>> # IF 1 et IF 3 (canaux 1–32 et 65–96) :
        >>> session.obs.select_channels("I", [(1, 32), (65, 96)])
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        if self.flag_mask is not None and self.flag_mask.any():
            logger.warning(
                "select_channels() : %d flags actifs perdus suite au changement de sélection.",
                int(self.flag_mask.sum()),
            )
        if self._native.select_channels(pol.upper(), pairs) != 0:
            raise DifmapError(f"Échec de select_channels (Pol: {pol}, pairs: {pairs})")
        self.flag_mask = None
        self.undo_history.clear()
        self.invalidate_cache()

    @staticmethod
    def parse_select_syntax(text: str, nchan: int, nif: int) -> list:
        """
        Convertit une chaîne de sélection de canaux (syntaxe difmap) en paires d'indices.

        Les indices sont globaux, 1-indexed, séparés par des virgules et lus deux
        par deux comme ``(bchan, echan)``. Un nombre impair de valeurs = le dernier
        canal est utilisé seul (``bchan == echan``). Chaîne vide = tous les canaux.

        Parameters
        ----------
        text : str
            Chaîne de sélection, ex. ``"20, 25, 47, 65"`` ou ``"1, nif*nchan"``.
        nchan : int
            Nombre de canaux par IF (obtenu via ``get_nchan()``).
        nif : int
            Nombre d'IFs (obtenu via la propriété ``nif``).

        Returns
        -------
        list of (int, int)
            Liste de paires ``(bchan, echan)`` en indice global 1-indexed.
            Liste vide = sélectionner tous les canaux.

        Raises
        ------
        ValueError
            Si un indice de canal est hors plage ou si la syntaxe est invalide.

        Examples
        --------
        >>> # nchan=64, nif=3 → total 192 canaux
        >>> Observation.parse_select_syntax("20, 25, 47, 65", nchan=64, nif=3)
        [(20, 25), (47, 65)]
        >>> Observation.parse_select_syntax("10", nchan=64, nif=3)
        [(10, 10)]
        >>> Observation.parse_select_syntax("", nchan=64, nif=3)
        []
        >>> Observation.parse_select_syntax("1, nif*nchan", nchan=64, nif=3)
        [(1, 192)]
        """
        text = text.strip()
        if not text:
            return []

        total = max(1, nif) * max(1, nchan)

        def _eval(tok: str) -> int:
            tok = tok.strip()
            # Variables simples supportées
            tok = tok.replace("nif*nchan", str(total))
            tok = tok.replace("nif",   str(nif))
            tok = tok.replace("nchan", str(nchan))
            try:
                v = int(tok)
            except ValueError:
                raise ValueError(f"Valeur de canal invalide : '{tok}'")
            return v

        raw_tokens = [t.strip() for t in text.split(",") if t.strip()]
        nums: list[int] = []
        for tok in raw_tokens:
            if "-" in tok:
                a_s, b_s = [p.strip() for p in tok.split("-", 1)]
                nums.append(_eval(a_s))
                nums.append(_eval(b_s))
            else:
                nums.append(_eval(tok))
        if not nums:
            return []

        pairs = []
        i = 0
        while i < len(nums):
            bchan = nums[i]
            echan = nums[i + 1] if i + 1 < len(nums) else bchan  # impair → canal unique
            if bchan < 1 or echan < 1 or bchan > total or echan > total:
                raise ValueError(
                    f"Canal {bchan}..{echan} hors plage [1, {total}]"
                )
            pairs.append((bchan, echan))
            i += 2

        return pairs

    @staticmethod
    def ifs_from_pairs(pairs: list, nchan: int, nif: int) -> list[int]:
        """
        Retourne la liste triée des IFs couverts par des paires de canaux globaux.

        Parameters
        ----------
        pairs : list of (int, int)
            Paires ``(bchan, echan)`` en indice global 1-indexed.
        nchan : int
            Nombre de canaux par IF.
        nif : int
            Nombre total d'IFs.

        Returns
        -------
        list of int
            IFs concernés, triés, 1-indexed.

        Examples
        --------
        >>> Observation.ifs_from_pairs([(1, 32), (65, 96)], nchan=32, nif=4)
        [1, 3]
        """
        nchan = max(1, nchan)
        ifs = set()
        for bchan, echan in pairs:
            cif_lo = (bchan - 1) // nchan + 1
            cif_hi = (echan - 1) // nchan + 1
            for cif in range(cif_lo, min(cif_hi, nif) + 1):
                ifs.add(cif)
        return sorted(ifs)

    def set_if_range(self, if_beg: int, if_end: int) -> None:
        """
        Restreint l'extraction UV à une plage d'IFs sans recharger les données.

        Plus rapide que ``select()`` quand seul le filtre IF change : ne relit
        pas le fichier scratch, ne remet pas la polarisation à zéro.
        Appeler ``get_data()`` ensuite pour obtenir les données filtrées.

        Parameters
        ----------
        if_beg : int
            Premier IF souhaité (1-indexed). ``1`` = premier IF.
        if_end : int
            Dernier IF souhaité (1-indexed). ``0`` = jusqu'au dernier IF.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si l'appel C échoue.

        Examples
        --------
        >>> session.obs.select(pol="I")          # sélection initiale complète
        >>> session.obs.set_if_range(2, 3)       # restreindre aux IFs 2 et 3
        >>> data = session.obs.get_data()
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        if self._native.set_if_range(if_beg, if_end) != 0:
            raise DifmapError(f"Échec de set_if_range({if_beg}, {if_end})")
        self.flag_mask = None
        self.undo_history.clear()
        self.invalidate_cache()

    @property
    def nif(self) -> int:
        """
        Nombre total d'IFs dans l'observation courante.

        Retourne ``0`` si aucune observation n'est active. Utile pour construire
        les arguments de ``select()`` ou calculer les indices de canaux globaux.

        Examples
        --------
        >>> session.observe("data/source.uvfits")
        >>> print(session.obs.nif)
        4
        """
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
        Retourne les polarisations présentes dans le fichier chargé.

        La liste est extraite du header texte du moteur C. Elle peut contenir
        une ou plusieurs valeurs parmi ``"RR"``, ``"LL"``, ``"RL"``, ``"LR"``,
        ``"I"``, ``"Q"``, ``"U"``, ``"V"``. Retourne ``[]`` si rien n'est chargé.

        Returns
        -------
        list of str
            Polarisations disponibles, dans l'ordre du fichier.

        Examples
        --------
        >>> session.observe("data/source.uvfits")
        >>> session.obs.available_polarizations()
        ['RR', 'LL']
        """
        if not self._session.uv_loaded:
            return []

        match = re.search(r"^\s*Polarizations\s*:\s*(.+?)\s*$", self.header(), re.MULTILINE)
        if not match:
            return []

        _VALID = {"I", "Q", "U", "V", "RR", "LL", "RL", "LR", "XX", "YY", "XY", "YX"}
        tokens = [tok.strip().upper() for tok in re.split(r"[\s,]+", match.group(1)) if tok.strip()]
        seen = set()
        values = []
        for tok in tokens:
            if tok in _VALID and tok not in seen:
                seen.add(tok)
                values.append(tok)
        return values

    def flag_data(self, indices) -> int:
        """
        Marque les visibilités aux indices donnés comme exclues (flaguées).

        Met à jour simultanément l'état C (poids négatifs) et le masque
        Python ``flag_mask`` pour garantir leur cohérence.

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
        if len(indices_c) == 0:
            return 0
        result = self._native.flag_data(indices_c)
        # Mise à jour du cache en place : l_extract_uv filtre wt<=0, donc une
        # ré-extraction réduirait la taille du tableau et réinitialiserait
        # flag_mask. On applique wt = -|wt| dans la copie Python pour que
        # la taille reste stable et flag_mask reste cohérent.
        if self._cached_raw_data is not None:
            wgt = self._cached_raw_data.get('weight')
            if wgt is not None:
                valid = indices_c[(indices_c >= 0) & (indices_c < len(wgt))]
                wgt[valid] = -np.abs(wgt[valid])
        if self.flag_mask is not None:
            valid = indices_c[(indices_c >= 0) & (indices_c < len(self.flag_mask))]
            self.flag_mask[valid] = True
        self.notify_data_changed()
        return result

    def unflag_data(self, indices) -> int:
        """
        Restaure les visibilités précédemment flaguées.

        Met à jour simultanément l'état C (poids positifs) et le masque
        Python ``flag_mask``. Inverse exact de ``flag_data()``.

        Parameters
        ----------
        indices : array-like of int
            Indices (0-based) des visibilités à restaurer.

        Returns
        -------
        int
            Nombre de visibilités effectivement restaurées.

        Examples
        --------
        >>> session.obs.flag_data([10, 11, 12])
        3
        >>> session.obs.unflag_data([11])   # rétablir uniquement la visibilité 11
        1
        """
        indices_c = np.asarray(indices, dtype=np.int32)
        if len(indices_c) == 0:
            return 0
        result = self._native.unflag_data(indices_c)
        if self._cached_raw_data is not None:
            wgt = self._cached_raw_data.get('weight')
            if wgt is not None:
                valid = indices_c[(indices_c >= 0) & (indices_c < len(wgt))]
                wgt[valid] = np.abs(wgt[valid])
        if self.flag_mask is not None:
            valid = indices_c[(indices_c >= 0) & (indices_c < len(self.flag_mask))]
            self.flag_mask[valid] = False
        self.notify_data_changed()
        return result

    def save_wobs(self, filepath: str, do_shift: bool = False) -> bool:
        """
        Sauvegarde les données UV dans un fichier UVFITS (commande wobs difmap).

        Si l'extension ``'.fits'`` est absente du nom, elle est ajoutée automatiquement.

        Parameters
        ----------
        filepath : str
            Chemin de destination. Exemple : ``"sortie_editee.fits"``.
        do_shift : bool, optional
            Si True, décale le centre de pointage dans le fichier de sortie.

        Returns
        -------
        bool
            ``True`` si la sauvegarde a réussi.
        """
        if not filepath.lower().endswith('.fits'):
            filepath += '.fits'
        logger.info("Sauvegarde wobs vers : %s (do_shift=%s)", filepath, do_shift)
        self._native.save_wobs(filepath, do_shift)
        return True
