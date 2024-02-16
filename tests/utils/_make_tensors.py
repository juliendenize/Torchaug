import torch
from torchaug.transforms._utils import _max_value as get_max_value
from torchvision import tv_tensors
from torchaug import ta_tensors

BATCH_DEFAULT_SIZE = (2,)
DEFAULT_SIZE = (17, 11)


NUM_CHANNELS_MAP = {
    "GRAY": 1,
    "GRAY_ALPHA": 2,
    "RGB": 3,
    "RGBA": 4,
}


def make_image(
    size=DEFAULT_SIZE,
    *,
    color_space="RGB",
    batch_dims=(),
    dtype=None,
    device="cpu",
    memory_format=torch.contiguous_format,
):
    num_channels = NUM_CHANNELS_MAP[color_space]
    dtype = dtype or torch.uint8
    max_value = get_max_value(dtype)
    data = torch.testing.make_tensor(
        (*batch_dims, num_channels, *size),
        low=0,
        high=max_value,
        dtype=dtype,
        device=device,
        memory_format=memory_format,
    )
    if color_space in {"GRAY_ALPHA", "RGBA"}:
        data[..., -1, :, :] = max_value

    return ta_tensors.Image(data)


def make_image_tensor(*args, **kwargs):
    return make_image(*args, **kwargs).as_subclass(torch.Tensor)


def make_batch_images(*args, batch_dims=BATCH_DEFAULT_SIZE, **kwargs):
    return ta_tensors.BatchImages(
        make_image_tensor(*args, batch_dims=batch_dims, **kwargs)
    )


def make_batch_images_tensor(*args, **kwargs):
    return make_batch_images(*args, **kwargs).as_subclass(torch.Tensor)


def make_bounding_boxes(
    canvas_size=DEFAULT_SIZE,
    *,
    format=tv_tensors.BoundingBoxFormat.XYXY,
    num_boxes=1,
    dtype=None,
    device="cpu",
):
    def sample_position(values, max_value):
        # We cannot use torch.randint directly here, because it only allows integer scalars as values for low and high.
        # However, if we have batch_dims, we need tensors as limits.
        return torch.stack([torch.randint(max_value - v, ()) for v in values.tolist()])

    if isinstance(format, str):
        format = tv_tensors.BoundingBoxFormat[format]

    dtype = dtype or torch.float32

    h, w = [torch.randint(1, s, (num_boxes,)) for s in canvas_size]
    y = sample_position(h, canvas_size[0])
    x = sample_position(w, canvas_size[1])

    if format is tv_tensors.BoundingBoxFormat.XYWH:
        parts = (x, y, w, h)
    elif format is tv_tensors.BoundingBoxFormat.XYXY:
        x1, y1 = x, y
        x2 = x1 + w
        y2 = y1 + h
        parts = (x1, y1, x2, y2)
    elif format is tv_tensors.BoundingBoxFormat.CXCYWH:
        cx = x + w / 2
        cy = y + h / 2
        parts = (cx, cy, w, h)
    else:
        raise ValueError(f"Format {format} is not supported")

    return ta_tensors.BoundingBoxes(
        torch.stack(parts, dim=-1).to(dtype=dtype, device=device),
        format=format,
        canvas_size=canvas_size,
    )


def make_batch_bounding_boxes(
    canvas_size=DEFAULT_SIZE,
    *,
    format=tv_tensors.BoundingBoxFormat.XYXY,
    num_boxes=1,
    batch_size=BATCH_DEFAULT_SIZE[0],
    dtype=None,
    device="cpu",
):
    bboxes = []
    for _ in range(batch_size):
        bboxes.append(
            make_bounding_boxes(
                canvas_size=canvas_size,
                format=format,
                num_boxes=num_boxes,
                dtype=dtype,
                device=device,
            ).as_subclass(torch.Tensor)
        )
    bboxes = torch.cat(bboxes)
    idx_sample = torch.tensor([0] + [num_boxes] * batch_size, device=device)
    return ta_tensors.BatchBoundingBoxes(
        bboxes, format=format, canvas_size=canvas_size, idx_sample=idx_sample
    )


def make_detection_masks(size=DEFAULT_SIZE, *, num_masks=1, dtype=None, device="cpu"):
    """Make a "detection" mask, i.e. (N, H, W), where each object is encoded as one of N boolean masks."""
    return ta_tensors.Mask(
        torch.testing.make_tensor(
            (num_masks, *size),
            low=0,
            high=2,
            dtype=dtype or torch.bool,
            device=device,
        )
    )


def make_batch_detection_masks(
    batch_dims=BATCH_DEFAULT_SIZE,
    size=DEFAULT_SIZE,
    *,
    num_masks=1,
    dtype=None,
    device="cpu",
):
    """Make a batch of "detection" masks, i.e. (B, N, H, W), where each object is encoded as one of N boolean
    masks."""
    return ta_tensors.BatchMasks(
        torch.testing.make_tensor(
            (*batch_dims, num_masks, *size),
            low=0,
            high=2,
            dtype=dtype or torch.bool,
            device=device,
        )
    )


def make_segmentation_mask(
    size=DEFAULT_SIZE, *, num_categories=10, batch_dims=(), dtype=None, device="cpu"
):
    """Make a "segmentation" mask, i.e. (*, H, W), where the category is encoded as pixel value."""
    return ta_tensors.Mask(
        torch.testing.make_tensor(
            (*batch_dims, *size),
            low=0,
            high=num_categories,
            dtype=dtype or torch.uint8,
            device=device,
        )
    )


def make_batch_segmentation_masks(
    size=DEFAULT_SIZE,
    *,
    num_categories=10,
    batch_dims=BATCH_DEFAULT_SIZE,
    dtype=None,
    device="cpu",
):
    """Make a batch of "segmentation" masks, i.e. (B, *, H, W), where the category is encoded as pixel value."""
    return ta_tensors.BatchMasks(
        torch.testing.make_tensor(
            (*batch_dims, *size),
            low=0,
            high=num_categories,
            dtype=dtype or torch.uint8,
            device=device,
        )
    )


def make_video(size=DEFAULT_SIZE, *, num_frames=3, batch_dims=(), **kwargs):
    return ta_tensors.Video(
        make_image(size, batch_dims=(*batch_dims, num_frames), **kwargs)
    )


def make_video_tensor(*args, **kwargs):
    return make_video(*args, **kwargs).as_subclass(torch.Tensor)


def make_batch_videos(*args, batch_dims=BATCH_DEFAULT_SIZE, **kwargs):
    return ta_tensors.BatchVideos(
        make_video_tensor(*args, batch_dims=batch_dims, **kwargs)
    )


def make_batch_videos_tensor(*args, **kwargs):
    return make_batch_videos(*args, **kwargs).as_subclass(torch.Tensor)
