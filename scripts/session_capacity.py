#!/usr/bin/env python3
"""
Calcule combien de sessions difmap peuvent tourner en parallèle
sans saturer la mémoire RAM.

Usage:
    python session_capacity.py
    python session_capacity.py --watch          # rafraîchissement continu
    python session_capacity.py --safety 0.8     # marge de sécurité (défaut 0.75)
"""

import argparse
import multiprocessing
import os
import sys
import time

import psutil


# ─── Mesure mémoire d'un process difmap ──────────────────────────────────────

def _worker_probe(queue: multiprocessing.Queue) -> None:
    """Process fils : importe le moteur C et rapporte son empreinte mémoire."""
    try:
        import difmap_native  # noqa: F401
        rss = psutil.Process(os.getpid()).memory_info().rss
    except ImportError:
        rss = 0
    queue.put(rss)


def measure_session_memory() -> int:
    """
    Retourne l'empreinte RSS (bytes) d'un process difmap fraîchement démarré.
    Inclut Python + le moteur C natif.
    """
    q: multiprocessing.Queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_worker_probe, args=(q,))
    p.start()
    p.join(timeout=15)

    if p.exitcode != 0 or q.empty():
        # Fallback : difmap_native non chargeable ici, on mesure juste Python
        return psutil.Process(os.getpid()).memory_info().rss

    return q.get()


# ─── Données système ──────────────────────────────────────────────────────────

def get_memory_stats() -> dict:
    vm = psutil.virtual_memory()
    return {
        "total":     vm.total,
        "available": vm.available,
        "used":      vm.used,
        "percent":   vm.percent,
    }


def calculate_capacity(mem: dict, session_rss: int, safety: float = 0.75) -> dict:
    """
    Calcule le nombre maximum de sessions parallèles sans saturer la RAM.

    Parameters
    ----------
    mem         : résultat de get_memory_stats()
    session_rss : empreinte mémoire d'une session (bytes)
    safety      : fraction de la mémoire disponible utilisable (0-1)
    """
    usable    = mem["available"] * safety
    max_sess  = max(0, int(usable // session_rss)) if session_rss > 0 else 0
    used_frac = mem["percent"] / 100.0

    # Niveau de risque
    if used_frac >= 0.90:
        risk = "CRITIQUE"
        risk_color = RED
    elif used_frac >= 0.75:
        risk = "ELEVÉ"
        risk_color = YELLOW
    elif used_frac >= 0.50:
        risk = "MODÉRÉ"
        risk_color = YELLOW
    else:
        risk = "FAIBLE"
        risk_color = GREEN

    return {
        "max_sessions":  max_sess,
        "session_rss":   session_rss,
        "usable":        usable,
        "risk":          risk,
        "risk_color":    risk_color,
    }


# ─── Affichage ────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
GREY   = "\033[90m"
WHITE  = "\033[97m"

BAR_WIDTH = 40


def _bar(fraction: float, color: str) -> str:
    filled = int(fraction * BAR_WIDTH)
    filled = max(0, min(BAR_WIDTH, filled))
    return (
        "["
        + color + "█" * filled + RESET
        + GREY + "░" * (BAR_WIDTH - filled) + RESET
        + "]"
    )


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def display_report(mem: dict, cap: dict, session_rss: int) -> None:
    used_frac = mem["percent"] / 100.0

    if used_frac >= 0.75:
        ram_color = RED
    elif used_frac >= 0.50:
        ram_color = YELLOW
    else:
        ram_color = GREEN

    max_s = cap["max_sessions"]
    sess_frac = 1.0 - (max_s / max(max_s + 1, 1)) if max_s == 0 else 0.0
    if max_s == 0:
        sess_color = RED
    elif max_s <= 2:
        sess_color = YELLOW
    else:
        sess_color = GREEN

    print()
    print(f"{BOLD}{CYAN}{'─'*54}{RESET}")
    print(f"{BOLD}{CYAN}   Difmap Session Capacity — Vélocimètre mémoire{RESET}")
    print(f"{BOLD}{CYAN}{'─'*54}{RESET}")
    print()

    # RAM globale
    print(f"  {BOLD}RAM système{RESET}")
    print(f"  {_bar(used_frac, ram_color)} {mem['percent']:.1f}%")
    print(
        f"  Utilisée : {_fmt_bytes(mem['used'])} / "
        f"Dispo : {_fmt_bytes(mem['available'])} / "
        f"Total : {_fmt_bytes(mem['total'])}"
    )
    print()

    # Empreinte par session
    print(f"  {BOLD}Empreinte mémoire d'une session difmap{RESET}")
    print(f"  ≈ {_fmt_bytes(session_rss)} par processus")
    print()

    # Capacité
    max_cpu = os.cpu_count() or 1
    print(f"  {BOLD}Sessions parallèles estimées{RESET}")
    if max_s == 0:
        sess_bar = _bar(1.0, RED)
        print(f"  {sess_bar} {RED}{BOLD}0 — RAM insuffisante !{RESET}")
    else:
        bar_frac = min(1.0, max_s / max(max_cpu * 2, max_s))
        print(f"  {_bar(bar_frac, sess_color)} {sess_color}{BOLD}{max_s}{RESET} sessions max")
        print(f"  (marge de sécurité {int(cap['usable']/mem['available']*100):.0f}% de la RAM dispo)")

    print()
    print(
        f"  CPUs disponibles : {BOLD}{max_cpu}{RESET} | "
        f"Risque mémoire : {cap['risk_color']}{BOLD}{cap['risk']}{RESET}"
    )

    # Recommandation DifmapBatchManager
    print()
    print(f"  {BOLD}Recommandation DifmapBatchManager{RESET}")
    if max_s == 0:
        print(f"  {RED}Libérez de la mémoire avant de lancer un batch.{RESET}")
    else:
        safe_workers = min(max_s, max_cpu)
        print(
            f"  {GREEN}DifmapBatchManager(max_workers={safe_workers}){RESET}"
        )
        if safe_workers < max_s:
            print(
                f"  {GREY}(limité par CPU ; la RAM permettrait {max_s}){RESET}"
            )

    print(f"{BOLD}{CYAN}{'─'*54}{RESET}")
    print()


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcule le nombre max de sessions difmap parallèles."
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Rafraîchit l'affichage toutes les 2 secondes (Ctrl-C pour quitter)."
    )
    parser.add_argument(
        "--safety", type=float, default=0.75, metavar="FRAC",
        help="Fraction de la RAM disponible utilisable (défaut 0.75)."
    )
    parser.add_argument(
        "--no-probe", action="store_true",
        help="Ne pas lancer de subprocess de mesure (utilise la mémoire Python courante)."
    )
    args = parser.parse_args()

    safety = max(0.1, min(1.0, args.safety))

    print(f"{GREY}Mesure de l'empreinte mémoire d'une session difmap…{RESET}", flush=True)

    if args.no_probe:
        session_rss = psutil.Process(os.getpid()).memory_info().rss
    else:
        session_rss = measure_session_memory()

    if args.watch:
        try:
            while True:
                # Efface l'écran (compatible Linux/macOS)
                os.system("clear")
                mem = get_memory_stats()
                cap = calculate_capacity(mem, session_rss, safety)
                display_report(mem, cap, session_rss)
                print(f"  {GREY}Actualisation dans 2 s — Ctrl-C pour quitter{RESET}\n")
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n  Arrêt.")
    else:
        mem = get_memory_stats()
        cap = calculate_capacity(mem, session_rss, safety)
        display_report(mem, cap, session_rss)


if __name__ == "__main__":
    main()
