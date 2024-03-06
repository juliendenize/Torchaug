from __future__ import annotations

import numpy as np
import torch

from torchaug import ta_tensors


@torch.jit.unused
def to_image(inpt: torch.Tensor | np.ndarray) -> ta_tensors.Image:
    """See :class:`~torchaug.transforms.ToImage` for details."""
    if isinstance(inpt, np.ndarray):
        output = torch.from_numpy(np.atleast_3d(inpt)).permute((2, 0, 1)).contiguous()
    elif isinstance(inpt, torch.Tensor):
        output = inpt
    else:
        raise TypeError(
            f"Input can either be a pure Tensor, a numpy array, but got {type(inpt)} instead."
        )
    return ta_tensors.Image(output)


@torch.jit.unused
def to_batch_images(inpt: torch.Tensor) -> ta_tensors.BatchImages:
    """See :class:`~torchaug.transforms.ToBatchImages` for details."""
    if isinstance(inpt, torch.Tensor):
        output = inpt
    else:
        raise TypeError(f"Input should be a Tensor.")
    return ta_tensors.BatchImages(output)
