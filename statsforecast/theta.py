# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/src/theta.ipynb.

# %% auto 0
__all__ = ['theta_target_fn', 'is_constant']

# %% ../nbs/src/theta.ipynb 1
import math
from typing import Tuple

import numpy as np
from numba import njit
from scipy.stats import norm
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf

from .utils import _seasonal_naive, _repeat_val_seas, CACHE, NOGIL, results

# %% ../nbs/src/theta.ipynb 4
# Global variables
STM = 0
OTM = 1
DSTM = 2
DOTM = 3
TOL = 1.0e-10
HUGEN = 1.0e10
NA = -99999.0
smalno = np.finfo(float).eps

# %% ../nbs/src/theta.ipynb 6
@njit(nogil=NOGIL, cache=CACHE)
def initstate(y, modeltype, initial_smoothed, alpha, theta):
    states = np.zeros((1, 5), dtype=np.float32)
    states[0, 0] = alpha * y[0] + (1 - alpha) * initial_smoothed  # level
    states[0, 1] = y[0]  # mean y
    if modeltype in [DSTM, DOTM]:
        # dynamic models
        states[0, 2] = y[0]  # An
        states[0, 3] = 0  # Bn
        states[0, 4] = y[0]  # mu
    else:
        # nodynamic models
        n = len(y)
        Bn = (
            6
            * (2 * np.mean(np.arange(1, n + 1) * y) - (1 + n) * np.mean(y))
            / (n**2 - 1)
        )
        An = np.mean(y) - (n + 1) * Bn / 2
        states[0, 2] = An
        states[0, 3] = Bn
        states[0, 4] = initial_smoothed + (1 - 1 / theta) * (An + Bn)

    return states

# %% ../nbs/src/theta.ipynb 8
@njit(nogil=NOGIL, cache=CACHE)
def thetacalc(
    y: np.ndarray,
    states: np.ndarray,  # states
    modeltype: int,
    initial_smoothed: float,
    alpha: float,
    theta: float,
    e: np.ndarray,
    amse: np.ndarray,
    nmse: int,
) -> float:
    denom = np.zeros(nmse)
    f = np.zeros(nmse)
    # update first state
    states[0, :] = initstate(
        y=y,
        modeltype=modeltype,
        initial_smoothed=initial_smoothed,
        alpha=alpha,
        theta=theta,
    )

    amse[:nmse] = 0.0
    e[0] = y[0] - states[0, 4]
    n = len(y)
    for i in range(1, n):
        # one step forecast
        thetafcst(
            states=states,
            i=i,
            modeltype=modeltype,
            f=f,
            h=nmse,
            alpha=alpha,
            theta=theta,
        )
        if math.fabs(f[0] - NA) < TOL:
            mse = NA
            return mse
        e[i] = y[i] - f[0]
        for j in range(nmse):
            if (i + j) < n:
                denom[j] += 1.0
                tmp = y[i + j] - f[j]
                amse[j] = (amse[j] * (denom[j] - 1.0) + (tmp * tmp)) / denom[j]
        # update state
        thetaupdate(
            states=states,
            i=i,
            modeltype=modeltype,
            alpha=alpha,
            theta=theta,
            y=y[i],
            usemu=0,
        )
    mean_y = np.mean(np.abs(y))
    if math.fabs(mean_y - 0.0) < TOL:
        mean_y = TOL
    mse = np.sum(e[3:] ** 2) / mean_y
    return mse

# %% ../nbs/src/theta.ipynb 9
@njit(nogil=NOGIL, cache=CACHE)
def thetafcst(states, i, modeltype, f, h, alpha, theta):
    # obs:
    # forecast are obtained in a recursive manner
    # this is not standard, for example in ets
    # forecasts
    new_states = np.zeros((i + h, states.shape[1]), dtype=np.float32)
    new_states[:i] = states[:i]
    for i_h in range(h):
        thetaupdate(
            states=new_states,
            i=i + i_h,
            modeltype=modeltype,
            alpha=alpha,
            theta=theta,
            y=0,
            usemu=1,
        )
        f[i_h] = new_states[i + i_h, 4]  # mu is the forecast

# %% ../nbs/src/theta.ipynb 10
@njit(nogil=NOGIL, cache=CACHE)
def thetaupdate(states, i, modeltype, alpha, theta, y, usemu):  # kind of model
    # states
    # level, meany, An, Bn, mu
    # get params
    level = states[i - 1, 0]
    meany = states[i - 1, 1]
    An = states[i - 1, 2]
    Bn = states[i - 1, 3]
    # update mu
    states[i, 4] = level + (1 - 1 / theta) * (
        An * ((1 - alpha) ** i) + Bn * (1 - (1 - alpha) ** (i + 1)) / alpha
    )
    if usemu:
        y = states[i, 4]
    # update level
    states[i, 0] = alpha * y + (1 - alpha) * level
    # update meany
    states[i, 1] = (i * meany + y) / (i + 1)
    # update Bn and An
    if modeltype in [DSTM, DOTM]:
        # dynamic models
        states[i, 3] = ((i - 1) * Bn + 6 * (y - meany) / (i + 1)) / (i + 2)
        states[i, 2] = states[i, 1] - states[i, 3] * (i + 2) / 2
    else:
        states[i, 2] = An
        states[i, 3] = Bn

# %% ../nbs/src/theta.ipynb 11
@njit(nogil=NOGIL, cache=CACHE)
def thetaforecast(states, n, modeltype, f, h, alpha, theta):
    # compute forecasts
    new_states = thetafcst(
        states=states, i=n, modeltype=modeltype, f=f, h=h, alpha=alpha, theta=theta
    )
    return new_states

# %% ../nbs/src/theta.ipynb 16
@njit(nogil=NOGIL, cache=CACHE)
def initparamtheta(
    initial_smoothed: float, alpha: float, theta: float, y: np.ndarray, modeltype: str
):
    if modeltype in ["STM", "DSTM"]:
        if np.isnan(initial_smoothed):
            initial_smoothed = y[0] / 2
            optimize_level = 1
        else:
            optimize_level = 0
        if np.isnan(alpha):
            alpha = 0.5
            optimize_alpha = 1
        else:
            optimize_alpha = 0
        theta = 2.0  # no optimize
        optimize_theta = 0
    elif modeltype in ["OTM", "DOTM"]:
        if np.isnan(initial_smoothed):
            initial_smoothed = y[0] / 2
            optimize_level = 1
        else:
            optimize_level = 0
        if np.isnan(alpha):
            alpha = 0.5
            optimize_alpha = 1
        else:
            optimize_alpha = 0
        if np.isnan(theta):
            theta = 2.0
            optimize_theta = 1
        else:
            optimize_theta = 0
    return {
        "initial_smoothed": initial_smoothed,
        "optimize_initial_smoothed": optimize_level,
        "alpha": alpha,
        "optimize_alpha": optimize_alpha,
        "theta": theta,
        "optimize_theta": optimize_theta,
    }

# %% ../nbs/src/theta.ipynb 18
@njit(nogil=NOGIL, cache=CACHE)
def switch_theta(x: str):
    return {"STM": 0, "OTM": 1, "DSTM": 2, "DOTM": 3}[x]

# %% ../nbs/src/theta.ipynb 20
@njit(nogil=NOGIL, cache=CACHE)
def pegelsresid_theta(
    y: np.ndarray,
    modeltype: str,
    initial_smoothed: float,
    alpha: float,
    theta: float,
    nmse: int,
):
    states = np.zeros((len(y), 5), dtype=np.float32)
    e = np.full_like(y, fill_value=np.nan)
    amse = np.full(nmse, fill_value=np.nan)
    mse = thetacalc(
        y=y,
        states=states,
        modeltype=switch_theta(modeltype),
        initial_smoothed=initial_smoothed,
        alpha=alpha,
        theta=theta,
        e=e,
        amse=amse,
        nmse=nmse,
    )
    if not np.isnan(mse):
        if np.abs(mse + 99999) < 1e-7:
            mse = np.nan
    return amse, e, states, mse

# %% ../nbs/src/theta.ipynb 21
@njit(nogil=NOGIL, cache=CACHE)
def theta_target_fn(
    optimal_param,
    init_level,
    init_alpha,
    init_theta,
    opt_level,
    opt_alpha,
    opt_theta,
    y,
    modeltype,
    nmse,
):
    states = np.zeros((len(y), 5), dtype=np.float32)
    j = 0
    if opt_level:
        level = optimal_param[j]
        j += 1
    else:
        level = init_level

    if opt_alpha:
        alpha = optimal_param[j]
        j += 1
    else:
        alpha = init_alpha

    if opt_theta:
        theta = optimal_param[j]
        j += 1
    else:
        theta = init_theta

    e = np.full_like(y, fill_value=np.nan)
    amse = np.full(nmse, fill_value=np.nan)
    mse = thetacalc(
        y=y,
        states=states,
        modeltype=switch_theta(modeltype),
        initial_smoothed=level,
        alpha=alpha,
        theta=theta,
        e=e,
        amse=amse,
        nmse=nmse,
    )
    if mse < -1e10:
        mse = -1e10
    if math.isnan(mse):
        mse = -np.inf
    if math.fabs(mse + 99999) < 1e-7:
        mse = -np.inf
    return mse

# %% ../nbs/src/theta.ipynb 22
@njit(nogil=NOGIL, cache=CACHE)
def nelder_mead_theta(
    x0: np.ndarray,
    args: Tuple = (),
    lower: np.ndarray = np.empty(0),
    upper: np.ndarray = np.empty(0),
    init_step: float = 0.05,
    zero_pert: float = 0.0001,
    alpha: float = 1.0,
    gamma: float = 2.0,
    rho: float = 0.5,
    sigma: float = 0.5,
    max_iter: int = 2_000,
    tol_std: float = 1e-10,
    adaptive: bool = False,
):
    # We are trying to minimize the function fn(x, args)
    # with initial point x0.
    # Step 0:
    # get x1, ..., x_{n+1}
    # the original article suggested a simplex where an initial point is given as x0
    # with the others generated with a fixed step along each dimension in turn.
    bounds = len(lower) and len(upper)
    if bounds:
        x0 = np.clip(x0, lower, upper)

    n = x0.size
    if adaptive:
        gamma = 1.0 + 2.0 / n
        rho = 0.75 - 1.0 / (2.0 * n)
        sigma = 1.0 - 1.0 / n
    simplex = np.full(
        (n + 1, n), fill_value=np.nan, dtype=np.float64
    )  # each row is x_j
    simplex[:] = x0
    # perturb simplex using `init_step`
    diag = np.copy(np.diag(simplex))
    diag[diag == 0.0] = zero_pert
    diag[diag != 0.0] *= 1 + init_step
    np.fill_diagonal(simplex, diag)
    # restrict simplex to bounds if passed
    if bounds:
        for j in range(n + 1):
            simplex[j] = np.clip(simplex[j], lower, upper)
    # array of the value of f
    f_simplex = np.full(n + 1, fill_value=np.nan)
    for j in range(n + 1):
        f_simplex[j] = theta_target_fn(simplex[j], *args)
    for it in range(max_iter):
        # Step1: order of f_simplex
        # print(simplex)
        # print(f_simplex)
        order_f = f_simplex.argsort()
        best_idx = order_f[0]
        worst_idx = order_f[-1]
        second_worst_idx = order_f[-2]
        # Check whether method should stop.
        if np.std(f_simplex) < tol_std:
            break
        # calculate centroid except argmax f_simplex
        x_o = simplex[np.delete(order_f, -1)].sum(axis=0) / n
        # Step2: Reflection, Compute reflected point
        x_r = x_o + alpha * (x_o - simplex[worst_idx])
        # restrict x_r to bounds if passed
        if bounds:
            x_r = np.clip(x_r, lower, upper)
        f_r = theta_target_fn(x_r, *args)
        if f_simplex[best_idx] <= f_r < f_simplex[second_worst_idx]:
            simplex[worst_idx] = x_r
            f_simplex[worst_idx] = f_r
            continue
        # Step3: Expansion, reflected point is the best point so far
        if f_r < f_simplex[best_idx]:
            x_e = x_o + gamma * (x_r - x_o)
            # restrict x_e to bounds if passed
            if bounds:
                x_e = np.clip(x_e, lower, upper)
            f_e = theta_target_fn(x_e, *args)
            if f_e < f_r:
                simplex[worst_idx] = x_e
                f_simplex[worst_idx] = f_e
            else:
                simplex[worst_idx] = x_r
                f_simplex[worst_idx] = f_r
            continue
        # Step4: outside Contraction
        if f_simplex[second_worst_idx] <= f_r < f_simplex[worst_idx]:
            x_oc = x_o + rho * (x_r - x_o)
            if bounds:
                x_oc = np.clip(x_oc, lower, upper)
            f_oc = theta_target_fn(x_oc, *args)
            if f_oc <= f_r:
                simplex[worst_idx] = x_oc
                f_simplex[worst_idx] = f_oc
                continue
        # step 5 inside contraction
        else:
            x_ic = x_o - rho * (x_r - x_o)
            # restrict x_c to bounds if passed
            if bounds:
                x_ic = np.clip(x_ic, lower, upper)
            f_ic = theta_target_fn(x_ic, *args)
            if f_ic < f_simplex[worst_idx]:
                simplex[worst_idx] = x_ic
                f_simplex[worst_idx] = f_ic
                continue
        # step 6: shrink
        simplex[np.delete(order_f, 0)] = simplex[best_idx] + sigma * (
            simplex[np.delete(order_f, 0)] - simplex[best_idx]
        )
        for i in np.delete(order_f, 0):
            simplex[i] = np.clip(simplex[i], lower, upper)
            f_simplex[i] = theta_target_fn(simplex[i], *args)
    return results(simplex[best_idx], f_simplex[best_idx], it + 1, simplex)

# %% ../nbs/src/theta.ipynb 23
def optimize_theta_target_fn(init_par, optimize_params, y, modeltype, nmse):
    x0 = [init_par[key] for key, val in optimize_params.items() if val]
    x0 = np.array(x0, dtype=np.float32)
    if not len(x0):
        return

    init_level = init_par["initial_smoothed"]
    init_alpha = init_par["alpha"]
    init_theta = init_par["theta"]

    opt_level = optimize_params["initial_smoothed"]
    opt_alpha = optimize_params["alpha"]
    opt_theta = optimize_params["theta"]

    res = nelder_mead_theta(
        x0,
        args=(
            init_level,
            init_alpha,
            init_theta,
            opt_level,
            opt_alpha,
            opt_theta,
            y,
            modeltype,
            nmse,
        ),
        tol_std=1e-4,
        lower=np.array([-1e10, 0.1, 1.0]),
        upper=np.array([1e10, 0.99, 1e10]),
        max_iter=1_000,
        adaptive=True,
    )
    return res

# %% ../nbs/src/theta.ipynb 24
@njit(nogil=NOGIL, cache=CACHE)
def is_constant(x):
    return np.all(x[0] == x)

# %% ../nbs/src/theta.ipynb 26
def thetamodel(
    y: np.ndarray,
    m: int,
    modeltype: str,
    initial_smoothed: float,
    alpha: float,
    theta: float,
    nmse: int,
):
    # initial parameters
    par = initparamtheta(
        initial_smoothed=initial_smoothed,
        alpha=alpha,
        theta=theta,
        y=y,
        modeltype=modeltype,
    )
    optimize_params = {
        key.replace("optimize_", ""): val for key, val in par.items() if "optim" in key
    }
    par = {key: val for key, val in par.items() if "optim" not in key}
    # parameter optimization
    fred = optimize_theta_target_fn(
        init_par=par,
        optimize_params=optimize_params,
        y=y,
        modeltype=modeltype,
        nmse=nmse,
    )
    if fred is not None:
        fit_par = fred.x
    j = 0
    if optimize_params["initial_smoothed"]:
        j += 1
    if optimize_params["alpha"]:
        par["alpha"] = fit_par[j]
        j += 1
    if optimize_params["theta"]:
        par["theta"] = fit_par[j]
        j += 1

    amse, e, states, mse = pegelsresid_theta(y=y, modeltype=modeltype, nmse=nmse, **par)

    return dict(
        mse=mse,
        amse=amse,
        fit=fred,
        residuals=e,
        m=m,
        states=states,
        par=par,
        n=len(y),
        modeltype=modeltype,
        mean_y=np.mean(y),
    )

# %% ../nbs/src/theta.ipynb 28
def compute_pi_samples(
    n, h, states, sigma, alpha, theta, mean_y, seed=0, n_samples=200
):
    samples = np.full((h, n_samples), fill_value=np.nan, dtype=np.float32)
    # states: level, meany, An, Bn, mu
    smoothed, _, A, B, _ = states[-1]
    np.random.seed(seed)
    for i in range(n, n + h):
        samples[i - n] = smoothed + (1 - 1 / theta) * (
            A * ((1 - alpha) ** i) + B * (1 - (1 - alpha) ** (i + 1)) / alpha
        )
        samples[i - n] += np.random.normal(scale=sigma, size=n_samples)
        smoothed = alpha * samples[i - n] + (1 - alpha) * smoothed
        mean_y = (i * mean_y + samples[i - n]) / (i + 1)
        B = ((i - 1) * B + 6 * (samples[i - n] - mean_y) / (i + 1)) / (i + 2)
        A = mean_y - B * (i + 2) / 2
    return samples

# %% ../nbs/src/theta.ipynb 29
def forecast_theta(obj, h, level=None):
    forecast = np.full(h, fill_value=np.nan)
    n = obj["n"]
    states = obj["states"]
    alpha = obj["par"]["alpha"]
    theta = obj["par"]["theta"]
    thetaforecast(
        states=states,
        n=n,
        modeltype=switch_theta(obj["modeltype"]),
        h=h,
        f=forecast,
        alpha=alpha,
        theta=theta,
    )
    res = {"mean": forecast}

    if level is not None:
        sigma = np.std(obj["residuals"][3:], ddof=1)
        mean_y = obj["mean_y"]
        samples = compute_pi_samples(
            n=n,
            h=h,
            states=states,
            sigma=sigma,
            alpha=alpha,
            theta=theta,
            mean_y=mean_y,
        )
        for lv in level:
            min_q = (100 - lv) / 200
            max_q = min_q + lv / 100
            res[f"lo-{lv}"] = np.quantile(samples, min_q, axis=1)
            res[f"hi-{lv}"] = np.quantile(samples, max_q, axis=1)

    if obj.get("decompose", False):
        seas_forecast = _repeat_val_seas(obj["seas_forecast"]["mean"], h=h)
        for key in res:
            if obj["decomposition_type"] == "multiplicative":
                res[key] = res[key] * seas_forecast
            else:
                res[key] = res[key] + seas_forecast
    return res

# %% ../nbs/src/theta.ipynb 31
def auto_theta(
    y,
    m,
    model=None,
    initial_smoothed=None,
    alpha=None,
    theta=None,
    nmse=3,
    decomposition_type="multiplicative",
):
    # converting params to floats
    # to improve numba compilation
    if initial_smoothed is None:
        initial_smoothed = np.nan
    if alpha is None:
        alpha = np.nan
    if theta is None:
        theta = np.nan
    if nmse < 1 or nmse > 30:
        raise ValueError("nmse out of range")
    # constan values
    if is_constant(y):
        thetamodel(
            y=y,
            m=m,
            modeltype="STM",
            nmse=nmse,
            initial_smoothed=np.mean(y) / 2,
            alpha=0.5,
            theta=2.0,
        )
    # seasonal decomposition if needed
    decompose = False
    # seasonal test
    if m >= 4:
        r = acf(y, nlags=m, fft=False)[1:]
        stat = np.sqrt((1 + 2 * np.sum(r[:-1] ** 2)) / len(y))
        decompose = np.abs(r[-1]) / stat > norm.ppf(0.95)

    data_positive = min(y) > 0
    if decompose:
        # change decomposition type if data is not positive
        if decomposition_type == "multiplicative" and not data_positive:
            decomposition_type = "additive"
        y_decompose = seasonal_decompose(y, model=decomposition_type, period=m).seasonal
        if decomposition_type == "multiplicative" and any(y_decompose < 0.01):
            decomposition_type = "additive"
            y_decompose = seasonal_decompose(y, model="additive", period=m).seasonal
        if decomposition_type == "additive":
            y = y - y_decompose
        else:
            y = y / y_decompose
        seas_forecast = _seasonal_naive(
            y=y_decompose, h=m, season_length=m, fitted=False
        )

    # validate model
    if model not in [None, "STM", "OTM", "DSTM", "DOTM"]:
        raise ValueError("Invalid model type")

    n = len(y)
    npars = 3
    # non-optimized tiny datasets
    if n <= npars:
        raise NotImplementedError("tiny datasets")
    if model is None:
        modeltype = ["STM", "OTM", "DSTM", "DOTM"]
    else:
        modeltype = [model]

    best_ic = np.inf
    for mtype in modeltype:
        fit = thetamodel(
            y=y,
            m=m,
            modeltype=mtype,
            nmse=nmse,
            initial_smoothed=initial_smoothed,
            alpha=alpha,
            theta=theta,
        )
        fit_ic = fit["mse"]
        if not np.isnan(fit_ic):
            if fit_ic < best_ic:
                model = fit
                best_ic = fit_ic
    if np.isinf(best_ic):
        raise Exception("no model able to be fitted")

    if decompose:
        if decomposition_type == "multiplicative":
            model["residuals"] = model["residuals"] * y_decompose
        else:
            model["residuals"] = model["residuals"] + y_decompose
        model["decompose"] = decompose
        model["decomposition_type"] = decomposition_type
        model["seas_forecast"] = dict(seas_forecast)
    return model

# %% ../nbs/src/theta.ipynb 41
def forward_theta(fitted_model, y):
    m = fitted_model["m"]
    model = fitted_model["modeltype"]
    initial_smoothed = fitted_model["par"]["initial_smoothed"]
    alpha = fitted_model["par"]["alpha"]
    theta = fitted_model["par"]["theta"]
    return auto_theta(
        y=y,
        m=m,
        model=model,
        initial_smoothed=initial_smoothed,
        alpha=alpha,
        theta=theta,
    )
