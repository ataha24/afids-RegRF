#!/usr/bin/env python
"""Methods for applying trained regRF models."""
from __future__ import annotations

import itertools as it
from argparse import ArgumentParser
from collections.abc import Iterable, Sequence
from os import PathLike
from pathlib import Path
from typing import NoReturn

import numpy as np
import pandas as pd
from joblib import load
from numpy.typing import NDArray

from utils import afids_to_fcsv, get_fid, gen_features

def apply_afid_model(
    afid_num: int,
    subject_paths: Iterable[PathLike[str] | str],
    fcsv_paths: Iterable[PathLike[str] | str],
    model_dir_path: PathLike[str] | str,
    feature_offsets: tuple[NDArray, NDArray],
    padding: int,
    sampling_rate: int,
    size: int
) -> NDArray:
    """Apply a trained regRF model for a fiducial"""
    aff, diff, samples = it.chain.from_iterable(
        gen_features(
            subject_path,
            get_fid(fcsv_path, afid_num - 1),
            feature_offsets,
            padding,
            sampling_rate,
            size,
            predict=True
        )
        for subject_path, fcsv_path in zip(subject_paths, fcsv_paths)
    )

    # NOTE: Load from appropriate location
    # Load trained model and predict distances of coordinates
    model_fname = f"afid-{str(afid_num).zfill(2)}_desc-rf_sampleRate-iso{sampling_rate}vox_model.joblib"
    regr_rf = load(Path(model_dir_path) / model_fname)
    dist_predict = regr_rf.predict(diff)

    # Extract smallest Euclidean distance from predictions
    dist_df = pd.DataFrame(dist_predict)
    print(dist_df[0].max())
    idx = dist_df[0].idxmax()

    # Reverse look up to determine voxel with lowest distances
    print(f'Voxel coordinates with greatest likelihood of being AFID #{afid_num} are: {samples[idx]}')

    afid_coords = aff[:3, :3].dot(samples[idx]) + aff[:3, 3]

    return afid_coords


def apply_all_afid_models(
    subject_paths: Sequence[PathLike[str] | str],
    fcsv_paths: Sequence[PathLike[str] | str],
    feature_offsets_path: PathLike | str,
    model_dir_path: PathLike | str,
    padding: int = 0,
    size: int = 1,
    sampling_rate: int = 5,
) -> NoReturn:
    """Apply a trained regRF fiducial for each of the 32 AFIDs."""
    all_afids_coords = np.empty((3, ), dtype=float) 

    feature_offsets = np.load(feature_offsets_path)
    for afid_num in range(1, 33):
        afid_coords = apply_afid_model(
            afid_num,
            subject_paths,
            fcsv_paths,
            model_dir_path,
            (feature_offsets["arr_0"], feature_offsets["arr_1"]),
            padding,
            size,
            sampling_rate,
        )
        all_afids_coords = np.vstack((all_afids_coords, afid_coords))
    
    afids_to_fcsv(all_afids_coords[1:].astype(int))


def gen_parser() -> ArgumentParser:
    """Generate CLI parser for script"""
    parser = ArgumentParser()

    parser.add_argument(
        "--subject_paths",
        nargs="+",
        type=str,
        help=(
            "Path to subject nifti images. If more than 1 subject, pass paths "
            "as space-separated list."
        )    
    )
    parser.add_argument(
        "--fcsv_paths",
        nargs="+",
        type=str,
        help=(
            "Path to subject fcsv files. If more than 1 subject, pass paths as "
            "space-separated list."
        )
    )
    parser.add_argument(
        "--feature_offsets_path",
        nargs="1",
        type=str,
        help=(
            "Path to featuers_offsets.npz file"
        )
    )
    parser.add_argument(
        "--model_dir_path",
        nargs=1,
        type=str,
        help=(
            "Path to directory for saving fitted models."
        )
    )
    parser.add_argument(
        "--padding",
        nargs="?",
        type=int,
        default=0,
        required=False,
        help=(
            "Number of voxels to add when zero-padding nifti images. "
            "Default: 0"
        )
    )
    parser.add_argument(
        "--size",
        nargs="?",
        type=int,
        default=1,
        required=False,
        help=("Factor to resample nifti image by. Default: 1")
    )
    parser.add_argument(
        "--sampling_rate",
        nargs="?",
        type=int,
        default=5,
        required=False,
        help=(
            "Number of voxels in both directions along each axis to sample as 
            "part of the training Default: 5"
        )
    )

    return parser


def main():
    parser = gen_parser()
    args = parser.parse_args()

    apply_all_afid_models(
        subject_paths=args.subject_paths,
        fcsv_paths=args.fcsv_paths,
        feature_offsets_path=args.feature_offsets_path,
        model_dir_path=args.model_dir_path,
        padding=args.padding,
        size=args.size,
        sampling_rate=args.sampling_rate,
    )


if __name__ == "__main__":
    main()