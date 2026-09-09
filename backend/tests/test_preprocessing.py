import numpy as np
import pytest

from backend.utils.preprocessing import to_rgb_channels


def test_grayscale_array_gains_three_channels():
    img = np.zeros((10, 20), dtype=np.uint8)
    out = to_rgb_channels(img)
    assert out.shape == (10, 20, 3)
    assert (out[..., 0] == out[..., 1]).all()
    assert (out[..., 1] == out[..., 2]).all()


def test_rgba_drops_alpha_channel():
    img = np.full((8, 8, 4), 255, dtype=np.uint8)
    out = to_rgb_channels(img)
    assert out.shape == (8, 8, 3)


def test_single_channel_array_gains_three_channels():
    img = np.zeros((5, 5, 1), dtype=np.uint8)
    out = to_rgb_channels(img)
    assert out.shape == (5, 5, 3)


def test_rgb_array_is_untouched():
    img = np.zeros((6, 6, 3), dtype=np.uint8)
    out = to_rgb_channels(img)
    assert out.shape == img.shape
    assert out is img