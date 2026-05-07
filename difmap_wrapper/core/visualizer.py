# difmap_wrapper/visualizer.py
import difmap_native
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize, LogNorm, PowerNorm
from matplotlib.offsetbox import AnchoredOffsetbox, AuxTransformBox
import re
from datetime import datetime

class Visualizer:
    """
    Graphiques statiques pour explorer les données UV et les images.

    Accessible via ``session.vis``. Pour l'interactivité (flagging au clic,
    zoom, statistiques), utiliser l'interface graphique PyQt6.

    Examples
    --------
    >>> session.obs.select(pol="RR")
    >>> session.vis.uvplot()           # couverture UV
    >>> session.vis.radplot()          # amplitude vs rayon UV
    """

    def __init__(self, session):
        self._session = session
        self._native = difmap_native

    def uvplot(self, ax=None, figsize=(8, 8), color='blue', s=1, alpha=0.5,
               title=None, edgecolors='none', xlim=None, ylim=None,
               save_path: str = None, show: bool = True, **kwargs):
        """
        Affiche la couverture du plan UV (U en abscisse, V en ordonnée).

        Les coordonnées sont converties en Méga-longueurs d'onde (Mλ).
        Les points conjugués (−U, −V) sont ajoutés automatiquement.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axe sur lequel dessiner. Si absent, une nouvelle figure est créée.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces si une nouvelle figure est créée.
            Par défaut ``(8, 8)``.
        color : str, optional
            Couleur des points. Par défaut ``'blue'``.
        s : float, optional
            Taille des marqueurs en points². Par défaut ``1``.
        alpha : float, optional
            Transparence des points, entre 0 (invisible) et 1 (opaque).
            Par défaut ``0.5``.
        title : str, optional
            Titre du graphique. Si absent, un titre est généré automatiquement
            à partir du nom de la source.
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.axes.Axes.scatter``.

        Returns
        -------
        matplotlib.axes.Axes
            L'axe sur lequel la figure a été tracée.

        Examples
        --------
        >>> session.vis.uvplot(color='steelblue', s=2)

        Sur un axe existant :

        >>> fig, ax = plt.subplots()
        >>> session.vis.uvplot(ax=ax, color='red')
        """
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant uvplot().")
            return None

        u = data['u'] / 1e6
        v = data['v'] / 1e6

        # Suivi de la création de la figure
        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
            created_fig = True

        ax.scatter(u,  v,  s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)
        ax.scatter(-u, -v, s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)

        # Limites symétriques identiques sur les deux axes → plot carré
        max_range = float(max(np.abs(u).max(), np.abs(v).max())) * 1.1
        ax.set_xlim(max_range, -max_range)  # axe RA inversé
        ax.set_ylim(-max_range, max_range)

        ax.set_xlabel(r"U ($M\lambda$)")
        ax.set_ylabel(r"V ($M\lambda$)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Couverture UV : {source_name}")
        if xlim is not None:
            ax.set_xlim(xlim)
        if ylim is not None:
            ax.set_ylim(ylim)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.6)

        # Sauvegarde de la figure si demandée (avant l'affichage potentiel)
        if save_path:
            ax.get_figure().savefig(save_path, bbox_inches='tight')

        # Gestion de l'affichage et de la mémoire
        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax

    def radplot(self, ax=None, figsize=(10, 6), color='black', alpha=0.5, s=1,
                title=None, show_model: bool = True,
                model_color: str = 'red', model_alpha: float = 0.7, model_s: float = 1,
                save_path: str = None, show: bool = True, **kwargs):
        """
        Affiche l'amplitude des visibilités en fonction du rayon UV.

        Si un modèle CLEAN est disponible (après ``clean()``), superpose
        l'amplitude du modèle en rouge avec ``show_model=True``.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axe sur lequel dessiner.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces. Par défaut ``(10, 6)``.
        color : str, optional
            Couleur des points observés. Par défaut ``'black'``.
        alpha : float, optional
            Transparence des points observés. Par défaut ``0.5``.
        s : float, optional
            Taille des marqueurs observés. Par défaut ``1``.
        title : str, optional
            Titre du graphique.
        show_model : bool, optional
            Superpose l'amplitude du modèle si disponible. Par défaut ``True``.
        model_color : str, optional
            Couleur des points du modèle. Par défaut ``'red'``.
        model_alpha : float, optional
            Transparence des points du modèle. Par défaut ``0.7``.
        model_s : float, optional
            Taille des marqueurs du modèle. Par défaut ``1``.

        Returns
        -------
        matplotlib.axes.Axes

        Examples
        --------
        >>> session.vis.radplot()                        # données + modèle si dispo
        >>> session.vis.radplot(show_model=False)        # données seules
        >>> session.vis.radplot(color='navy', alpha=0.3, s=0.5)
        """
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant radplot().")
            return None

        u   = data['u']
        v   = data['v']
        amp = data['amp']
        uv_radius = np.sqrt(u**2 + v**2) / 1e6

        created_fig = ax is None
        if created_fig:
            fig, ax = plt.subplots(figsize=figsize)

        # Données observées
        ax.scatter(uv_radius, amp, s=s, color=color, alpha=alpha,
                   label='Observé', **kwargs)

        # Modèle CLEAN superposé
        if show_model:
            modamp = data.get('modamp')
            if modamp is not None and np.any(modamp != 0):
                ax.scatter(uv_radius, modamp, s=model_s, color=model_color,
                           alpha=model_alpha, label='Modèle', zorder=3)
                ax.legend(loc='upper right', fontsize=8, framealpha=0.7)

        ax.set_xlabel(r"Rayon UV ($M\lambda$)")
        ax.set_ylabel("Amplitude (Jy)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Radplot : {source_name}")
        ax.set_ylim(bottom=0)
        ax.grid(True, linestyle=':', alpha=0.6)

        if save_path:
            ax.get_figure().savefig(save_path, bbox_inches='tight')

        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax


    @staticmethod
    def _vis_central_peak(data: np.ndarray) -> float:
        """Pic signé sur la région d'affichage complète.

        Difmap garde le signe de l'extrême dominant dans maplot.c:setcont().
        """
        dmin = float(np.nanmin(data))
        dmax = float(np.nanmax(data))
        return dmax if abs(dmax) > abs(dmin) else dmin

    @staticmethod
    def _imageable_zone_peak(full_data: np.ndarray) -> float:
        """Pic signé sur la zone imageable (centre 1/4..3/4 de la carte).

        DIFMAP/PGPLOT calcule typiquement les contours sur une zone "imageable"
        centrale plutôt que sur l'intégralité des bords.
        """
        ny, nx = full_data.shape
        y0, y1 = ny // 4, 3 * ny // 4
        x0, x1 = nx // 4, 3 * nx // 4
        y0 = max(0, y0)
        x0 = max(0, x0)
        y1 = min(ny, y1)
        x1 = min(nx, x1)
        if y1 <= y0 or x1 <= x0:
            return Visualizer._vis_central_peak(full_data)
        return Visualizer._vis_central_peak(full_data[y0:y1, x0:x1])

    @staticmethod
    def _make_norm(scale: str, vmin, vmax, data: np.ndarray):
        """Normalisation matplotlib équivalente à mapfunc de difmap (linear/log/sqrt)."""
        dmin = float(np.nanmin(data))
        dmax = float(np.nanmax(data))
        v_lo = vmin if vmin is not None else dmin
        v_hi = vmax if vmax is not None else dmax
        if scale == 'log':
            safe_lo = max(v_lo, v_hi * 1e-4, 1e-12) if v_hi > 0 else 1e-6
            return LogNorm(vmin=safe_lo, vmax=v_hi)
        if scale == 'sqrt':
            return PowerNorm(gamma=0.5, vmin=max(v_lo, 0.0), vmax=v_hi)
        return Normalize(vmin=v_lo, vmax=v_hi)

    @staticmethod
    def _compute_contour_levels(peak, mode='pct', absmin=1.0, absmax=100.0,
                                 factor=2.0, custom=None):
        """
        Calcule les niveaux de contours selon Difmap.

        - Défaut maplot.c:setcont(): [-1, 1, 2, 4, 8, 16, 32, 64] % du pic signé.
        - loglevs: [-absmin, absmin, absmin*factor, ...] % du pic signé.
        - custom/clevs: niveaux absolus fournis en Jy/beam.
        """
        if peak == 0:
            return []

        mode = (mode or 'pct').lower()
        if mode in {'custom', 'clevs'}:
            # DIFMAP: levs est en % du pic tant que cmul<=0 (cas standard)
            # Ici, on suit ce comportement: les niveaux custom sont interprétés en % du pic.
            if not custom:
                return []
            if peak is None or float(peak) == 0.0:
                return []
            out = []
            for x in custom:
                try:
                    v = float(x)
                except Exception:
                    continue
                if not np.isfinite(v) or v == 0.0:
                    continue
                out.append(v * float(peak) / 100.0)
            return out

        if mode in {'pct', 'levs', 'default', 'standard'}:
            return [pct * peak / 100.0 for pct in (-1.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)]

        if mode not in {'log', 'loglevs'}:
            return []

        absmin = abs(float(absmin))
        absmax = abs(float(absmax))
        factor = abs(float(factor))
        if absmin > absmax:
            absmin, absmax = absmax, absmin

        # DIFMAP: loglevs génère des niveaux en % du pic avec un facteur ~2
        # et sature typiquement à 100%.
        absmax = min(absmax, 100.0)
        if factor <= 1.0:
            factor = 2.0

        if absmin < 1.0e-5 or absmax < 1.0e-5:
            return []

        # loglevs N  =>  -N, +N, +2N, +4N, ... (jusqu'à 100%)
        pct_levels = [-absmin]
        val = absmin
        while val <= absmax:
            pct_levels.append(val)
            val *= factor
        return [pct * peak / 100.0 for pct in pct_levels]

    @staticmethod
    def _vis_draw_contours(ax, data, x_lin, y_lin, peak, lw=0.8,
                           mode='pct', absmin=1.0, absmax=100.0,
                           factor=2.0, custom=None):
        """
        Contours difmap : négatifs en rouge, positifs en blanc, traits pleins.
        Supporte les modes 'pct' (levs), 'log' (loglevs) et 'custom'.
        Retourne la liste des niveaux tracés (Jy/beam).
        """
        levels = Visualizer._compute_contour_levels(peak, mode, absmin, absmax, factor, custom)
        if not levels:
            return []
        cmin = float(np.nanmin(data))
        cmax = float(np.nanmax(data))
        visible = [l for l in levels if cmin < l < cmax]
        if not visible:
            return []

        pos_levels = sorted([l for l in visible if l >= 0])
        neg_levels = sorted([l for l in visible if l < 0])

        drawn = []
        if pos_levels:
            ax.contour(
                x_lin, y_lin, data, levels=pos_levels,
                colors='white', linewidths=lw, linestyles='solid',
                alpha=1.0
            )
            drawn.extend(pos_levels)
        if neg_levels:
            ax.contour(
                x_lin, y_lin, data, levels=neg_levels,
                colors='red', linewidths=lw, linestyles='solid',
                alpha=1.0
            )
            drawn.extend(neg_levels)
        return drawn

    @staticmethod
    def _vis_add_annotations(ax, data, map_type, info=None,
                              drawn_levels=None, contour_mode='pct'):
        """
        Bloc d'annotations style PGPLOT — coin supérieur droit, contenu par type de carte.

        Clean map  : Peak, RMS, SNR, Beam FWHM, niveaux de contours
        Dirty map  : Range affiché, RMS
        Residual   : Peak résiduel, RMS
        """
        peak_val = float(np.nanmax(np.abs(data)))
        dmin     = float(np.nanmin(data))
        dmax     = float(np.nanmax(data))

        # Calcul RMS (zone centrale pour éviter les bords)
        ny, nx = data.shape
        cy, cx = ny // 2, nx // 2
        margin = max(ny // 8, 4)
        rms_zone = data[cy - margin:cy + margin, cx - margin:cx + margin]
        rms = float(np.sqrt(np.nanmean(rms_zone ** 2))) if rms_zone.size > 0 else 0.0

        lines = []

        if map_type == "clean":
            snr = dmax / rms if rms > 0 else 0.0
            lines.append(("Peak",    f"{dmax:.4g} Jy/beam"))
            lines.append(("RMS",     f"{rms:.3g} Jy/beam"))
            lines.append(("SNR",     f"{snr:.1f}"))
            if info:
                bmaj = info.get('bmaj', 0.0)
                bmin = info.get('bmin', 0.0)
                bpa  = info.get('bpa',  0.0)
                if bmaj > 0 and bmin > 0:
                    lines.append(("Beam", f"{bmaj:.3g}″ × {bmin:.3g}″  PA {bpa:.1f}°"))
            if drawn_levels:
                cpeak = Visualizer._imageable_zone_peak(data)
                if (contour_mode or '').lower() in {'custom', 'clevs'}:
                    lvl_str = ", ".join(f"{l:.3g}" for l in drawn_levels[:6])
                    lines.append(("Levels Jy/b", lvl_str))
                elif cpeak != 0:
                    pct_str = ", ".join(f"{l / cpeak * 100:.2g}" for l in drawn_levels[:6])
                    lines.append(("Contours %", pct_str))

        elif map_type == "residual":
            lines.append(("Peak res.", f"{dmax:.4g} Jy/beam"))
            lines.append(("Min  res.", f"{dmin:.4g} Jy/beam"))
            lines.append(("RMS",       f"{rms:.3g} Jy/beam"))

        else:  # dirty
            lines.append(("Range", f"{dmin:.3g}  –  {dmax:.3g} Jy/beam"))
            lines.append(("RMS",   f"{rms:.3g} Jy/beam"))

        if not lines:
            return

        # Rendu : texte en bas de l'axe, en dehors de la grille
        # Ne pas utiliser xlabel (ça modifie le layout et crée une marge)

        # Construire un bloc proche de ce que DIFMAP/PGPLOT affiche (maplot.c)
        formatted_lines: list[str] = []

        session = getattr(ax, '_difmap_session', None)
        source = None
        pol = None
        if session is not None:
            try:
                source = session.obs.source
            except Exception:
                source = None
            try:
                pol = session.obs.get_polarization()
            except Exception:
                pol = None

        header_text = ""
        try:
            header_text = difmap_native.get_header_text() or ""
        except Exception:
            header_text = ""

        # Fréquence moyenne en GHz depuis le tableau du header
        freq_ghz = 0.0
        if header_text:
            freqs = []
            for m in re.finditer(r"^\s*\d+\s+\d+\s+([0-9.]+e[+-]\d+)", header_text, flags=re.MULTILINE):
                try:
                    freqs.append(float(m.group(1)))
                except Exception:
                    continue
            if freqs:
                freq_ghz = float(np.mean(freqs)) / 1e9

        # Date si présente
        date_str = ""
        if header_text:
            m = re.search(r"\b(19|20)\d{2}\s+[A-Za-z]{3}\s+\d{1,2}\b", header_text)
            if m:
                date_str = m.group(0)

        # Stations: utiliser indices tel_a/tel_b pour déduire Ntel puis noms
        stations_str = ""
        try:
            uv = difmap_native.get_uv_data() or {}
            tel_a = uv.get('tel_a')
            tel_b = uv.get('tel_b')
            sub = uv.get('subarray')
            if tel_a is not None and tel_b is not None and len(tel_a) and len(tel_b):
                n_tel = int(max(int(np.max(tel_a)), int(np.max(tel_b)))) + 1
                isub = int(sub[0]) if sub is not None and len(sub) else 0
                codes = []
                for itel in range(n_tel):
                    name = difmap_native.get_telescope_name(isub, itel)
                    if not name:
                        continue
                    code = name.strip().upper()[:2]
                    codes.append(code)
                if codes:
                    # difmap affiche souvent une concaténation compacte
                    stations_str = "".join(sorted(set(codes)))
        except Exception:
            stations_str = ""

        # Map center: tenter d'extraire RA/Dec du header (sinon placeholder)
        ra = "00 00 00.000"
        dec = "+00 00 00.000"
        if header_text:
            m = re.search(r"RA\s*[=:]\s*([0-9:.\s]+)\s*,?\s*Dec\s*[=:]\s*([+\-0-9:.\s]+)", header_text, flags=re.IGNORECASE)
            if m:
                ra = " ".join(m.group(1).strip().replace(':', ' ').split())
                dec = " ".join(m.group(2).strip().replace(':', ' ').split())

        # Lignes de tête
        map_label = (map_type or 'dirty').capitalize()
        pol_txt = pol or "XX"
        if stations_str:
            formatted_lines.append(f"{map_label} {pol_txt} map.  Array: {stations_str}")
        else:
            formatted_lines.append(f"{map_label} {pol_txt} map.")

        src = source or "Unknown"
        if freq_ghz > 0 and date_str:
            formatted_lines.append(f"{src}  at {freq_ghz:.3f} GHz  {date_str}")
        elif freq_ghz > 0:
            formatted_lines.append(f"{src}  at {freq_ghz:.3f} GHz")
        elif date_str:
            formatted_lines.append(f"{src}  {date_str}")
        else:
            formatted_lines.append(f"{src}  {datetime.now().strftime('%Y %b %d')}")

        # Infos par type de map
        dmin = float(np.nanmin(data))
        dmax = float(np.nanmax(data))
        rms = float(info.get('rms', 0.0)) if isinstance(info, dict) else 0.0

        formatted_lines.append(f"Map center:  RA: {ra},  Dec: {dec} (2000.0)")
        formatted_lines.append(f"Displayed range: {dmin:.4g} to {dmax:.4g} Jy/beam")

        if map_type == 'clean':
            formatted_lines.append(f"Map peak: {dmax:.4g} Jy/beam")
            if drawn_levels:
                cpeak = Visualizer._imageable_zone_peak(data)
                if cpeak != 0:
                    pct_levels = [float(lvl) / cpeak * 100.0 for lvl in drawn_levels if np.isfinite(lvl)]
                    show = pct_levels[:8]
                    suffix = " ..." if len(pct_levels) > 8 else ""
                    formatted_lines.append(
                        "Contours %: " + " ".join(f"{p:.0g}" for p in show) + suffix
                    )
            if isinstance(info, dict):
                bmaj = float(info.get('bmaj', 0.0) or 0.0)
                bmin = float(info.get('bmin', 0.0) or 0.0)
                bpa = float(info.get('bpa', 0.0) or 0.0)
                if bmaj > 0 and bmin > 0:
                    formatted_lines.append(f"Beam FWHM: {bmaj:.3g} × {bmin:.3g} (mas) at {bpa:.2f}°")

        if map_type in {'residual', 'clean'} and rms > 0:
            formatted_lines.append(f"RMS: {rms:.4g} Jy/beam")
            peak_abs = float(np.nanmax(np.abs(data)))
            formatted_lines.append(f"{peak_abs / rms:.1f}σ")

        text_content = "\n".join(formatted_lines)
        ax.text(
            0.5, -0.12, text_content,
            transform=ax.transAxes,
            ha='center', va='top',
            fontsize=7.5,
            fontfamily='monospace',
            color='black',
            clip_on=False,
            zorder=10,
        )

    @staticmethod
    def plot_clean_map(img_dict: dict, windows=None, ax=None,
                       cmap: str = 'inferno', figsize: tuple = (8, 8),
                       title: str = None,
                       scale: str = 'linear', vmin=None, vmax=None,
                       contour_mode: str = 'pct',
                       contour_absmin: float = 1.0, contour_absmax: float = 100.0,
                       contour_factor: float = 2.0, contour_custom=None,
                       show_model: bool = False,
                       save_path: str = None, show: bool = True) -> 'plt.Axes':
        """
        Affichage scientifique d'une Clean Map, Residual Map ou Dirty Map,
        identique au mode pgplot de Difmap (maplot.c).

        Comportement selon ``img_dict['map_type']`` :

        - ``"clean"``    → "Map peak: X Jy/beam" + ellipse du faisceau
        - ``"residual"`` → "Displayed range: min □ max Jy/beam", pas d'ellipse
        - ``"dirty"``    → idem résiduel

        Parameters
        ----------
        img_dict : dict
            Dictionnaire retourné par ``get_map_package()`` ou ``get_residual_package()``.
        windows : list of tuple, optional
            Fenêtres CLEAN ``[(xa, xb, ya, yb)]`` en mas.
        ax : matplotlib.axes.Axes, optional
            Axe existant. Si absent, une nouvelle figure est créée.
        cmap : str
            Palette de couleurs. Par défaut ``'inferno'``.
        figsize : tuple
            Taille de la figure. Par défaut ``(8, 8)``.
        title : str, optional
            Titre. Si absent, déduit de ``map_type``.
        scale : str, optional
            Échelle de couleur : ``'linear'``, ``'log'`` ou ``'sqrt'`` (mapfunc).
        vmin, vmax : float, optional
            Bornes de la colormap (``None`` = automatique).
        contour_mode : str, optional
            ``'pct'`` (levs Difmap), ``'log'`` (loglevs) ou ``'custom'``.
        contour_absmin : float
            Pour ``'log'`` : niveau min en % du pic (défaut 1 %).
        contour_absmax : float
            Pour ``'log'`` : niveau max en % du pic (défaut 100 %).
        contour_factor : float
            Pour ``'log'`` : facteur multiplicatif (défaut 2.0).
        contour_custom : list of float, optional
            Pour ``'custom'`` : niveaux absolus en Jy/beam.
        save_path : str, optional
            Chemin de sauvegarde.
        show : bool
            Afficher si True.

        Returns
        -------
        matplotlib.axes.Axes
        """
        from matplotlib.patches import Ellipse, Rectangle

        if "data" not in img_dict or "extent" not in img_dict:
            raise KeyError("Le dictionnaire doit contenir les clés 'data' et 'extent'.")

        map_type = img_dict.get("map_type", "dirty")

        _TYPE_TITLE = {"clean": "Clean map.", "residual": "Residual map.", "dirty": "Dirty map."}
        if title is None:
            title = _TYPE_TITLE.get(map_type, "Map")

        created_fig = ax is None
        if created_fig:
            fig, ax = plt.subplots(figsize=figsize)

        data = img_dict['data']
        info = img_dict.get('info', {})
        extent = img_dict['extent']  # [xmax, xmin, ymin, ymax]
        xmax_e, xmin_e, ymin_e, ymax_e = extent
        astrometric_extent = [xmax_e, xmin_e, ymin_e, ymax_e]

        ny_px, nx_px = data.shape
        x_pixel_size = (xmin_e - xmax_e) / nx_px
        y_pixel_size = (ymax_e - ymin_e) / ny_px
        x_coords = np.linspace(xmax_e, xmin_e, nx_px, endpoint=False) + x_pixel_size / 2
        y_coords = np.linspace(ymin_e, ymax_e, ny_px, endpoint=False) + y_pixel_size / 2
        x_grid, y_grid = np.meshgrid(x_coords, y_coords)

        # 1. Image de fond
        scale_l = (scale or 'linear').lower()
        data_show = np.ma.masked_less_equal(data, 0.0) if scale_l == 'log' else data
        norm = Visualizer._make_norm(scale, vmin, vmax, data)
        im = ax.imshow(data_show, origin='lower', extent=astrometric_extent, cmap=cmap,
                       aspect='equal', norm=norm)
        ax.get_figure().colorbar(im, ax=ax, label='Flux (Jy/beam)', fraction=0.046, pad=0.04)

        # 3. Contours isophotes
        # Difmap calcule les niveaux sur la zone "imageable" (centre), pas sur les bords
        peak = Visualizer._imageable_zone_peak(data)
        drawn = Visualizer._vis_draw_contours(
            ax, data, x_grid, y_grid, peak,
            mode=contour_mode, absmin=contour_absmin, absmax=contour_absmax,
            factor=contour_factor, custom=contour_custom
        )

        # 4. Fenêtres CLEAN
        active_wins = windows if windows is not None else img_dict.get('windows', [])
        for (xa, xb, ya, yb) in active_wins:
            x0, y0 = min(xa, xb), min(ya, yb)
            w, h   = abs(xb - xa), abs(yb - ya)
            ax.add_patch(Rectangle(
                (x0, y0), w, h,
                linewidth=1.3, edgecolor='cyan', facecolor='none', linestyle='--', alpha=0.85
            ))

        # 5. Composantes du modèle CLEAN (optionnel, show_model=True)
        # Logique exacte de DIFMAP modplot.c:cmpplot():
        # - type == delta → affiche '+' (symbole 2 PGPLOT)
        # - type != delta → affiche ellipse (major, ratio, phi)
        # Couleurs selon DIFMAP modplot.c:31-70:
        # - freepar=0 (fixed) + flux>0 → color 10 (lime/green)
        # - freepar=0 (fixed) + flux<0 → color 2 (red)
        # Les composantes CLEAN sont toujours freepar=0 (fixed)
        # Vérification des limites comme DIFMAP modplot.c:74
        if show_model:
            import math
            from matplotlib.patches import Ellipse as _Ellipse
            
            # Récupérer les limites d'affichage
            xa, xb = extent[0], extent[1]
            ya, yb = extent[2], extent[3]
            if xa > xb:
                xa, xb = xb, xa
            if ya > yb:
                ya, yb = yb, ya
            
            for cmp in img_dict.get('model_components', []):
                cx, cy = cmp['x'], cmp['y']
                cmp_type = cmp.get('type', 'delta')
                major = cmp.get('major', 0.0)
                flux = cmp.get('flux', 0.0)
                
                # Vérifier si le centre est visible (comme DIFMAP cmpplot:74)
                visible = (cx >= xa and cx <= xb and cy >= ya and cy <= yb)
                if not visible:
                    continue  # Ne pas afficher les composantes hors limites
                
                # Couleur selon le signe du flux (comme DIFMAP)
                if flux >= 0:
                    color = 'lime'      # PGPLOT color 10 (green/yellow)
                else:
                    color = 'red'        # PGPLOT color 2 (red)
                
                # Delta components: afficher '+' uniquement
                if cmp_type == 'delta' or major <= 0:
                    ax.plot(cx, cy, '+', color=color, markersize=5,
                            markeredgewidth=0.8, alpha=0.9, zorder=6)
                else:
                    # Composantes étendues: afficher ellipse uniquement
                    phi_rad = cmp.get('phi', 0.0)
                    ratio = cmp.get('ratio', 1.0)
                    angle_deg = 90.0 - math.degrees(phi_rad)
                    minor = major * ratio
                    ax.add_patch(_Ellipse(
                        (cx, cy),
                        width=major,
                        height=minor,
                        angle=angle_deg,
                        facecolor='none', edgecolor=color,
                        linewidth=0.8, alpha=0.9, zorder=6
                    ))

        # 6. Ellipse faisceau propre (uniquement pour carte restaurée)
        if map_type == "clean":
            bmaj = info.get('bmaj', 0.0)
            bmin = info.get('bmin', 0.0)
            bpa  = info.get('bpa',  0.0)
            if bmaj > 0 and bmin > 0:
                beam_box = AuxTransformBox(ax.transData)
                beam_box.add_artist(Ellipse(
                    (0.0, 0.0), width=bmaj, height=bmin, angle=90 - bpa,
                    facecolor='gold', edgecolor='white', linewidth=1, alpha=0.85, zorder=5
                ))
                ax.add_artist(AnchoredOffsetbox(
                    loc='lower left', child=beam_box,
                    pad=0.0, borderpad=1.5, frameon=False
                ))

        # 6. Annotations texte (en bas, en dehors de la grille)
        Visualizer._vis_add_annotations(ax, data, map_type, info=info,
                                         drawn_levels=drawn, contour_mode=contour_mode)

        ax.set_xlabel("Décalage RA (mas)")
        ax.set_ylabel("Décalage Dec (mas)")
        ax.set_title(title)
        # Note: xlabel est défini dans _vis_add_annotations

        if save_path and created_fig:
            ax.get_figure().savefig(save_path, bbox_inches='tight')
        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax

    @staticmethod
    def plot_image(img_dict: dict, ax=None, cmap: str = None, figsize: tuple = (8, 6),
                   title: str = None, xlim=None, ylim=None,
                   scale: str = 'linear', vmin=None, vmax=None,
                   contour_mode: str = 'pct',
                   contour_absmin: float = 1.0, contour_absmax: float = 100.0,
                   contour_factor: float = 2.0, contour_custom=None,
                   show_model: bool = False,
                   save_path: str = None, show: bool = True, **kwargs) -> 'plt.Axes':
        """
        Affiche une image astrophysique avec sa barre de couleur et ses axes astrométriques.

        Le titre et la palette de couleurs sont déduits automatiquement de la clé
        ``'map_type'`` du dictionnaire (``"dirty"`` → "Dirty Map" / inferno,
        ``"clean"`` → "Clean Map" / viridis) sauf si ``title`` ou ``cmap``
        sont fournis explicitement.

        Parameters
        ----------
        img_dict : dict
            Dictionnaire retourné par ``DifmapImager.get_map_package()``.
            Doit contenir les clés ``'data'`` (tableau 2D) et ``'extent'``
            (limites en mas pour les axes). La clé optionnelle ``'map_type'``
            (``"dirty"`` ou ``"clean"``) est utilisée pour choisir le titre
            et la palette par défaut.
        cmap : str, optional
            Palette de couleurs Matplotlib. Si absent, déduit de ``map_type``.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces. Par défaut ``(8, 6)``.
        title : str, optional
            Titre affiché au-dessus de l'image. Si absent, déduit de ``map_type``.
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.pyplot.imshow``.

        Raises
        ------
        KeyError
            Si les clés ``'data'`` ou ``'extent'`` sont absentes du dictionnaire.

        Examples
        --------
        >>> img = session.imager.make_dirty_map(512, 0.1)
        >>> session.vis.plot_image(img)                          # titre auto "Dirty Map"
        >>> img2 = session.imager.make_clean_map(512, 0.1)
        >>> session.vis.plot_image(img2)                         # titre auto "Clean Map"
        >>> session.vis.plot_image(img, title="Source J0003")    # titre explicite
        """
        if "data" not in img_dict or "extent" not in img_dict:
            raise KeyError("Le dictionnaire d'image doit contenir les clés 'data' et 'extent'.")

        map_type = img_dict.get("map_type", "dirty")

        # Les Clean Maps utilisent l'affichage scientifique complet (contours + beam + fenêtres)
        if map_type == "clean":
            return Visualizer.plot_clean_map(
                img_dict,
                ax=ax,
                cmap=cmap or 'inferno',
                figsize=figsize,
                title=title or "Clean Map",
                scale=scale, vmin=vmin, vmax=vmax,
                contour_mode=contour_mode, contour_absmin=contour_absmin,
                contour_absmax=contour_absmax, contour_factor=contour_factor,
                contour_custom=contour_custom,
                show_model=show_model,
                save_path=save_path,
                show=show,
            )

        if title is None:
            title = "Residual map." if map_type == "residual" else "Dirty map."
        if cmap is None:
            cmap = "inferno"

        extent = img_dict['extent']  # [xmax, xmin, ymin, ymax]
        xmax_e, xmin_e, ymin_e, ymax_e = extent
        astrometric_extent = [xmax_e, xmin_e, ymin_e, ymax_e]
        data = img_dict['data']
        ny_px, nx_px = data.shape
        x_lin = np.linspace(xmax_e, xmin_e, nx_px)
        y_lin = np.linspace(ymin_e, ymax_e, ny_px)

        created_fig = ax is None
        if created_fig:
            fig, ax = plt.subplots(figsize=figsize)

        scale_l = (scale or 'linear').lower()
        data_show = np.ma.masked_less_equal(data, 0.0) if scale_l == 'log' else data
        norm = Visualizer._make_norm(scale, vmin, vmax, data)
        im = ax.imshow(data_show, extent=astrometric_extent, origin='lower', cmap=cmap,
                       aspect='equal', norm=norm, **kwargs)
        ax.get_figure().colorbar(im, ax=ax, label='Flux (Jy/beam)')

        # IMPORTANT: Difmap n'affiche les contours QUE sur les clean maps restaurées (ncmp > 0)
        # Voir difmap.c:3855: docont = mappar.docont && ((vlbmap->ncmp && domap) || ...)
        # Dirty et Residual maps n'ont JAMAIS de contours
        # Pas de contours, pas d'annotations de niveaux pour dirty/residual
        Visualizer._vis_add_annotations(ax, data, map_type,
                                         drawn_levels=None, contour_mode='none')

        ax.set_title(title)
        ax.set_xlabel("Décalage RA (mas)")
        ax.set_ylabel("Décalage Dec (mas)")
        # Coller l'affichage à l'extent exact par défaut (évite la marge "cadre")
        if xlim is not None:
            ax.set_xlim(xlim)
        else:
            ax.set_xlim(astrometric_extent[0], astrometric_extent[1])
        if ylim is not None:
            ax.set_ylim(ylim)
        else:
            ax.set_ylim(astrometric_extent[2], astrometric_extent[3])

        if save_path and created_fig:
            ax.get_figure().savefig(save_path, bbox_inches='tight')

        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax
    def mapplot(self, img_dict: dict = None, **kwargs):
        """
        Affiche l'image actuellement en mémoire.

        Si ``img_dict`` est absent, récupère automatiquement l'image depuis le
        moteur C avec les paramètres du dernier ``mapsize()``.

        Parameters
        ----------
        img_dict : dict, optional
            Package image (sortie de ``get_map_package()``). Si absent, l'image
            courante en mémoire C est utilisée.
        **kwargs
            Paramètres supplémentaires transmis à ``plot_image()``.

        Raises
        ------
        DifmapStateError
            Si ``mapsize()`` n'a pas encore été appelé.

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)
        >>> session.imager.invert()
        >>> session.vis.mapplot(title="Dirty Map après inversion")
        """
        if img_dict is None:
            from ..utils.exceptions import DifmapStateError
            if self._session.imager._last_cellsize is None:
                raise DifmapStateError(
                    "Astrométrie inconnue. Veuillez exécuter mapsize() avant mapplot()."
                )
            img_dict = self._session.imager.get_map_package(
                cellsize=self._session.imager._last_cellsize
            )
        # Titre automatique si l'appelant n'en fournit pas
        kwargs.setdefault(
            "title",
            "Clean Map" if img_dict.get("map_type") == "clean" else "Dirty Map"
        )
        return self.plot_image(img_dict, **kwargs)
