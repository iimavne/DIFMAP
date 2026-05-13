import pickle

import pytest

from difmap_wrapper import (
    CleanCommand,
    DifmapSession,
    InvertCommand,
    MapsizeCommand,
    ObserveCommand,
    RestoreCommand,
    SelectCommand,
    SelfcalCommand,
)


def test_commands_are_picklable():
    cmds = [
        ObserveCommand("tests/test_data/0003-066_X.SPLIT.1"),
        SelectCommand(pol="RR"),
        MapsizeCommand(size=256, cellsize=0.5),
        InvertCommand(uvmin_wav=0.0, uvmax_wav=0.0, uvhwhm_pix=0.0),
        CleanCommand(niter=5, gain=0.1, cutoff=0.0),
        RestoreCommand(beam=None),
        SelfcalCommand(solint=0.0),
    ]
    blob = pickle.dumps(cmds)
    restored = pickle.loads(blob)
    assert restored == cmds


@pytest.mark.parametrize(
    "uvfile",
    [
        "tests/test_data/0003-066_X.SPLIT.1",
    ],
)
def test_execute_and_replay_workflow(uvfile):
    cmds = [
        ObserveCommand(uvfile),
        SelectCommand(pol="RR"),
        MapsizeCommand(size=256, cellsize=0.5),
        InvertCommand(),
    ]

    with DifmapSession() as s1:
        for c in cmds:
            s1.execute(c)
        img1 = s1.imager.get_map().copy()

    with DifmapSession() as s2:
        s2.replay(cmds)
        img2 = s2.imager.get_map().copy()

    assert img1.shape == img2.shape
    assert img1.size == img2.size
