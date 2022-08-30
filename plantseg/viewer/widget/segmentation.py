from concurrent.futures import Future
from functools import partial
from typing import Union, Tuple, Callable

from magicgui import magicgui
from napari.layers import Labels, Image, Layer
from napari.types import LayerDataTuple
from enum import Enum

from plantseg.dataprocessing.functional.advanced_dataprocessing import fix_over_under_segmentation_from_nuclei
from plantseg.dataprocessing.functional.dataprocessing import normalize_01
from plantseg.viewer.widget.utils import start_threading_process, build_nice_name, layer_properties
from plantseg.segmentation.functional import gasp, multicut, dt_watershed, mutex_ws
from plantseg.segmentation.functional import lifted_multicut_from_nuclei_segmentation, lifted_multicut_from_nuclei_pmaps


class ClusteringOptions(Enum):
    gasp = gasp
    multicut = multicut
    mutex_ws = mutex_ws


def _generic_clustering(image: Image, labels: Labels,
                        beta: float = 0.5,
                        minsize: int = 100,
                        name: str = 'GASP',
                        agg_func: Callable = gasp) -> Future[LayerDataTuple]:
    out_name = build_nice_name(image.name, name)
    inputs_names = (image.name, labels.name)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image.scale,
                                    metadata=image.metadata)
    layer_type = 'labels'
    step_kwargs = dict(beta=beta, post_minsize=minsize)

    return start_threading_process(agg_func,
                                   runtime_kwargs={'boundary_pmaps': image.data,
                                                   'superpixels': labels.data},
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name=f'{name} Clustering',
                                   )


@magicgui(call_button='Run Clustering',
          image={'label': 'Image',
                 'tooltip': 'Raw or boundary image to use as input for clustering.'},
          _labels={'label': 'Over-segmentation',
                   'tooltip': 'Over-segmentation labels layer to use as input for clustering.'},
          mode={'label': 'Aggl. Mode',
                'choices': ['GASP', 'MutexWS', 'MultiCut'],
                'tooltip': 'Select which agglomeration algorithm to use.'
                },
          beta={'label': 'Under/Over segmentation factor',
                'tooltip': 'A low value will increase under-segmentation tendency '
                           'and a large value increase over-segmentation tendency.',
                'widget_type': 'FloatSlider', 'max': 1., 'min': 0.},
          minsize={'label': 'Min-size',
                   'tooltip': 'Minimum segment size allowed in voxels.'})
def widget_agglomeration(image: Image, _labels: Labels,
                         mode: str = "GASP",
                         beta: float = 0.6,
                         minsize: int = 100) -> Future[LayerDataTuple]:
    if mode == 'GASP':
        func = gasp

    elif mode == 'MutexWS':
        func = mutex_ws

    else:
        func = multicut

    return _generic_clustering(image, _labels, beta=beta, minsize=minsize, name=mode, agg_func=func)


@magicgui(call_button='Run Lifted MultiCut',
          image={'label': 'Image',
                 'tooltip': 'Raw or boundary image to use as input for clustering.'},
          nuclei={'label': 'Nuclei',
                  'tooltip': 'Nuclei binary predictions or Nuclei segmentation.'},
          _labels={'label': 'Over-segmentation',
                   'tooltip': 'Over-segmentation labels layer to use as input for clustering.'},
          beta={'label': 'Under/Over segmentation factor',
                'tooltip': 'A low value will increase under-segmentation tendency '
                           'and a large value increase over-segmentation tendency.',
                'widget_type': 'FloatSlider', 'max': 1., 'min': 0.},
          minsize={'label': 'Min-size',
                   'tooltip': 'Minimum segment size allowed in voxels.'})
def widget_lifted_multicut(image: Image,
                           nuclei: Layer,
                           _labels: Labels,
                           beta: float = 0.5,
                           minsize: int = 100) -> Future[LayerDataTuple]:
    if isinstance(nuclei, Image):
        lmc = lifted_multicut_from_nuclei_pmaps
        extra_key = 'nuclei_pmaps'
    elif isinstance(nuclei, Labels):
        lmc = lifted_multicut_from_nuclei_segmentation
        extra_key = 'nuclei_seg'
    else:
        raise ValueError(f'{nuclei} must be either an image or a labels layer')

    out_name = build_nice_name(image.name, 'LiftedMultiCut')
    inputs_names = (image.name, nuclei.name, _labels.name)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image.scale,
                                    metadata=image.metadata)
    layer_type = 'labels'
    step_kwargs = dict(beta=beta, post_minsize=minsize)

    return start_threading_process(lmc,
                                   runtime_kwargs={'boundary_pmaps': image.data,
                                                   extra_key: nuclei.data,
                                                   'superpixels': _labels.data},
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name=f'Lifted Multicut Clustering',
                                   )


def dtws_wrapper(boundary_pmaps,
                 stacked: bool = True,
                 threshold: float = 0.5,
                 min_size: int = 100,
                 sigma_seeds: float = .2,
                 sigma_weights: float = 2.,
                 alpha: float = 1.,
                 pixel_pitch: Tuple[int, int, int] = (1, 1, 1),
                 apply_nonmax_suppression: bool = False,
                 nuclei: bool = False):
    if nuclei:
        boundary_pmaps = normalize_01(boundary_pmaps)
        boundary_pmaps = 1. - boundary_pmaps
        mask = boundary_pmaps < threshold
    else:
        mask = None

    return dt_watershed(boundary_pmaps=boundary_pmaps,
                        threshold=threshold,
                        min_size=min_size,
                        stacked=stacked,
                        sigma_seeds=sigma_seeds,
                        sigma_weights=sigma_weights,
                        alpha=alpha,
                        pixel_pitch=pixel_pitch,
                        apply_nonmax_suppression=apply_nonmax_suppression,
                        mask=mask
                        )


@magicgui(call_button='Run Watershed',
          image={'label': 'Image',
                 'tooltip': 'Raw or boundary image to use as input for Watershed.'},
          stacked={'label': 'Stacked',
                   'tooltip': 'Define if the Watershed will run slice by slice (faster) '
                              'or on the full volume (slower).',
                   'widget_type': 'RadioButtons',
                   'orientation': 'horizontal',
                   'choices': ['2D', '3D']},
          threshold={'label': 'Threshold',
                     'tooltip': 'A low value will increase over-segmentation tendency '
                                'and a large value increase under-segmentation tendency.',
                     'widget_type': 'FloatSlider', 'max': 1., 'min': 0.},
          min_size={'label': 'Min-size',
                    'tooltip': 'Minimum segment size allowed in voxels.'},
          sigma_seeds={'label': 'Sigma seeds'},
          sigma_weights={'label': 'Sigma weights'},
          alpha={'label': 'Alpha'},
          use_pixel_pitch={'label': 'Use pixel pitch'},
          pixel_pitch={'label': 'Pixel pitch'},
          apply_nonmax_suppression={'label': 'Apply nonmax suppression'},
          nuclei={'label': 'Is image Nuclei'}

          )
def widget_dt_ws(image: Image,
                 stacked: str = '2D',
                 threshold: float = 0.5,
                 min_size: int = 100,
                 sigma_seeds: float = .2,
                 sigma_weights: float = 2.,
                 alpha: float = 1.,
                 use_pixel_pitch: bool = False,
                 pixel_pitch: Tuple[int, int, int] = (1, 1, 1),
                 apply_nonmax_suppression: bool = False,
                 nuclei: bool = False) -> Future[LayerDataTuple]:
    out_name = build_nice_name(image.name, 'dtWS')
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image.scale,
                                    metadata=image.metadata)
    layer_type = 'labels'

    stacked = False if stacked == '3D' else True
    pixel_pitch = pixel_pitch if use_pixel_pitch else None
    step_kwargs = dict(threshold=threshold,
                       min_size=min_size,
                       stacked=stacked,
                       sigma_seeds=sigma_seeds,
                       sigma_weights=sigma_weights,
                       alpha=alpha,
                       pixel_pitch=pixel_pitch,
                       apply_nonmax_suppression=apply_nonmax_suppression,
                       nuclei=nuclei)

    return start_threading_process(dtws_wrapper,
                                   runtime_kwargs={'boundary_pmaps': image.data},
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name=f'Watershed Segmentation',
                                   )


@magicgui(call_button='Run Watershed',
          image={'label': 'Image',
                 'tooltip': 'Raw or boundary image to use as input for Watershed.'},
          stacked={'label': 'Stacked',
                   'tooltip': 'Define if the Watershed will run slice by slice (faster) '
                              'or on the full volume (slower).',
                   'widget_type': 'RadioButtons',
                   'orientation': 'horizontal',
                   'choices': ['2D', '3D']},
          threshold={'label': 'Threshold',
                     'tooltip': 'A low value will increase over-segmentation tendency '
                                'and a large value increase under-segmentation tendency.',
                     'widget_type': 'FloatSlider', 'max': 1., 'min': 0.},
          min_size={'label': 'Min-size',
                    'tooltip': 'Minimum segment size allowed in voxels.'},
          )
def widget_simple_dt_ws(image: Image,
                        stacked: str = '2D',
                        threshold: float = 0.5,
                        min_size: int = 100) -> Future[LayerDataTuple]:
    out_name = build_nice_name(image.name, 'dtWS')
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image.scale,
                                    metadata=image.metadata)
    layer_type = 'labels'

    stacked = False if stacked == '3D' else True
    step_kwargs = dict(threshold=threshold,
                       min_size=min_size,
                       stacked=stacked,
                       pixel_pitch=None)

    return start_threading_process(dtws_wrapper,
                                   runtime_kwargs={'boundary_pmaps': image.data},
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name=f'Watershed Segmentation',
                                   )


@magicgui(call_button='Run Segmentation Fix from Nuclei',
          cell_segmentation={'label': 'Cell Segmentation'},
          nuclei_segmentation={'label': 'Nuclei Segmentation'},
          boundary_pmaps={'label': 'Boundary Image'},
          threshold_merge={'label': 'Threshold merge'},
          threshold_split={'label': 'Threshold split'})
def widget_fix_over_under_segmentation_from_nuclei(cell_segmentation: Labels,
                                                   nuclei_segmentation: Labels,
                                                   boundary_pmaps: Union[None, Image],
                                                   threshold_merge=0.33,
                                                   threshold_split=0.66) -> Future[LayerDataTuple]:
    out_name = build_nice_name(cell_segmentation.name, 'NucleiSegFix')

    if boundary_pmaps is not None:
        inputs_names = (cell_segmentation.name, nuclei_segmentation.name, boundary_pmaps.name)
        func_kwargs = {'cell_seg': cell_segmentation.data,
                       'nuclei_seg': nuclei_segmentation.data,
                       'boundary': boundary_pmaps.data}
    else:
        inputs_names = (cell_segmentation.name, nuclei_segmentation.name)
        func_kwargs = {'cell_seg': cell_segmentation.data,
                       'nuclei_seg': nuclei_segmentation.data}

    layer_kwargs = layer_properties(name=out_name,
                                    scale=cell_segmentation.scale,
                                    metadata=cell_segmentation.metadata)
    layer_type = 'labels'
    step_kwargs = dict(threshold_merge=threshold_merge, threshold_split=threshold_split)

    return start_threading_process(fix_over_under_segmentation_from_nuclei,
                                   runtime_kwargs=func_kwargs,
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name=f'Fix Over / Under segmentation',
                                   )
