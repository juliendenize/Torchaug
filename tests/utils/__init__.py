import functools

import torch

from ._common import (
    assert_equal,
    assert_not_equal,
    cache,
    cpu_and_cuda,
    freeze_rng_state,
    needs_cuda,
    needs_cuda,
    set_rng_seed,
)

from ._make_tensors import (
    ALL_IMAGES_MAKERS,
    ALL_MAKERS,
    BATCH_IMAGES_AND_VIDEO_TENSOR_AND_SAMPLE_MAKERS,
    BATCH_IMAGES_TENSOR_AND_MAKERS,
    BATCH_MAKERS,
    BATCH_MASK_MAKERS,
    BOUNDING_BOXES_MAKERS,
    IMAGE_AND_VIDEO_TENSOR_AND_MAKERS,
    IMAGE_MAKERS,
    IMAGE_TENSOR_AND_MAKERS,
    make_batch_bounding_boxes,
    make_batch_detection_masks,
    make_batch_images,
    make_batch_images_tensor,
    make_batch_segmentation_masks,
    make_batch_videos,
    make_batch_videos_tensor,
    make_bounding_boxes,
    make_detection_masks,
    make_image,
    make_image_pil,
    make_image_tensor,
    make_segmentation_mask,
    make_video,
    make_video_tensor,
    MASKS_MAKERS,
    SAMPLE_MAKERS,
    VIDEO_MAKERS,
)

from ._transform_utils import (
    _script,
    adapt_fill,
    check_batch_transform,
    check_functional,
    check_functional_kernel_signature_match,
    check_kernel,
    check_kernel_cuda_vs_cpu,
    check_transform,
    check_type,
    CORRECTNESS_FILLS,
    EXHAUSTIVE_TYPE_FILLS,
    param_value_parametrization,
    transform_cls_to_functional,
)
