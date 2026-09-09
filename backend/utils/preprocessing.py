import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional


def resize_image(image: np.ndarray, max_dim: int = 1280) -> np.ndarray:
    """Resize image maintaining aspect ratio so max dimension <= max_dim."""
    h, w = image.shape[:2]
    if max(h, w) <= max_dim:
        return image
    scale = max_dim / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize pixel values to [0, 1] range."""
    return image.astype(np.float32) / 255.0


def denormalize_image(image: np.ndarray) -> np.ndarray:
    """Convert normalized [0, 1] image back to [0, 255] uint8."""
    return np.clip(image * 255, 0, 255).astype(np.uint8)


def adjust_contrast(image: np.ndarray, alpha: float = 1.2, beta: int = 10) -> np.ndarray:
    """Adjust contrast and brightness. alpha > 1 increases contrast."""
    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def enhance_image(image: np.ndarray) -> np.ndarray:
    """Apply CLAHE for local contrast enhancement."""
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)


def preprocess_pipeline(
    image: np.ndarray,
    max_dim: int = 1280,
    enhance: bool = True,
    normalize: bool = False
) -> np.ndarray:
    """Full preprocessing pipeline: resize -> enhance -> (normalize)."""
    image = resize_image(image, max_dim)
    if enhance:
        image = enhance_image(image)
    if normalize:
        image = normalize_image(image)
    return image


def pil_to_numpy(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to RGB numpy array."""
    return np.array(image.convert("RGB"))


def to_rgb_channels(image: np.ndarray) -> np.ndarray:
    """Normalize a numpy image to 3-channel RGB.

    Handles grayscale (H x W) and Alpha (H x W x 4) arrays that YOLO cannot
    process, returning an H x W x 3 array.
    """
    if image.ndim == 2:
        return np.stack([image] * 3, axis=-1)
    if image.ndim == 3:
        if image.shape[2] == 4:
            return image[..., :3]
        if image.shape[2] == 1:
            return np.concatenate([image] * 3, axis=-1)
        return image
    return image


def numpy_to_pil(image: np.ndarray) -> Image.Image:
    """Convert RGB numpy array to PIL Image."""
    if image.dtype == np.float32:
        image = denormalize_image(image)
    return Image.fromarray(image)


def prepare_for_inference(image: np.ndarray, input_size: Tuple[int, int] = (640, 640)) -> np.ndarray:
    """Resize and pad image for YOLO inference (letterbox)."""
    h, w = image.shape[:2]
    target_w, target_h = input_size
    
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    pad_top = (target_h - new_h) // 2
    pad_left = (target_w - new_w) // 2
    padded[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
    
    return padded