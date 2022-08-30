from concurrent.futures import Future
from functools import partial
from typing import Callable, Tuple

from napari.qt.threading import thread_worker
from napari.utils.notifications import show_info

from plantseg.viewer.dag_handler import dag_manager


def identity(x):
    return x


def start_threading_process(func: Callable,
                            runtime_kwargs: dict,
                            statics_kwargs: dict,
                            out_name: str,
                            input_keys: Tuple[str, ...],
                            layer_kwarg: dict,
                            layer_type: str = 'image',
                            step_name: str = '',
                            skip_dag: bool = False) -> Future:

    runtime_kwargs.update(statics_kwargs)
    thread_func = thread_worker(partial(func, **runtime_kwargs))
    future = Future()

    def on_done(result):
        show_info(f'Napari - PlantSeg info: widget {step_name} computation complete')
        _func = func if not skip_dag else identity
        dag_manager.add_step(_func, input_keys=input_keys,
                             output_key=out_name,
                             static_params=statics_kwargs,
                             step_name=step_name)
        result = result, layer_kwarg, layer_type
        future.set_result(result)

    worker = thread_func()
    worker.returned.connect(on_done)
    worker.start()
    show_info(f'Napari - PlantSeg info: widget {step_name} computation started')
    return future


def layer_properties(name, scale, metadata: dict = None):
    keys_to_save = {'original_voxel_size', 'voxel_size_unit', 'root_name'}
    if metadata is not None:
        _new_metadata = {key: metadata[key] for key in keys_to_save if key in metadata}
    else:
        _new_metadata = {}
    return {'name': name, 'scale': scale, 'metadata': _new_metadata}


def _find_version(old_suffix, new_suffix):
    s_idx = old_suffix.find(new_suffix)
    if s_idx != -1:
        v_idx = s_idx + len(new_suffix)
        old_suffix, current_version = old_suffix[:v_idx], old_suffix[v_idx:]

        current_version = 0 if current_version == '' else int(current_version[1:-1])
        current_version += 1
        new_version = f'[{current_version}]'
        return old_suffix, new_version

    return f'{old_suffix}_{new_suffix}', ''


def build_nice_name(base, new_suffix):
    if base.find('_') == -1:
        return f'{base}_{new_suffix}'

    *base_without_suffix, old_suffix = base.split('_')
    base_without_suffix = '_'.join(base_without_suffix)

    new_suffix, version = _find_version(old_suffix, new_suffix)
    return f'{base_without_suffix}_{new_suffix}{version}'
