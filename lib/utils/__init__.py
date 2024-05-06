#!/usr/bin/env python3

import importlib
import logging
import platform
import random
import re
import time
from contextlib import contextmanager, nullcontext
from functools import lru_cache
from typing import Any, List, Optional
import numpy as np
import torch
from torch import Tensor, autocast
from torch.nn import functional
from torch.overrides import handle_torch_function, has_torch_function_variadic

logger = logging.getLogger(__name__)

@lru_cache
def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    
    if torch.backend.mps.is_available():
        return "mps"
    
    return "cpu"

@lru_cache
def get_default_dtype():
    if get_device() == "cuda":
        return torch.float16
    
    if get_device() == "mps":
        return torch.float16
    
    return torch.float32


@lru_cache
def get_hardware_description(device_type: str) -> str:
    desc = platform.platform()
    if device_type == "cuda":
        desc += "-" + torch.cuda.get_device_name(0)
        
    return desc

def get_obj_from_str(import_path: str, reload=False) -> Any:
    module_path, obj_name = import_path.rsplit(".", 1)
    if reload:
        module_imp = importlib.import_module(module_path)
        importlib.reload(module_imp)
    
    module = importlib.import_module(module_path, package=None)
    return getattr(module, obj_name)

def instantiate_from_config(config: dict) -> Any:
    if "target" not in config:
        if config == "__is_first_stage__":
            return None
        if config == "__is_unconditional__":
            return None
        
        raise KeyError("Expected key `target` to instantiate.")
    
    params = config.get("params", {})
    _cls = get_obj_from_str(config["target"])
    start = time.perf_counter()
    c = _cls(**params)
    end = time.perf_counter()
    logger.debug(f"Instantiation of {_cls} took {end-start} seconds")
    return c

@contextmanager
def platform_appropriate_autocast(precision="autocast", enabled=True):
    if precision == "autocast" and get_device() in ("cuda",):
        with autocast(get_device(), enabled=enabled):
            yield
    else:
        with nullcontext(get_device()):
            yield
            
def _fixed_layer_norm(
    input: Tensor, 
    normalized_shape: List[int],
    weight: Optional[Tensor] = None,
    bias: Optional[Tensor] = None,
    eps: float = 1e-5,
) -> Tensor:
    if has_torch_function_variadic(input, weight, bias):
        return handle_torch_function(
            _fixed_layer_norm,
            (input, weight, bias),
            input,
            normalized_shape,
            weight=weight,
            bias=bias,
            eps=eps,
        )
    return torch.layer_norm(
        input.contiguous(),
        normalized_shape,
        weight,
        bias,
        eps,
        torch.backends.cudnn.enabled,
    )
