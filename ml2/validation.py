"""Purged walk-forward splits for overlapping labels.

Events are ordered by t0. Because every label looks `horizon` bars ahead, a training event whose
[t0, exit_idx] reaches into the test period would leak the test outcome into training - such events are PURGED.
The scheme is forward-only (train always precedes test), so no embargo after the test block is needed.
"""
import numpy as np


def purge(train_pos, exit_idx, boundary_bar):
    """Keep only training events whose label had fully resolved before `boundary_bar`."""
    train_pos = np.asarray(train_pos)
    return train_pos[exit_idx[train_pos] < boundary_bar]


def purged_walk_forward(t0, exit_idx, n_splits=5):
    """Expanding-window folds: list of {"train": positions, "test": positions}. Needs sorted t0."""
    t0, exit_idx = np.asarray(t0), np.asarray(exit_idx)
    if len(t0) != len(exit_idx) or np.any(np.diff(t0) < 0):
        raise ValueError("t0 must be sorted and aligned with exit_idx")
    if n_splits < 1 or len(t0) < (n_splits + 1) * 2:
        raise ValueError("not enough events for %d splits" % n_splits)
    parts = np.array_split(np.arange(len(t0)), n_splits + 1)
    folds = []
    for i in range(n_splits):
        train = np.concatenate(parts[:i + 1])
        test = parts[i + 1]
        folds.append({"train": purge(train, exit_idx, t0[test[0]]), "test": test})
    return folds
