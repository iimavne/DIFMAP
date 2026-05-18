from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..types import Polarization


@dataclass(frozen=True, slots=True)
class ObserveCommand:
    filepath: str


@dataclass(frozen=True, slots=True)
class SelectCommand:
    pol: Polarization = "I"
    ifs: tuple[int, int] = (1, 0)
    channels: tuple[int, int] = (1, 0)


@dataclass(frozen=True, slots=True)
class MapsizeCommand:
    size: int
    cellsize: float
    ny: int = 0
    cellsize_y: float = 0.0


@dataclass(frozen=True, slots=True)
class InvertCommand:
    # Units: wavelengths (λ), NOT Mλ.  Convert with `value_Mlambda * 1e6`.
    # native_uvrange() receives λ directly and stores them without uvtowav().
    uvmin_wav: float = 0.0
    uvmax_wav: float = 0.0
    uvhwhm_pix: float = 0.0


@dataclass(frozen=True, slots=True)
class CleanCommand:
    niter: int = 100
    gain: float = 0.05
    cutoff: float = 0.0


@dataclass(frozen=True, slots=True)
class RestoreCommand:
    beam: tuple[float, float, float] | None = None
    noresid: bool = False
    dosm: bool = True


@dataclass(frozen=True, slots=True)
class SelfcalCommand:
    doamp: bool = False
    dofloat: bool = False
    solint: float = 0.0
    maxamp: float = 0.0
    maxphs: float = 0.0
    p_mintel: int = 3
    a_mintel: int = 4
    doflag: bool = True
    clip: bool = False


DifmapCommand = (
    ObserveCommand
    | SelectCommand
    | MapsizeCommand
    | InvertCommand
    | CleanCommand
    | RestoreCommand
    | SelfcalCommand
)


MapType = Literal["dirty", "residual", "clean"]
