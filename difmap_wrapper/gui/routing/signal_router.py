# difmap_wrapper/gui/routing/signal_router.py
"""
Centralise les connexions signal/slot pour éviter le boilerplate.

Avantage: 
- Élimine les patterns répétitifs lambda
- Facile à débugguer (pas de lambdas anonymes)
- Single point de modification
"""


class SignalRouter:
    """
    Connecte les signaux PyQt aux actions de l'éditeur de plots.
    
    Évite ~15 lignes de boilerplate lambda dans _connect_signals().
    """
    
    def __init__(self, main_window):
        """
        Parameters
        ----------
        main_window : MainWindow
            Instance de la fenêtre principale
        """
        self.window = main_window
        self.toolbar = main_window.toolbar
        self.control_panel = main_window.control_panel
    
    def _get_active_editor(self):
        """Récupère l'éditeur actif (sur l'onglet actuel)."""
        return self.window._get_active_editor()
    
    def route_toolbar_action(self, action_attr, method_name, args=None):
        """
        Connecte une action toolbar à une méthode d'éditeur (onglet actif).
        
        Parameters
        ----------
        action_attr : str
            Nom de l'attribut action (ex: 'action_home')
        method_name : str
            Nom de la méthode sur l'éditeur (ex: 'action_home')
        args : list, optional
            Arguments à passer à la méthode
        
        Example
        -------
        >>> router.route_toolbar_action('action_home', 'action_home')
        >>> router.route_toolbar_action('action_zoom', 'action_toggle_zoom', [None])
        """
        if not hasattr(self.toolbar, action_attr):
            print(f"Warning: Toolbar has no attribute {action_attr}")
            return
        
        action = getattr(self.toolbar, action_attr)
        args = args or []
        
        def callback():
            editor = self._get_active_editor()
            if editor and hasattr(editor, method_name):
                getattr(editor, method_name)(*args)
                # Important: Remettre le focus sur le graphique pour raccourcis clavier
                if hasattr(editor, 'fig') and hasattr(editor.fig, 'canvas'):
                    editor.fig.canvas.setFocus()
        
        action.triggered.connect(callback)
    
    def route_button_both(self, button_attr, method_name, args=None):
        """
        Connecte un bouton à une action sur TOUS les éditeurs (UV + Radplot).
        
        Utile pour les actions globales (ex: changer la taille des marqueurs).
        
        Parameters
        ----------
        button_attr : str
            Nom de l'attribut bouton (ex: 'btn_next_sub')
        method_name : str
            Nom de la méthode (ex: 'action_next_subarray')
        args : list, optional
        
        Example
        -------
        >>> router.route_button_both('btn_next_sub', 'action_next_subarray', [None])
        """
        if not hasattr(self.control_panel, button_attr):
            print(f"Warning: ControlPanel has no attribute {button_attr}")
            return
        
        button = getattr(self.control_panel, button_attr)
        args = args or []
        
        def callback():
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(*args)
        
        button.clicked.connect(callback)
    
    def route_checkbox_both(self, checkbox_attr, method_name):
        """
        Connecte une checkbox à une action bool sur tous les éditeurs.
        
        Parameters
        ----------
        checkbox_attr : str
        method_name : str
        
        Example
        -------
        >>> router.route_checkbox_both('chk_all_channels', 'set_flag_all_channels')
        """
        if not hasattr(self.control_panel, checkbox_attr):
            print(f"Warning: ControlPanel has no attribute {checkbox_attr}")
            return
        
        checkbox = getattr(self.control_panel, checkbox_attr)
        
        def callback(checked):
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(checked)
        
        checkbox.toggled.connect(callback)
    
    def route_slider_both(self, slider_attr, method_name):
        """
        Connecte un slider à une action sur tous les éditeurs.
        
        Parameters
        ----------
        slider_attr : str
        method_name : str
        
        Example
        -------
        >>> router.route_slider_both('slider_size', 'update_marker_size')
        """
        if not hasattr(self.control_panel, slider_attr):
            print(f"Warning: ControlPanel has no attribute {slider_attr}")
            return
        
        slider = getattr(self.control_panel, slider_attr)
        
        def callback(value):
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(float(value))
        
        slider.valueChanged.connect(callback)
    
    def connect_all(self):
        """
        Connecte TOUS les signaux en une seule appel.
        
        À utiliser dans main_window._connect_signals()
        """
        # TOOLBAR
        self.route_toolbar_action('action_home', 'action_home')
        self.route_toolbar_action('action_pan', 'action_toggle_pan', [None]) 
        self.route_toolbar_action('action_zoom', 'action_toggle_zoom', [None])
        self.route_toolbar_action('action_cut', 'action_toggle_cut', [None])
        
        # TELESCOPE FOCUS
        self.route_button_both('btn_next_sub', 'action_next_subarray', [None])
        self.route_button_both('btn_prev_sub', 'action_prev_subarray', [None])
        self.route_button_both('btn_next_ant', 'action_next_telescope', [None])
        self.route_button_both('btn_prev_ant', 'action_prev_telescope', [None])
        
        # SEARCH
        def search_callback():
            target = self.control_panel.input_search_tel.text()
            if target:
                for widget in [self.window.plot_widget, self.window.radplot_widget]:
                    if widget and hasattr(widget, 'editor') and widget.editor:
                        editor = widget.editor
                        if hasattr(editor, 'action_specific_telescope'):
                            editor.action_specific_telescope(None, target)
        
        self.control_panel.btn_search_tel.clicked.connect(search_callback)
        
        # FLAGGING & DISPLAY
        self.route_checkbox_both('chk_all_channels', 'set_flag_all_channels')
        self.route_checkbox_both('chk_conjugate', 'set_conjugate_visible')
        self.route_checkbox_both('chk_crosshair', 'set_crosshair_visible')
        self.route_slider_both('slider_size', 'update_marker_size')
        
        # IMAGING & DATA
        self.control_panel.btn_compute.clicked.connect(self.window._compute_dirty_map)
        self.control_panel.combo_pol.currentTextChanged.connect(self.window._change_polarization)


# Utilisation dans main_window.py:
# 
# def _connect_signals(self):
#     """Connecte tous les signaux via le router centralisé."""
#     router = SignalRouter(self)
#     router.connect_all()  # ← UNE SEULE LIGNE AU LIEU DE 30+
