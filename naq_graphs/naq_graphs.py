"""Main functions of NAQ graphs"""
import multiprocessing

import numpy as np
import scipy as sc
from tqdm import tqdm

from . import modes
from .utils import _to_complex


class WorkerModes:
    """Worker to find modes."""

    def __init__(self, estimated_modes, graph, params, D0s=None):
        self.graph = graph
        self.params = params
        self.estimated_modes = estimated_modes
        self.D0s = D0s

    def __call__(self, mode_id):
        if self.D0s is not None:
            self.params["D0"] = self.D0s[mode_id]
        return modes.refine_mode_brownian_ratchet(
            self.estimated_modes[mode_id], self.graph, self.params
        )


class WorkerScan:
    """Worker to scan complex frequency."""

    def __init__(self, graph):
        self.graph = graph

    def __call__(self, freq):
        return modes.mode_quality(_to_complex(freq), self.graph)


def scan_frequencies(graph, params, n_workers=1):
    """Scan a range of complex frequencies and return mode qualities."""
    ks = np.linspace(params["k_min"], params["k_max"], params["k_n"])
    alphas = np.linspace(params["alpha_min"], params["alpha_max"], params["alpha_n"])
    freqs = [[k, a] for k in ks for a in alphas]

    worker_scan = WorkerScan(graph)
    pool = multiprocessing.Pool(n_workers)
    qualities_list = list(
        tqdm(
            pool.imap(worker_scan, freqs, chunksize=100),
            total=len(freqs),
        )
    )
    pool.close()

    id_k = [k_i for k_i in range(len(ks)) for a_i in range(len(alphas))]
    id_a = [a_i for k_i in range(len(ks)) for a_i in range(len(alphas))]
    qualities = sc.sparse.coo_matrix(
        (qualities_list, (id_k, id_a)), shape=(params["k_n"], params["alpha_n"])
    ).toarray()

    return ks, alphas, qualities


def find_modes(ks, alphas, qualities, graph, params, n_workers=1):
    """Find the modes from a scan."""
    estimated_modes = modes.find_rough_modes_from_scan(
        ks, alphas, qualities, min_distance=2, threshold_abs=1.0
    )

    worker_modes = WorkerModes(estimated_modes, graph, params)
    pool = multiprocessing.Pool(n_workers)
    refined_modes = pool.map(worker_modes, range(len(estimated_modes)))
    pool.close()

    if len(refined_modes) == 0:
        raise Exception("No modes found!")

    true_modes = modes.clean_duplicate_modes(
        refined_modes, ks[1] - ks[0], alphas[1] - alphas[0]
    )
    return true_modes[np.argsort(true_modes[:, 1])]


def pump_trajectories(  # pylint: disable=too-many-locals
    passive_modes, graph, params, D0s, n_workers=1, return_approx=False
):
    """For a sequence of D0s, find the mode positions of the modes modes."""
    pool = multiprocessing.Pool(n_workers)

    if return_approx:
        new_modes_approx_all = []

    new_modes = [passive_modes.copy()]
    for d in tqdm(range(len(D0s) - 1)):
        new_modes_approx = new_modes[-1].copy()
        for m in range(len(passive_modes)):
            new_modes_approx[m] = modes.pump_linear(
                new_modes[-1][m], graph, params, D0s[d], D0s[d + 1]
            )

        if return_approx:
            new_modes_approx_all.append(new_modes_approx)

        params["D0"] = D0s[d + 1]
        worker_modes = WorkerModes(new_modes_approx, graph, params)
        new_modes_tmp = np.array(pool.map(worker_modes, range(len(new_modes_approx))))

        for i, mode in enumerate(new_modes_tmp):
            if mode is None:
                print("Mode not be updated, consider changing the search parameters.")
                new_modes_tmp[i] = new_modes[-1][i]
        new_modes.append(new_modes_tmp)

    pool.close()

    if return_approx:
        return np.array(new_modes), np.array(new_modes_approx_all)
    return np.array(new_modes)


def find_threshold_lasing_modes(  # pylint: disable=too-many-locals
    passive_modes, graph, params, D0_max, D0_steps, threshold=1e-2, n_workers=1
):
    """Find the threshold lasing modes and associated lasing thresholds."""
    pool = multiprocessing.Pool(n_workers)
    stepsize = params["search_stepsize"]

    new_modes = passive_modes.copy()
    threshold_lasing_modes = []

    lasing_thresholds = []
    D0s = np.zeros(len(passive_modes))

    while len(new_modes) > 0:
        print(len(new_modes), "modes left to find")

        new_D0s = np.zeros(len(new_modes))
        new_modes_approx = []
        for i, new_mode in enumerate(new_modes):
            new_D0s[i] = D0s[i] + modes.lasing_threshold_linear(
                new_mode, graph, params, D0s[i]
            )

            new_D0s[i] = min(D0_steps + D0s[i], new_D0s[i])

            new_modes_approx.append(
                modes.pump_linear(new_mode, graph, params, D0s[i], new_D0s[i])
            )

        # this is a trick to reduce the stepsizes as we are near the solution
        params["search_stepsize"] = (
            stepsize * np.mean(abs(new_D0s - D0s)) / np.mean(new_D0s)
        )

        worker_modes = WorkerModes(new_modes_approx, graph, params, D0s=new_D0s)
        new_modes_tmp = np.array(pool.map(worker_modes, range(len(new_modes_approx))))

        selected_modes = []
        selected_D0s = []
        for i, mode in enumerate(new_modes_tmp):
            if mode is None:
                print(
                    "A mode could not be updated, consider changing the search parameters"
                )
                selected_modes.append(new_modes[i])
                selected_D0s.append(D0s[i])

            elif abs(mode[1]) < threshold:
                threshold_lasing_modes.append(mode)
                lasing_thresholds.append(new_D0s[i])

            elif new_D0s[i] < D0_max:
                selected_modes.append(mode)
                selected_D0s.append(new_D0s[i])

        new_modes = selected_modes.copy()
        D0s = selected_D0s.copy()

    pool.close()

    return threshold_lasing_modes, lasing_thresholds
