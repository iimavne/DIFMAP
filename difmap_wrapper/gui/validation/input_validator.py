# difmap_wrapper/gui/validation/input_validator.py
"""
Validateurs réutilisables pour les entrées utilisateur.

Avantage: Évite la duplication de validation, centralise la logique.
"""

from PyQt6.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox


class InputValidator:
    """
    Valide et récupère les valeurs des widgets avec sécurité.
    
    Inclut:
    - Gestion des valeurs vides
    - Limites min/max
    - Conversions de type
    - Gestion d'erreurs
    """
    
    @staticmethod
    def get_int(widget, default=0, min_val=None, max_val=None):
        """
        Récupère une valeur entière depuis un widget.
        
        Parameters
        ----------
        widget : QLineEdit or QSpinBox
        default : int
            Valeur par défaut si vide
        min_val : int, optional
            Valeur minimale acceptée
        max_val : int, optional
            Valeur maximale acceptée
        
        Returns
        -------
        int
        
        Raises
        ------
        ValueError
            Si conversion échoue ou valeur hors limites
        """
        try:
            if isinstance(widget, QSpinBox):
                val = widget.value()
            else:
                text = widget.text().strip()
                val = int(text) if text else default
            
            if min_val is not None and val < min_val:
                raise ValueError(f"Value must be >= {min_val}")
            if max_val is not None and val > max_val:
                raise ValueError(f"Value must be <= {max_val}")
            
            return val
            
        except ValueError as e:
            raise ValueError(f"Invalid integer value: {e}")
    
    @staticmethod
    def get_float(widget, default=0.0, min_val=None, max_val=None):
        """
        Récupère une valeur décimale depuis un widget.
        
        Parameters
        ----------
        widget : QLineEdit or QDoubleSpinBox
        default : float
            Valeur par défaut si vide
        min_val : float, optional
        max_val : float, optional
        
        Returns
        -------
        float
        
        Raises
        ------
        ValueError
        """
        try:
            if isinstance(widget, QDoubleSpinBox):
                val = widget.value()
            else:
                text = widget.text().strip()
                val = float(text) if text else default
            
            if min_val is not None and val < min_val:
                raise ValueError(f"Value must be >= {min_val}")
            if max_val is not None and val > max_val:
                raise ValueError(f"Value must be <= {max_val}")
            
            return val
            
        except ValueError as e:
            raise ValueError(f"Invalid float value: {e}")
    
    @staticmethod
    def get_string(widget, required=False, min_len=None, max_len=None):
        """
        Récupère une chaîne depuis un widget.
        
        Parameters
        ----------
        widget : QLineEdit
        required : bool
            Doit pas être vide
        min_len : int, optional
        max_len : int, optional
        
        Returns
        -------
        str
        
        Raises
        ------
        ValueError
        """
        try:
            text = widget.text().strip()
            
            if required and not text:
                raise ValueError("This field is required")
            if min_len is not None and len(text) < min_len:
                raise ValueError(f"Minimum {min_len} characters")
            if max_len is not None and len(text) > max_len:
                raise ValueError(f"Maximum {max_len} characters")
            
            return text
            
        except ValueError as e:
            raise ValueError(f"Invalid string value: {e}")
    
    @staticmethod
    def get_choice(widget):
        """Récupère la sélection actuelle d'une QComboBox."""
        return widget.currentText()


# Exemple d'utilisation en pratique :
# 
# from diffmap_wrapper.gui.validation import InputValidator
#
# try:
#     mapsize = InputValidator.get_int(
#         self.control_panel.input_mapsize,
#         default=256,
#         min_val=64,
#         max_val=4096
#     )
#     cellsize = InputValidator.get_float(
#         self.control_panel.input_cellsize,
#         default=1.0,
#         min_val=0.001,
#         max_val=10.0
#     )
# except ValueError as e:
#     self.log_console.log(f"Input error: {e}")
#     return
