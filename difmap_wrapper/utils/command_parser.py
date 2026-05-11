"""
Parseur et exécuteur de commandes Difmap pour Python.
Permet l'exécution de scripts Difmap natives directement en Python,
incluant le support des macros avec @.
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class CommandNotFoundError(Exception):
    """Exception levée quand une commande n'existe pas."""
    pass


class CommandParser:
    """
    Parseur pour les scripts et commandes Difmap.
    
    Supporte :
    - Commandes simples : observe /path/to/file.uvf
    - Paramètres multiples : uvweight 10 2 1
    - Commentaires : ! ceci est un commentaire
    - Macros : @macrofilename.cmd
    - Chaînes avec guillements : device /ps myfig.ps
    """

    def __init__(self):
        self.commands: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable) -> None:
        """
        Enregistre une fonction de commande.
        
        Parameters
        ----------
        name : str
            Nom de la commande (sera en minuscules)
        func : Callable
            Fonction à appeler avec les arguments parsés
        """
        self.commands[name.lower()] = func

    def parse_line(self, line: str) -> Optional[Tuple[str, List[str]]]:
        """
        Parse une ligne unique de commande Difmap.
        
        Formats supportés:
        - observe /path/file.uvf     → ('observe', ['/path/file.uvf'])
        - uvweight 10 2 1             → ('uvweight', ['10', '2', '1'])
        - ! commentaire               → None
        - @macroname.cmd              → ('@include', ['macroname.cmd'])
        
        Parameters
        ----------
        line : str
            Ligne texte à parser
            
        Returns
        -------
        Optional[Tuple[str, List[str]]]
            (command_name, [args]) ou None si ligne vide/commentaire
        """
        # Nettoyer les espaces leading/trailing
        line = line.strip()

        # Ignorer les lignes vides et commentaires
        if not line or line.startswith("!"):
            return None

        # Détecrer macro (@fichier)
        if line.startswith("@"):
            macro_name = line[1:].strip()
            return ("@include", [macro_name])

        # Parser les tokens respectant les guillemets
        tokens = self._tokenize(line)
        if not tokens:
            return None

        command = tokens[0].lower()
        args = tokens[1:]

        return (command, args)

    def _tokenize(self, line: str) -> List[str]:
        """
        Tokenise une ligne respectant les guillemets simples/doubles.
        
        "mon path/fichier.txt" → un seul token
        'chemin/fichier' arg2 → deux tokens
        """
        tokens = []
        current_token = ""
        in_double_quote = False
        in_single_quote = False
        i = 0

        while i < len(line):
            char = line[i]

            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                i += 1
            elif char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                i += 1
            elif char in (' ', '\t') and not in_double_quote and not in_single_quote:
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                i += 1
            else:
                current_token += char
                i += 1

        if current_token:
            tokens.append(current_token)

        return tokens

    def parse_script(self, script_text: str) -> List[Tuple[str, List[str]]]:
        """
        Parse un script complet lignepar ligne.
        
        Parameters
        ----------
        script_text : str
            Script Difmap multilignes
            
        Returns
        -------
        List[Tuple[str, List[str]]]
            Liste des commandes parsées
        """
        commands = []
        for line in script_text.split('\n'):
            parsed = self.parse_line(line)
            if parsed:
                commands.append(parsed)
        return commands

    def load_macro(self, macro_path: Union[str, Path]) -> List[Tuple[str, List[str]]]:
        """
        Charge une macro depuis un fichier.
        
        Parameters
        ----------
        macro_path : Union[str, Path]
            Chemin du fichier macro (.cmd ou .txt)
            
        Returns
        -------
        List[Tuple[str, List[str]]]
            Commandes du fichier macro
            
        Raises
        ------
        FileNotFoundError
            Si le fichier n'existe pas
        """
        path = Path(macro_path)
        if not path.exists():
            raise FileNotFoundError(f"Macro file not found: {macro_path}")

        with open(path, 'r') as f:
            content = f.read()

        return self.parse_script(content)

    def execute(self, command: str, args: List[str], session: Any = None) -> Any:
        """
        Exécute une commande enregistrée.
        
        Parameters
        ----------
        command : str
            Nom de la commande
        args : List[str]
            Arguments à passer
        session : Any
            Objet session (pour accès au contexte)
            
        Returns
        -------
        Any
            Résultat de la commande
            
        Raises
        ------
        CommandNotFoundError
            Si la commande n'existe pas
        """
        cmd_lower = command.lower().strip()

        if cmd_lower not in self.commands:
            available = ", ".join(sorted(self.commands.keys()))
            raise CommandNotFoundError(
                f"Commande inconnue: '{cmd_lower}'\n"
                f"Commandes disponibles: {available}"
            )

        func = self.commands[cmd_lower]
        coerced = [self._coerce_arg(a) for a in args]
        return func(*coerced, session=session) if session else func(*coerced)

    @staticmethod
    def _coerce_arg(value: str):
        """Convertit un argument string en int ou float si possible, sinon le garde tel quel."""
        try:
            i = int(value)
            return i
        except (ValueError, TypeError):
            pass
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

    def get_available_commands(self) -> List[str]:
        """Retourne la liste des commandes disponibles."""
        return sorted(self.commands.keys())
