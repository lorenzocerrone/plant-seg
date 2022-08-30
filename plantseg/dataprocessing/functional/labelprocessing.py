import numpy as np
from skimage import measure


def relabel_segmentation(segmentation_image):
    """
    Relabel contiguously a segmentation image, non-touching instances with same id will be relabeled differently.
    To be noted that measure.label is different from ndimage.label
    """
    return measure.label(segmentation_image)


def set_background_to_value(segmentation_image, value: int = 0):
    segmentation_image += 1
    idx, counts = np.unique(segmentation_image, return_counts=True)
    bg_idx = idx[np.argmax(counts)]
    return np.where(segmentation_image == bg_idx, value, segmentation_image)

