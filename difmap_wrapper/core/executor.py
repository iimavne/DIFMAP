from __future__ import annotations

from typing import Protocol

from .commands import (
    CleanCommand,
    DifmapCommand,
    InvertCommand,
    MapsizeCommand,
    ObserveCommand,
    RestoreCommand,
    SelectCommand,
    SelfcalCommand,
)


class SupportsDifmapSession(Protocol):
    def observe(self, filepath: str) -> None: ...

    @property
    def obs(self): ...

    @property
    def imager(self): ...


class DifmapExecutor:
    def execute(self, session: SupportsDifmapSession, cmd: DifmapCommand) -> None:
        if isinstance(cmd, ObserveCommand):
            session.observe(cmd.filepath)
            return
        if isinstance(cmd, SelectCommand):
            session.obs.select(pol=cmd.pol, ifs=cmd.ifs, channels=cmd.channels)
            return
        if isinstance(cmd, MapsizeCommand):
            session.imager.mapsize(cmd.size, cmd.cellsize, ny=cmd.ny, cellsize_y=cmd.cellsize_y)
            return
        if isinstance(cmd, InvertCommand):
            session.imager.invert(uvmin_wav=cmd.uvmin_wav, uvmax_wav=cmd.uvmax_wav, uvhwhm_pix=cmd.uvhwhm_pix)
            return
        if isinstance(cmd, CleanCommand):
            session.imager.clean(niter=cmd.niter, gain=cmd.gain, cutoff=cmd.cutoff)
            return
        if isinstance(cmd, RestoreCommand):
            session.imager.restore(beam=cmd.beam, noresid=cmd.noresid, dosm=cmd.dosm)
            return
        if isinstance(cmd, SelfcalCommand):
            session.imager.selfcal(
                doamp=cmd.doamp,
                dofloat=cmd.dofloat,
                solint=cmd.solint,
                maxamp=cmd.maxamp,
                maxphs=cmd.maxphs,
                p_mintel=cmd.p_mintel,
                a_mintel=cmd.a_mintel,
                doflag=cmd.doflag,
                clip=cmd.clip,
            )
            return

        raise TypeError(f"Commande non supportée: {type(cmd).__name__}")
