# global
from typing import Optional, Tuple, Union
import math
import paddle
import ivy.functional.backends.paddle as paddle_backend
from paddle.fluid.libpaddle import Place
from ivy.functional.backends.paddle.device import to_device
from ivy.func_wrapper import (
    with_supported_dtypes,
)


# local
import ivy
from .. import backend_version

# noinspection PyProtectedMember
# Helpers for calculating Window Functions
# ----------------------------------------
# Code from cephes for i0


def _kaiser_window(window_length, beta):
    n = paddle.arange(0, window_length)
    alpha = (window_length - 1) / 2.0
    return paddle_backend.i0(
        beta * paddle.sqrt(1 - paddle_backend.divide((n - alpha), alpha) ** 2.0)
    ) / paddle_backend.i0(beta)


# Array API Standard #
# -------------------#


def kaiser_window(
    window_length: int,
    periodic: bool = True,
    beta: float = 12.0,
    *,
    dtype: Optional[paddle.dtype] = None,
    out: Optional[paddle.Tensor] = None,
) -> paddle.Tensor:
    if window_length < 2:
        return paddle.ones([window_length], dtype=dtype)
    if periodic is False:
        return _kaiser_window(window_length, beta).cast(dtype)
    else:
        return _kaiser_window(window_length + 1, beta)[:-1].cast(dtype)


def vorbis_window(
    window_length: paddle.Tensor,
    *,
    dtype: Optional[paddle.dtype] = paddle.float32,
    out: Optional[paddle.Tensor] = None,
) -> paddle.Tensor:
    if window_length == 0:
        return paddle.to_tensor([], dtype=dtype)
    i = paddle_backend.arange(1, window_length * 2, 2, device=ivy.default_device())
    pi = paddle.full(shape=i.shape, fill_value=math.pi)
    return paddle.sin((pi / 2) * (paddle.sin(pi * i / (window_length * 2)) ** 2)).cast(
        dtype
    )


def hann_window(
    size: int,
    /,
    *,
    periodic: Optional[bool] = True,
    dtype: Optional[paddle.dtype] = None,
    out: Optional[paddle.Tensor] = None,
) -> paddle.Tensor:
    if size < 2:
        return paddle.ones([size], dtype=dtype)
    if periodic:
        count = paddle.arange(size) / size
    else:
        count = paddle.linspace(start=0, stop=size, num=size)
    return (0.5 - 0.5 * paddle.cos(2 * math.pi * count)).cast(dtype)


def tril_indices(
    n_rows: int,
    n_cols: Optional[int] = None,
    k: Optional[int] = 0,
    /,
    *,
    device: Place,
) -> Tuple[paddle.Tensor, ...]:
    # special case due to inconsistent behavior when n_cols=1 and n_rows=0
    if not (n_cols and n_rows):
        return paddle.to_tensor([], dtype="int64"), paddle.to_tensor([], dtype="int64")
    return tuple(
        to_device(
            paddle.tril_indices(n_rows, col=n_cols, offset=k, dtype="int64"), device
        )
    )


@with_supported_dtypes(
    {"2.4.2 and below": ("float64", "float32", "int32", "int64")},
    backend_version,
)
def unsorted_segment_min(
    data: paddle.Tensor,
    segment_ids: paddle.Tensor,
    num_segments: Union[int, paddle.Tensor],
) -> paddle.Tensor:
    ivy.utils.assertions.check_unsorted_segment_min_valid_params(
        data, segment_ids, num_segments
    )
    if data.dtype == paddle.float32:
        init_val = 3.4028234663852886e38  # float32 max
    elif data.dtype == paddle.float64:
        init_val = 1.7976931348623157e308  # float64 max
    elif data.dtype == paddle.int32:
        init_val = 2147483647
    elif data.dtype == paddle.int64:
        init_val = 9223372036854775807
    else:
        raise ValueError("Unsupported data type")
    # Using paddle.full is causing interger overflow for int64
    res = paddle.empty((num_segments,) + tuple(data.shape[1:]), dtype=data.dtype)
    res[:] = init_val
    for i in range(num_segments):
        mask_index = segment_ids == i
        if paddle.any(mask_index):
            res[i] = paddle.min(data[mask_index], 0)

    return res
