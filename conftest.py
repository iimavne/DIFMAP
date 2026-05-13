import pytest


@pytest.fixture(autouse=True)
def _reset_native_state():
    try:
        import difmap_native
        difmap_native.cleanup()
    except Exception:
        pass

    yield

    try:
        import difmap_native
        difmap_native.cleanup()
    except Exception:
        pass
