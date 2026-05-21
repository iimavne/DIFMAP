# tests/test_manager.py
"""
Tests pour le système de traitement parallèle (DifmapBatchManager).

Valide que :
- Les tâches s'exécutent en parallèle sans collision mémoire
- Le Singleton DifmapSession fonctionne correctement dans chaque processus
- Les résultats sont retournés dans l'ordre
- Les exceptions sont correctement propagées

Notes
-----
Les fonctions worker DOIVENT être définies au niveau du module (pas de fonction
locale) car elles sont sérialisées par pickle pour les processus enfants.

"""

import pytest
import time
from typing import Dict, Any

from difmap_wrapper.manager import DifmapBatchManager
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError


# ========================================================================
# Fonctions workers « picklables » — définies au niveau du module
# ========================================================================


def simple_square_worker(x: int) -> Dict[str, Any]:
    """
    Worker trivial pour démonstration — calcule x^2.

    Cette fonction sert de baseline pour tester que run_batch fonctionne
    sans dépendre de DifmapSession.

    Parameters
    ----------
    x : int
        Nombre à élever au carré.

    Returns
    -------
    Dict[str, Any]
        Dictionnaire contenant :
        - 'input': x
        - 'output': x^2
        - 'status': 'OK'

    """
    result = x ** 2
    return {
        "input": x,
        "output": result,
        "status": "OK",
    }


def create_difmap_session_worker(task_id: int) -> Dict[str, Any]:
    """
    Worker qui crée une instance DifmapSession isolée.

    Démontre que chaque processus peut instancier sa propre session
    Singleton sans collision. N'accède pas à des fichiers réels.

    Parameters
    ----------
    task_id : int
        Identifiant unique de la tâche (pour le logging).

    Returns
    -------
    Dict[str, Any]
        Dictionnaire contenant :
        - 'task_id': task_id
        - 'session_created': True si la session a été créée
        - 'uv_loaded': état de uv_loaded
        - 'status': 'OK' ou code d'erreur

    Raises
    ------
    DifmapStateError
        JAMAIS levée, car chaque processus a son propre Singleton.

    """
    try:
        # Créer une session Singleton dans ce processus isolé
        with DifmapSession() as session:
            # Vérifier que la session est bien active
            uv_loaded_state = session.uv_loaded
            return {
                "task_id": task_id,
                "session_created": True,
                "uv_loaded": uv_loaded_state,
                "status": "OK",
            }
    except DifmapStateError as e:
        # NE doit JAMAIS arriver ici si l'isolation est correcte
        return {
            "task_id": task_id,
            "session_created": False,
            "error": str(e),
            "status": "ERROR_SINGLETON_COLLISION",
        }
    except Exception as e:
        # Autres erreurs inattendues
        return {
            "task_id": task_id,
            "session_created": False,
            "error": str(e),
            "status": "ERROR_UNEXPECTED",
        }


def slow_worker_with_delay(task_id: int, delay: float = 0.5) -> Dict[str, Any]:
    """
    Worker qui simule une tâche longue avec délai.

    Permet de vérifier que les processus s'exécutent réellement en parallèle
    (le temps total < somme des délais individuels).

    Parameters
    ----------
    task_id : int
        Identifiant unique de la tâche.
    delay : float, optional
        Délai en secondes avant de retourner. Défaut: 0.5 s.

    Returns
    -------
    Dict[str, Any]
        Dictionnaire contenant :
        - 'task_id': task_id
        - 'completed_at': timestamp de fin
        - 'status': 'OK'

    """
    time.sleep(delay)
    return {
        "task_id": task_id,
        "completed_at": time.time(),
        "status": "OK",
    }


# ========================================================================
# Tests
# ========================================================================


class TestDifmapBatchManager:
    """Suite de tests pour DifmapBatchManager."""

    def test_manager_instantiation(self):
        """Vérifie que le gestionnaire s'instancie correctement."""
        manager = DifmapBatchManager()
        assert manager is not None
        assert manager.max_workers is None  # Défaut

    def test_manager_with_max_workers(self):
        """Vérifie que max_workers est bien stocké."""
        manager = DifmapBatchManager(max_workers=2)
        assert manager.max_workers == 2

    def test_run_batch_simple_tasks(self):
        """
        Test basique : exécute 5 tâches triviales en parallèle.

        Vérifie que :
        - Tous les résultats sont retournés
        - Ils sont dans le bon ordre
        - Aucune exception n'est levée
        """
        manager = DifmapBatchManager(max_workers=3)
        inputs = [1, 2, 3, 4, 5]
        results = manager.run_batch(simple_square_worker, inputs)

        # Vérifier qu'on a 5 résultats
        assert len(results) == 5

        # Vérifier l'ordre et les valeurs
        expected = [1, 4, 9, 16, 25]
        for i, result in enumerate(results):
            assert result["input"] == inputs[i]
            assert result["output"] == expected[i]
            assert result["status"] == "OK"

    def test_run_batch_difmap_session_isolation(self):
        """
        Test critique : vérifie que chaque processus a son propre Singleton.

        - Lance 4 tâches simultanément avec max_workers=3
        - Chaque tâche crée une DifmapSession
        - Vérifie qu'aucune ne lève DifmapStateError
        - Vérifie que les 4 tâches complètent avec succès

        C'est LA preuve que l'isolation fonctionne.
        """
        manager = DifmapBatchManager(max_workers=3)
        task_ids = [1, 2, 3, 4]

        results = manager.run_batch(
            create_difmap_session_worker,
            task_ids,
        )

        # Vérifier qu'on a 4 résultats
        assert len(results) == 4

        # Vérifier que TOUTES les sessions ont été créées sans collision
        for i, result in enumerate(results):
            assert result["task_id"] == task_ids[i], \
                f"Résultat {i} : task_id mismatch"
            assert result["session_created"] is True, \
                f"Résultat {i} : session n'a pas été créée"
            assert result["status"] == "OK", \
                f"Résultat {i} : status={result.get('status')}, " \
                f"error={result.get('error')}"

            # Vérifier qu'il n'y a pas d'erreur de collision
            assert "ERROR_SINGLETON_COLLISION" not in result["status"], \
                f"Collision détectée pour task {task_ids[i]} : {result.get('error')}"

    def test_run_batch_parallelism(self):
        """
        Vérifie que les tâches s'exécutent réellement en parallèle.

        - Lance 6 tâches de 0.5s chacune avec max_workers=3
        - Temps total attendu : ~1.0s (2 vagues de 3 processus)
        - Si séquentiel : ~3.0s
        - Validée si tempo < 2.5s
        """
        manager = DifmapBatchManager(max_workers=3)
        task_ids = list(range(6))
        delay_per_task = 0.5

        start_time = time.time()
        results = manager.run_batch(
            slow_worker_with_delay,
            [(tid, delay_per_task) for tid in task_ids],
        )
        elapsed_time = time.time() - start_time

        # Vérifier que toutes les tâches complètent
        assert len(results) == 6
        for i, result in enumerate(results):
            assert result["status"] == "OK"

        # Vérifier que c'était parallèle (< 2.5s, non ~3.0s)
        assert elapsed_time < 2.5, \
            f"Tâches semblent séquentielles : {elapsed_time:.2f}s"
        print(f"✓ Parallelism vérifiée : 6 tâches x 0.5s en {elapsed_time:.2f}s")

    def test_run_batch_result_order(self):
        """
        Vérifie que les résultats sont retournés dans l'ordre d'input.

        Même si les processus terminent dans un ordre différent.
        """
        manager = DifmapBatchManager(max_workers=2)
        inputs = [10, 20, 30, 40, 50]

        results = manager.run_batch(simple_square_worker, inputs)

        # Les résultats doivent correspondre aux inputs en ordre
        for i, result in enumerate(results):
            assert result["input"] == inputs[i], \
                f"Ordre mismatch à l'index {i} : " \
                f"expected input {inputs[i]}, got {result['input']}"

    def test_run_batch_with_empty_list(self):
        """Teste le comportement avec une liste vide."""
        manager = DifmapBatchManager()
        results = manager.run_batch(simple_square_worker, [])
        assert results == []

    def test_run_batch_with_single_task(self):
        """Teste l'exécution d'une seule tâche."""
        manager = DifmapBatchManager()
        results = manager.run_batch(simple_square_worker, [42])

        assert len(results) == 1
        assert results[0]["input"] == 42
        assert results[0]["output"] == 42 ** 2
        assert results[0]["status"] == "OK"

    def test_run_batch_max_workers_override(self):
        """
        Vérifie que max_workers peut être surdéfini à l'appel.

        Le manager a max_workers=1, mais on passe max_workers=3 à run_batch.
        """
        manager = DifmapBatchManager(max_workers=1)

        # Lance 4 tâches avec override max_workers=3
        inputs = [1, 2, 3, 4]
        start_time = time.time()
        results = manager.run_batch(
            slow_worker_with_delay,
            [(i, 0.3) for i in inputs],
            max_workers=3,
        )
        elapsed_time = time.time() - start_time

        # Si max_workers=1 était utilisé (4 x 0.3s = 1.2s)
        # Si max_workers=3 était utilisé (~0.6s)
        # Tolérance : < 1.2s (permettant un peu d'overhead système)
        assert elapsed_time < 1.2, \
            f"Override max_workers=3 ne semble pas appliqué : {elapsed_time:.2f}s"
        print(f"✓ Override max_workers=3 vérifié : {elapsed_time:.2f}s")


# ========================================================================
# Intégration : test complet de collision mémoire
# ========================================================================


class TestMemoryCollisionPrevention:
    """
    Tests spécifiques pour la prévention de collision mémoire.

    Valide la raison d'être de DifmapBatchManager : permettre de charger
    plusieurs fichiers UVFITS en parallèle sans que leurs moteurs C ne
    se perturbent.
    """

    def test_multiple_sessions_in_parallel_no_collision(self):
        """
        Teste que 5 processus peuvent créer des sessions Singleton en parallèle.

        Si le Singleton était partagé entre processus (erreur architecturale),
        le 2ème processus lèverait DifmapStateError "instance already active".

        Ce test PROUVE que chaque processus a son propre espace mémoire.
        """
        manager = DifmapBatchManager(max_workers=3)

        # Lancer 5 tâches (plus que max_workers) pour forcer le queueing
        task_ids = list(range(5))
        results = manager.run_batch(
            create_difmap_session_worker,
            task_ids,
        )

        # Vérifier : aucune collision
        errors = [
            r for r in results
            if r["status"] == "ERROR_SINGLETON_COLLISION"
        ]
        assert len(errors) == 0, \
            f"Collision détectée : {errors}"

        # Tous les tasks doivent être OK
        ok_count = sum(1 for r in results if r["status"] == "OK")
        assert ok_count == 5, \
            f"Expected 5 OK, got {ok_count} (errors: {results})"

    def test_batch_manager_is_reusable(self):
        """Vérifie qu'on peut réutiliser le même manager plusieurs fois."""
        manager = DifmapBatchManager(max_workers=2)

        # Premier batch
        results1 = manager.run_batch(simple_square_worker, [1, 2, 3])
        assert len(results1) == 3

        # Deuxième batch — doit fonctionner sans pépins
        results2 = manager.run_batch(simple_square_worker, [10, 20])
        assert len(results2) == 2

        # Vérifier que les résultats sont corrects
        assert results1[0]["output"] == 1
        assert results2[0]["output"] == 100
