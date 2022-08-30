import numpy as np
from scipy.ndimage import zoom
from skimage.filters import median
from skimage.morphology import disk, ball
from vigra import gaussianSmoothing


def compute_scaling_factor(input_voxel_size, output_voxel_size):
    scaling = [i_size / o_size for i_size, o_size in zip(input_voxel_size, output_voxel_size)]
    return scaling


def compute_scaling_voxelsize(input_voxel_size, scaling_factor):
    output_voxel_size = [i_size / s_size for i_size, s_size in zip(input_voxel_size, scaling_factor)]
    return output_voxel_size


def scale_image_to_voxelsize(image, input_voxel_size, output_voxel_size, order=0):
    factor = compute_scaling_factor(input_voxel_size, output_voxel_size)
    return image_rescale(image, factor, order=order)


def image_rescale(image, factor, order):
    if np.array_equal(factor, [1., 1., 1.]):
        return image
    else:
        return zoom(image, zoom=factor, order=order)


def image_median(image, radius):
    if image.shape[0] == 1:
        shape = image.shape
        median_image = median(image[0], disk(radius))
        return median_image.reshape(shape)
    else:
        return median(image, ball(radius))


def image_gaussian_smoothing(image, sigma):
    image = image.astype('float32')
    max_sigma = (np.array(image.shape) - 1) / 3
    sigma = np.minimum(max_sigma, np.ones(max_sigma.ndim) * sigma)
    return gaussianSmoothing(image, sigma)


def image_crop(image, crop_str):
    crop_str = crop_str.replace('[', '').replace(']', '')
    slices = tuple((slice(*(int(i)
                            if i else None for i in part.strip().split(':')))
                    if ':' in part else int(part.strip())) for part in crop_str.split(','))
    return image[slices]


def fix_input_shape(data):
    if data.ndim == 2:
        return data.reshape(1, data.shape[0], data.shape[1])

    elif data.ndim == 3:
        return data

    elif data.ndim == 4:
        return data[0]

    else:
        raise RuntimeError(f"Expected input data to be 2d, 3d or 4d, but got {data.ndim}d input")


def normalize_01(data):
    return (data - np.min(data)) / (np.max(data) - np.min(data) + 1e-12).astype('float32')
