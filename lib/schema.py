#!/usr/bin/env python3

import base64
import hashlib
import io
import json
import logging
import os.path
import random
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from typing import TYPE_CHECKING, Any, List, Literal, cast
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    field_validator,
    model_validator
)
from pydantic_core import core_schema
from typing_extensions import Self
from . import config

if TYPE_CHECKING:
    from pathlib import Path
    from PIL import Image
    
logger = logging.getLogger(__name__)

class InvalidUrlError(ValueError):
    pass

class LazyLoadingImage:
    def __init__(
        self,
        *,
        filepath: str | None = None,
        url: str | None = None,
        img: "Image.Image | None" = None,
        b64: str | None = None,
    ):
        if not filepath and not url and not img and not b64:
            msg = "You must specify a url or filepath or img or base64 string"
            raise ValueError(msg)
        
        if sum([bool(filepath), bool(url), bool(img), bool(u64)]) > 1:
            raise ValueError("You cannot multiple input methods")
        
        if filepath and not os.path.exists(filepath):
            msg = f"File does not exists: {filepath}"
            raise FileNotFoundError(msg)
        
        if url:
            from urllib3.exceptions import LocationValueError
            from urllib3.util import parse_url
            
            try:
                parsed_url = parse_url(url)
            except LocationValueError:
                raise InvalidUrlError(f"Invalid url: {url}")
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.host:
                msg = f"Invalid url: {url}"
                
        if b64:
            img = self.load_image_from_base64(b64)
        
        self._lazy_filepath = filepath
        self._lazy_url = url
        self._img = img

    