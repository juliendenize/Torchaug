from __future__ import annotations

import enum
from math import ceil, floor
from typing import Any, Callable, Dict, List, Tuple, Type, Union

import torch
from torch import nn
from torch.utils._pytree import tree_flatten, tree_unflatten
from torchvision.transforms.v2._utils import check_type, has_any, is_pure_tensor
from torchvision.tv_tensors import set_return_type

from torchaug import ta_tensors
from torchaug.utils import _log_api_usage_once

from .functional._utils._kernel import _get_kernel


class RandomApplyTransform(nn.Module):
    _transformed_types: Tuple[Union[Type, Callable[[Any], bool]], ...] = (torch.Tensor,)
    _reshape_transform: bool = False
    _receive_flatten_inputs: bool = False

    def __init__(
        self,
        p: float = 0.5,
        inplace: bool = False,
        num_chunks: int = 1,
        permute_chunks: bool = False,
        batch_transform: bool = False,
    ) -> None:
        if not (0.0 <= p <= 1.0):
            raise ValueError(
                "`p` should be a floating point value in the interval [0.0, 1.0]."
            )
        elif p > 0 and p < 1 and self._reshape_transform and batch_transform:
            raise ValueError(
                "`p` should be 0 or 1 if `_reshape_transform` is True and `batch_transform` is True."
            )
        if inplace and self._reshape_transform:
            raise ValueError(
                "`inplace` should be False if `_reshape_transform` is True."
            )
        if (num_chunks == -1 or num_chunks > 1) and not batch_transform:
            raise ValueError("`num_chunks` should be 1 if `batch_transform` is False.")
        elif num_chunks < -1:
            raise ValueError("`num_chunks` should be greater than or equal to -1.")

        super().__init__()
        _log_api_usage_once(self)
        self.inplace = inplace
        self.num_chunks = num_chunks
        self.permute_chunks = permute_chunks
        self.p = p
        self.batch_transform = batch_transform

    @staticmethod
    def _get_input_batch_size(inpt: Any):
        batch_size = None
        if isinstance(inpt, ta_tensors.BatchBoundingBoxes):
            batch_size = inpt.batch_size
        elif isinstance(inpt, torch.Tensor):
            batch_size = inpt.shape[0]

        return batch_size

    def _get_chunks_indices(self, flat_inputs: List[Any], num_chunks: int):
        batch_size = self._get_input_batch_size(flat_inputs[0])
        device = flat_inputs[0].device

        if num_chunks == 1:
            return (torch.arange(0, batch_size, device=device),)
        else:
            if self.permute_chunks:
                indices = torch.randperm(batch_size, device=device)
            else:
                indices = torch.arange(0, batch_size, device=device)
            return indices.chunk(num_chunks)

    def _needs_transform_list(self, flat_inputs: List[Any]) -> List[bool]:
        # Below is a heuristic on how to deal with pure tensor inputs:
        # 1. Pure tensors, i.e. tensors that are not a tv_tensor, are passed through if there is an explicit image
        #    (`ta_tensors.Image`, `ta_tensors.BatchImages`) or video (`ta_tensors.Video`, `ta_tensors.BatchVideos`) in the sample.
        # 2. If there is no explicit image or video in the sample, only the first encountered pure tensor is
        #    transformed as image, while the rest is passed through. The order is defined by the returned `flat_inputs`
        #    of `tree_flatten`, which recurses depth-first through the input.
        #
        # This heuristic stems from two requirements:
        # 1. We need to keep BC for single input pure tensors and treat them as images.
        # 2. We don't want to treat all pure tensors as images, because some datasets like `CelebA` or `Widerface`
        #    return supplemental numerical data as tensors that cannot be transformed as images.
        #
        # The heuristic should work well for most people in practice. The only case where it doesn't is if someone
        # tries to transform multiple pure tensors at the same time, expecting them all to be treated as images.
        # However, this case wasn't supported by transforms v1 either, so there is no BC concern.

        needs_transform_list = []

        if self.batch_transform:
            transform_pure_tensor = not has_any(
                flat_inputs,
                ta_tensors.BatchImages,
                ta_tensors.BatchVideos,
            )
        else:
            transform_pure_tensor = not has_any(
                flat_inputs,
                ta_tensors.Image,
                ta_tensors.BatchImages,
                ta_tensors.Video,
                ta_tensors.BatchVideos,
            )
        for inpt in flat_inputs:
            needs_transform = True

            if not check_type(inpt, self._transformed_types):
                needs_transform = False
            elif is_pure_tensor(inpt):
                if transform_pure_tensor:
                    transform_pure_tensor = False
                else:
                    needs_transform = False
            needs_transform_list.append(needs_transform)
        return needs_transform_list

    def _get_params(
        self,
        flat_inputs: List[Any],
        num_chunks: int,
        chunks_indices: List[torch.Tensor],
    ) -> List[Dict[str, Any]]:
        return [dict() for _ in range(num_chunks)]

    def _get_indices_transform(
        self, batch_size: int, device: torch.device
    ) -> torch.Tensor | None:

        p_mul_batch_size = self.p * batch_size
        floor_apply = floor(p_mul_batch_size)
        ceil_apply = ceil(p_mul_batch_size)

        # If 0 < p_mul_batch_size < 1, then only one element from input is augmented
        # with p probability.
        if floor_apply == 0 or ceil_apply == 0:
            num_transform = 1 if torch.rand(1).item() < self.p else 0
        elif floor_apply == ceil_apply:
            num_transform = floor_apply
        # If p_mul_batch_size is rational, then upper or lower integer p_mul_batch_size
        # elements from input are augmented randomly depending with the decimal.
        else:
            decimal = p_mul_batch_size % 1
            num_transform = (
                floor_apply if decimal < torch.rand(1).item() else ceil_apply
            )

        # If no augmentation return the output directly, keep consistency of inplace.
        if num_transform == 0:
            return None
        elif num_transform == 1:
            indices_transform = torch.randint(0, batch_size, (1,), device=device)
        elif num_transform > 1:
            indices_transform = torch.randperm(batch_size, device=device)[
                :num_transform
            ]
        return indices_transform

    def _check_inputs(self, flat_inputs: List[Any]) -> None:
        pass

    def _call_kernel(
        self, functional: Callable, inpt: Any, *args: Any, **kwargs: Any
    ) -> Any:
        kernel = _get_kernel(functional, type(inpt), allow_passthrough=True)
        return kernel(inpt, *args, **kwargs)

    def _transform(self, inpt: Any, params: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def forward_single(self, flat_inputs: List[Any]) -> List[Any]:
        if self.p == 1.0:
            pass
        elif self.p == 0.0 or torch.rand(1) >= self.p:
            return flat_inputs

        needs_transform_list = self._needs_transform_list(flat_inputs)
        params = self._get_params(
            [
                inpt
                for (inpt, needs_transform) in zip(flat_inputs, needs_transform_list)
                if needs_transform
            ],
            num_chunks=1,
            chunks_indices=[torch.tensor([0], device=flat_inputs[0].device)],
        )[0]

        flat_outputs = [
            self._transform(inpt, params) if needs_transform else inpt
            for (inpt, needs_transform) in zip(flat_inputs, needs_transform_list)
        ]

        return flat_outputs

    def forward_batch(self, flat_inputs: List[Any]) -> List[Any]:
        if self.p == 0:  # if p is 0, return the input directly after checking the input
            return flat_inputs

        needs_transform_list = self._needs_transform_list(flat_inputs)

        if self.p == 1:  # if p is 1, transform all inputs
            transform_all = True

        else:
            batch_size = self._get_input_batch_size(flat_inputs[0])
            indices_transform = self._get_indices_transform(
                batch_size,
                flat_inputs[0].device,
            )

            transform_all = indices_transform.shape[0] == batch_size

        if (
            not transform_all and indices_transform is None
        ):  # if no augmentation return the inputs directly.
            return flat_inputs

        if transform_all:
            transform_inpts = flat_inputs
        else:
            transform_inpts = []  # store the input part to be augmented

            # Store the complete outputs before augmentation.
            # Part of the output that is augmented will be updated with the augmented part.
            flat_pre_outputs = []

            for (inpt, needs_transform) in zip(flat_inputs, needs_transform_list):
                if not needs_transform:
                    transform_inpts.append(None)
                    flat_outputs.append(inpt)
                    continue

                is_tv_inpt = isinstance(inpt, ta_tensors.TATensor)
                is_batch_bboxes_inpt = isinstance(inpt, ta_tensors.BatchBoundingBoxes)

                pre_output = (
                    inpt
                    if self.inplace
                    or (self._reshape_transform and not is_batch_bboxes_inpt)
                    else inpt.clone()
                )
                flat_pre_outputs.append(pre_output)

                if is_batch_bboxes_inpt:
                    transform_inpt = pre_output.get_chunk(
                        chunk_indices=indices_transform
                    )
                else:
                    with set_return_type("TVTensor" if is_tv_inpt else "Tensor"):
                        transform_inpt = pre_output[indices_transform]
                transform_inpts.append(transform_inpt)

        transform_batch_size = self._get_input_batch_size(transform_inpts[0])
        if self.num_chunks == -1:
            num_chunks = transform_batch_size
        else:
            num_chunks = min(transform_batch_size, self.num_chunks)

        chunks_indices = self._get_chunks_indices(transform_inpts, num_chunks)

        params = self._get_params(
            [
                transform_inpt
                for (transform_inpt, needs_transform) in zip(
                    transform_inpts, needs_transform_list
                )
                if needs_transform
            ],
            len(chunks_indices),
            chunks_indices,
        )

        transform_outputs = []

        for (transform_inpt, needs_transform) in zip(
            transform_inpts, needs_transform_list
        ):
            if not needs_transform:
                transform_outputs.append(transform_inpt)
                continue
            is_tv_inpt = isinstance(transform_inpt, ta_tensors.TATensor)
            is_batch_bboxes_inpt = isinstance(
                transform_inpt, ta_tensors.BatchBoundingBoxes
            )

            if num_chunks == 1:
                output = self._transform(transform_inpt, params[0])
            else:
                if self._reshape_transform:
                    output = []
                for i, chunk_indices in enumerate(chunks_indices):
                    if is_batch_bboxes_inpt:
                        chunk_inpt = transform_inpt.get_chunk(
                            chunk_indices=chunk_indices
                        )
                        chunk_output = self._transform(chunk_inpt, params[i])
                        transform_inpt.update_chunk_(
                            chunk_output, chunk_indices=chunk_indices
                        )
                    else:
                        with set_return_type("TVTensor" if is_tv_inpt else "Tensor"):
                            chunk_inpt = transform_inpt[chunk_indices]

                        chunk_output = self._transform(chunk_inpt, params[i])

                        if self._reshape_transform:
                            output.append(chunk_output)

                        else:
                            with set_return_type(
                                "TVTensor" if is_tv_inpt else "Tensor"
                            ):
                                transform_inpt[chunk_indices] = chunk_output
                            output = transform_inpt
            transform_outputs.append(output)

        if not transform_all:
            for flat_pre_output, transform_output, needs_transform in zip(
                flat_pre_outputs, transform_outputs, needs_transform_list
            ):
                if not needs_transform:
                    continue

                is_tv_output = isinstance(flat_pre_output, ta_tensors.TATensor)
                is_batch_bboxes_output = isinstance(
                    flat_pre_output, ta_tensors.BatchBoundingBoxes
                )

                if is_batch_bboxes_output:
                    flat_pre_output.update_chunk_(
                        transform_outputs, chunk_indices=indices_transform
                    )
                else:
                    with set_return_type("TVTensor" if is_tv_output else "Tensor"):
                        flat_pre_output[indices_transform] = transform_output

            flat_outputs = flat_pre_outputs
        else:
            flat_outputs = transform_outputs

        flat_outputs = [
            flat_output.contiguous()
            for flat_output, needs_transform in zip(flat_outputs, needs_transform_list)
            if needs_transform
        ]

        return flat_outputs

    def forward(self, *inputs: Any) -> Any:
        if not self._receive_flatten_inputs:
            inputs = inputs if len(inputs) > 1 else inputs[0]
            flat_inputs, spec = tree_flatten(inputs)
        else:
            flat_inputs = list(inputs)

        self._check_inputs(flat_inputs)
        if not self.batch_transform:
            flat_outputs = self.forward_single(flat_inputs)
        else:
            flat_outputs = self.forward_batch(flat_inputs)

        if self._receive_flatten_inputs:
            return tree_unflatten(flat_outputs, spec)

        return flat_outputs

    def extra_repr(self, exclude_names: List[str] = []) -> str:
        if not self.batch_transform:
            # TODO deal with inplace defined sometimes even for single input
            exclude_names.extend(["inplace", "num_chunks", "permute_chunks"])
        exclude_names.append("batch_transform")

        extra = []

        for name, value in self.__dict__.items():
            if name.startswith("_") or name == "training" or name in exclude_names:
                continue

            if not isinstance(value, (bool, int, float, str, tuple, list, enum.Enum)):
                continue

            extra.append(f"{name}={value}")

        return (
            ", ".join(extra) + ", batch_transform=True" if self.batch_transform else ""
        )


class Transform(RandomApplyTransform):
    def __init__(
        self,
        inplace: bool = False,
        num_chunks: int = 1,
        permute_chunks: bool = False,
        batch_transform: bool = False,
    ) -> None:
        super().__init__(
            p=1.0,
            inplace=inplace,
            num_chunks=num_chunks,
            permute_chunks=permute_chunks,
            batch_transform=batch_transform,
        )

    def extra_repr(self, exclude_names: List[str] = []) -> str:
        return super().extra_repr(exclude_names.append("p"))
