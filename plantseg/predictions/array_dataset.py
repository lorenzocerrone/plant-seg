import numpy as np
import pytorch3dunet.augment.transforms as transforms
from pytorch3dunet.datasets.utils import get_slice_builder, calculate_stats, default_prediction_collate
from pytorch3dunet.unet3d.utils import get_logger
from torch.utils.data import Dataset

logger = get_logger('ArrayDataset')


class ArrayDataset(Dataset):
    """
    Based on pytorch-3dunet  AbstractHDF5Dataset
    https://github.com/wolny/pytorch-3dunet/blob/master/pytorch3dunet/datasets/hdf5.py

    Inference only implementation of torch.utils.data.Dataset
    """

    def __init__(self, raw,
                 slice_builder_config,
                 transformer_config,
                 mirror_padding=(16, 32, 32),
                 global_normalization=True,
                 verbose_logging=True,
                 **kwargs):
        """
        :param raw: numpy array containing the raw image
        :para'/home/adrian/workspace/ilastik-datasets/VolkerDeconv/train'm slice_builder_config: configuration of the SliceBuilder
        :param transformer_config: data augmentation configuration
        :param mirror_padding (int or tuple): number of voxels padded to each axis
        """
        self.slice_builder_config = slice_builder_config

        if mirror_padding is not None:
            if isinstance(mirror_padding, int):
                mirror_padding = (mirror_padding,) * 3
            else:
                assert len(mirror_padding) == 3, f"Invalid mirror_padding: {mirror_padding}"

        self.mirror_padding = mirror_padding

        self.raw = raw

        if global_normalization:
            stats = calculate_stats(self.raw)
        else:
            stats = {'pmin': None, 'pmax': None, 'mean': None, 'std': None}

        self.transformer = transforms.Transformer(transformer_config, stats)
        self.raw_transform = self.transformer.raw_transform()

        # 'test' phase used only for predictions so ignore the label dataset
        self.label = None
        self.weight_map = None

        # add mirror padding if needed
        if self.mirror_padding is not None:
            z, y, x = self.mirror_padding
            pad_width = ((z, z), (y, y), (x, x))
            if self.raw.ndim == 4:
                channels = [np.pad(r, pad_width=pad_width, mode='reflect') for r in self.raw]
                self.raw = np.stack(channels)
            else:
                self.raw = np.pad(self.raw, pad_width=pad_width, mode='reflect')

        # build slice indices for raw and label data sets
        slice_builder = get_slice_builder(self.raw, self.label, self.weight_map, slice_builder_config)
        self.raw_slices = slice_builder.raw_slices
        self.label_slices = slice_builder.label_slices
        self.weight_slices = slice_builder.weight_slices

        self.patch_count = len(self.raw_slices)

        if verbose_logging:
            logger.info(f'Number of patches: {self.patch_count}')

    def __getitem__(self, idx):
        if idx >= len(self):
            raise StopIteration

        # get the slice for a given index 'idx'
        raw_idx = self.raw_slices[idx]
        # get the raw data patch for a given slice
        raw_patch_transformed = self.raw_transform(self.raw[raw_idx])
        # discard the channel dimension in the slices: predictor requires only the spatial dimensions of the volume
        if len(raw_idx) == 4:
            raw_idx = raw_idx[1:]
        return raw_patch_transformed, raw_idx

    def __len__(self):
        return self.patch_count

    @classmethod
    def prediction_collate(cls, batch):
        """Default collate_fn. Override in child class for non-standard datasets."""
        return default_prediction_collate(batch)
