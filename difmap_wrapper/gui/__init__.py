
import sys
import importlib


def _alias_module(name: str, attrs: dict) -> None:
    std_types = importlib.import_module("types")
    mod = std_types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


try:
    from .widgets.map_widget import CleanMapPlotWidget

    _alias_module(__name__ + ".map_widget", {"CleanMapPlotWidget": CleanMapPlotWidget})
    map_widget = sys.modules[__name__ + ".map_widget"]
except Exception:
    pass
