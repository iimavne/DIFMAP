# difmap_wrapper/manager.py
"""
Gestionnaire de traitement parallèle pour Difmap.

Permet l'exécution de tâches indépendantes (batch processing) sur plusieurs
processus OS distincts. Chaque processus dispose de son propre espace mémoire
et de sa propre instance DifmapSession, éliminant les collisions dues aux
variables globales du moteur C.

Ce module utilise ``concurrent.futures.ProcessPoolExecutor`` pour gérer
l'orchestration des processus workers.

Examples
--------
Traitement batch de fichiers FITS :

    >>> from difmap_wrapper.manager import DifmapBatchManager
    >>> from difmap_wrapper.session import DifmapSession
    >>>
    >>> def process_fits_file(filepath, pol="RR"):
    ...     '''Worker function : doit être au niveau du module (picklable).'''
    ...     with DifmapSession() as session:
    ...         session.observe(filepath)
    ...         session.obs.select(pol=pol)
    ...         data = session.obs.get_data()
    ...         return {
    ...             'file': filepath,
    ...             'n_visibilities': len(data['amp']),
    ...             'mean_amplitude': float(data['amp'].mean()),
    ...             'status': 'OK'
    ...         }
    >>>
    >>> manager = DifmapBatchManager()
    >>> files = ["data/source1.fits", "data/source2.fits", "data/source3.fits"]
    >>> results = manager.run_batch(process_fits_file, files, max_workers=2)
    >>> for res in results:
    ...     print(f"{res['file']}: {res['mean_amplitude']:.3f} Jy")
    data/source1.fits: 0.312 Jy
    data/source2.fits: 0.287 Jy
    data/source3.fits: 0.401 Jy

Notes
-----
- La fonction worker passée à ``run_batch`` **DOIT** être définie au niveau
  du module (pas de fonction locale ou lambda) pour être sérialisable.
- Chaque worker s'exécute dans un processus séparé avec sa propre instance
  de Singleton DifmapSession.
- Les résultats sont retournés dans l'ordre d'exécution (liste).
- Les exceptions levées dans les workers sont propagées lors de l'itération
  sur les futures.

"""

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Any, Optional, Iterable, Sequence
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker module-level pour run_command_batch (picklable par multiprocessing)
# ---------------------------------------------------------------------------

def _command_batch_worker(job: "tuple[list, Any]") -> dict:
    """
    Worker module-level pour run_command_batch.

    Exécute une séquence de DifmapCommand dans un processus isolé et retourne
    le résultat ainsi que l'historique sérialisé pour traçabilité.

    Parameters
    ----------
    job : tuple
        (commands, user_payload) où commands est une liste de DifmapCommand
        et user_payload est une valeur quelconque renvoyée telle quelle.
    """
    from difmap_wrapper.core.session import DifmapSession
    from difmap_wrapper.core.executor import DifmapExecutor
    from difmap_wrapper.core.history import CommandHistory

    commands, user_payload = job
    history = CommandHistory()
    executor = DifmapExecutor()
    errors = []

    with DifmapSession() as session:
        for cmd in commands:
            try:
                executor.execute(session, cmd)
                history.add(cmd)
            except Exception as exc:
                errors.append({"command": repr(cmd), "error": str(exc)})
                break

    return {
        "payload": user_payload,
        "history": history.to_dicts(),
        "errors": errors,
        "status": "ERROR" if errors else "OK",
    }


class DifmapBatchManager:
    """
    Orchestrateur de traitement parallèle pour Difmap.

    Gère l'exécution de tâches indépendantes sur un pool de processus OS,
    en évitant les collisions mémoire dues aux variables globales du moteur C.

    Attributes
    ----------
    max_workers : int, optional
        Nombre maximal de processus parallèles. Si None (défaut),
        égal au nombre de CPUs disponibles.

    Examples
    --------
    Instanciation et traitement simple :

        >>> manager = DifmapBatchManager(max_workers=4)
        >>> results = manager.run_batch(my_worker_func, range(10))
        >>> for res in results:
        ...     print(res)

    Traitement avec observation d'exécution :

        >>> manager = DifmapBatchManager()
        >>> args = [("file1.fits", "RR"), ("file2.fits", "LL"), ...]
        >>> results = manager.run_batch(
        ...     process_with_pol,
        ...     args,
        ...     max_workers=2
        ... )

    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialise le gestionnaire de batch.

        Parameters
        ----------
        max_workers : int, optional
            Nombre maximal de processus workers. Si None, utilise
            le nombre de CPUs détectés par le système.

        """
        self.max_workers = max_workers
        logger.debug(
            f"DifmapBatchManager initialisé avec max_workers={max_workers}"
        )

    def run_batch(
        self,
        worker_func: Callable,
        arguments: Iterable[Any],
        max_workers: Optional[int] = None,
    ) -> List[Any]:
        """
        Exécute une fonction worker sur une liste d'arguments en parallèle.

        Distribue les tâches à un pool de processus OS. Chaque processus
        s'exécute de manière isolée avec sa propre mémoire et sa propre
        instance DifmapSession Singleton.

        Parameters
        ----------
        worker_func : Callable
            Fonction à exécuter dans chaque processus. **DOIT** être
            définie au niveau du module (non locale, non lambda) pour
            être sérialisable par pickle.

            La signature typique est::

                def worker_func(arg: Any) -> Any:
                    '''Traite arg et retourne un résultat.'''
                    with DifmapSession() as session:
                        # ... traitement ...
                        return result

        arguments : Iterable[Any]
            Itérable d'arguments à passer au worker. Chaque argument
            sera passé à ``worker_func()`` dans un processus séparé.
            Peut être une liste, un tuple, un générateur, etc.

            Examples : ``[file1, file2, file3]``, ``[(file, pol), ...]``

        max_workers : int, optional
            Nombre maximal de workers parallèles. Si None, utilise
            la valeur stockée dans ``self.max_workers`` (ou le nombre
            de CPUs si celle-ci est aussi None).

        Returns
        -------
        List[Any]
            Liste des résultats retournés par le worker pour chaque
            argument, dans le même ordre que les arguments d'entrée.

        Raises
        ------
        Exception
            Toute exception levée dans un worker est propagée lors
            de l'accès au résultat. Utilisez un bloc try/except pour
            gérer les erreurs par worker.

        Examples
        --------
        Cas basique avec une liste d'entiers :

            >>> def square(x):
            ...     return x ** 2
            >>> manager = DifmapBatchManager()
            >>> results = manager.run_batch(square, [1, 2, 3, 4, 5])
            >>> print(results)
            [1, 4, 9, 16, 25]

        Cas réaliste avec fichiers FITS :

            >>> def process_fits(filepath):
            ...     with DifmapSession() as session:
            ...         session.observe(filepath)
            ...         session.obs.select(pol="RR")
            ...         data = session.obs.get_data()
            ...         return {
            ...             'file': filepath,
            ...             'n_vis': len(data['amp']),
            ...             'mean_amp': float(data['amp'].mean())
            ...         }
            >>> manager = DifmapBatchManager(max_workers=3)
            >>> files = ["a.fits", "b.fits", "c.fits", "d.fits"]
            >>> results = manager.run_batch(process_fits, files)
            >>> for res in results:
            ...     print(f"{res['file']}: {res['mean_amp']:.3f} Jy")

        Cas avec arguments tuples :

            >>> def process_with_pol(arg):
            ...     filepath, pol = arg
            ...     with DifmapSession() as session:
            ...         session.observe(filepath)
            ...         session.obs.select(pol=pol)
            ...         return len(session.obs.get_data()['amp'])
            >>> args = [("f1.fits", "RR"), ("f2.fits", "LL")]
            >>> manager = DifmapBatchManager()
            >>> sizes = manager.run_batch(process_with_pol, args)
            >>> print(sizes)
            [1024, 2048]

        Notes
        -----
        - La fonction worker doit être **picklable** : définie au niveau
          du module, pas comme fonction locale ou lambda complexe.
        - Les résultats sont retournés dans l'ordre d'input, même si
          les processus terminent dans un ordre différent.
        - Pour les tâches longues, utilisez ``max_workers`` < nombre de CPUs
          pour éviter la surcharge système.

        """
        # Vérifier que worker_func est picklable (top-level) avant toute soumission.
        # Les lambdas et fonctions locales ont respectivement '<lambda>' ou '<locals>'
        # dans __qualname__ et déclenchent une PicklingError cryptique au spawn.
        qualname = getattr(worker_func, '__qualname__', '')
        if '<lambda>' in qualname:
            raise TypeError(
                "worker_func ne peut pas être une fonction lambda : les lambdas "
                "ne sont pas sérialisables par pickle entre processus.\n"
                "→ Définissez une fonction nommée au niveau du module."
            )
        if '<locals>' in qualname:
            raise TypeError(
                f"worker_func '{qualname}' est une fonction locale (définie à l'intérieur "
                "d'une autre fonction) et ne peut pas être sérialisée entre processus.\n"
                "→ Déplacez la fonction au niveau du module."
            )

        # Déterminer le nombre de workers à utiliser
        workers = max_workers or self.max_workers
        logger.info(
            f"Démarrage du batch avec worker_func={worker_func.__name__}, "
            f"max_workers={workers}"
        )

        # Convertir arguments en liste si nécessaire (pour conserver l'ordre)
        args_list = list(arguments)
        results = [None] * len(args_list)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Soumettre toutes les tâches et garder trace du mapping
            # future -> index
            future_to_index = {
                executor.submit(worker_func, arg): idx
                for idx, arg in enumerate(args_list)
            }

            # Récupérer les résultats au fur et à mesure
            completed_count = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                    completed_count += 1
                    logger.debug(
                        f"Task {idx + 1}/{len(args_list)} complétée "
                        f"({completed_count}/{len(args_list)})"
                    )
                except Exception as e:
                    logger.error(
                        f"Task {idx + 1}/{len(args_list)} a échoué : {e}"
                    )
                    raise

        logger.info(f"Batch terminé : {len(args_list)} tâche(s) complétée(s)")
        return results

    def run_command_batch(
        self,
        jobs: Iterable[tuple[Sequence, Any]],
        max_workers: Optional[int] = None,
    ) -> List[dict]:
        """
        Exécute plusieurs pipelines de commandes en parallèle.

        Chaque « job » est un couple ``(commands, payload)`` :
        - ``commands`` : séquence de ``DifmapCommand`` picklables (voir ``commands.py``)
        - ``payload``  : valeur libre retournée telle quelle dans le résultat
          (typiquement un chemin de fichier ou un identifiant de tâche).

        Parameters
        ----------
        jobs : Iterable[tuple[Sequence[DifmapCommand], Any]]
            Itérable de couples (commands, payload).
        max_workers : int, optional
            Surcharge du nombre de workers (défaut : ``self.max_workers``).

        Returns
        -------
        List[dict]
            Une entrée par job :
            - ``'payload'``  : le payload fourni
            - ``'history'``  : liste de dicts des commandes exécutées
            - ``'errors'``   : liste d'éventuelles erreurs (vide si OK)
            - ``'status'``   : ``'OK'`` ou ``'ERROR'``

        Examples
        --------
        >>> from difmap_wrapper import ObserveCommand, SelectCommand, MapsizeCommand, InvertCommand
        >>> jobs = [
        ...     ([ObserveCommand("a.fits"), SelectCommand(), MapsizeCommand(256, 0.5), InvertCommand()], "a.fits"),
        ...     ([ObserveCommand("b.fits"), SelectCommand(), MapsizeCommand(256, 0.5), InvertCommand()], "b.fits"),
        ... ]
        >>> manager = DifmapBatchManager(max_workers=2)
        >>> results = manager.run_command_batch(jobs)
        >>> for r in results:
        ...     print(r['payload'], r['status'], len(r['history']), 'cmds')
        """
        return self.run_batch(
            _command_batch_worker,
            list(jobs),
            max_workers=max_workers,
        )
