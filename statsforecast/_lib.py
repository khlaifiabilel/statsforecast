# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/src/core/lib.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/src/core/lib.ipynb 1
import ctypes
import platform
import sys

import numpy as np

# %% ../nbs/src/core/lib.ipynb 2
def _data_as_double_ptr(x):
    x = np.asarray(x, dtype=np.float64)
    return x.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

def _data_as_int_ptr(x):
    x = np.asarray(x, dtype=np.intc)
    return x.ctypes.data_as(ctypes.POINTER(ctypes.c_int))

if sys.version_info < (3, 10):
    from importlib_resources import files
else:
    from importlib.resources import files

if platform.system() in ("Windows", "Microsoft"):
    _prefix = "Release"
    _extension = "dll"
else:
    _prefix = ""
    _extension = "so"

_LIB = ctypes.CDLL(
    str(files("statsforecast") / "lib" / _prefix / f"libstatsforecast.{_extension}")
