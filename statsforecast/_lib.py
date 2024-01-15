# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/src/core/lib.ipynb.

# %% auto 0
__all__ = ['Criterion', 'OptimResult']

# %% ../nbs/src/core/lib.ipynb 1
import ctypes
import platform
import sys
from enum import Enum

import numpy as np

if sys.version_info < (3, 10):
    from importlib_resources import files
else:
    from importlib.resources import files

# %% ../nbs/src/core/lib.ipynb 2
if platform.system() in ("Windows", "Microsoft"):
    _prefix = "Release"
    _extension = "dll"
else:
    _prefix = ""
    _extension = "so"

_LIB = ctypes.CDLL(
    str(files("statsforecast") / "lib" / _prefix / f"libstatsforecast.{_extension}")
)

# %% ../nbs/src/core/lib.ipynb 3
class Criterion(int, Enum):
    LIKELIHOOD = 0
    MSE = 1
    AMSE = 2
    SIGMA = 3
    MAE = 4

# %% ../nbs/src/core/lib.ipynb 4
class OptimResult(ctypes.Structure):
    _fields_ = [
        ("fun", ctypes.c_double),
        ("nit", ctypes.c_int),
    ]

# %% ../nbs/src/core/lib.ipynb 5
def _arr_as_double_ptr(arr: np.ndarray):
    if arr.dtype != np.float64:
        raise ValueError("Array does not have double type.")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
