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

    def __getattr__(self, key):
        if key == "_img":
            raise AttributeError()
        self._load_img()
        return getattr(self._img, key)
    
    def __setstate__(self, state):
        self.__dict__.update(state)
    
    def _load_img(self):
        if self._img is None:
            from PIL import Image, ImageOps
            
            if self._lazy_filepath:
                self._img = Image.open(self._lazy_filepath)
                logger.debug(
                    f"Loaded input 🖼  of size {self._img.size} from {self._lazy_filepath}"
                )
            elif self._lazy_url:
                import requests
                
                self._img = Image.open(
                    BytesIO(
                        requests.get(self._lazy_url, stream=True, timeout=60).content
                    )
                )
                logger.debug(
                    f"Loaded input 🖼  of size {self._img.size} from {self._lazy_filepath}"
                )
            else:
                raise ValueError("You must specify a url or filepath")

            self._img = ImageOps.exif_transpose(self._img)
    
    @classmethod
    def __get_pydantic_core_schema(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(value: Any) -> "LazyLoadingImage":
            from PIL import Image, UnidentifiedImageError
            
            if isinstance(value, cls):
                return value
            if isinstance(value, Image.Image):
                return cls(img=value)
            if isinstance(value, str):
                if "." in value [:1000]:
                    try:
                        return cls(filepath=value)
                    except FileNotFoundError as e:
                        raise ValueError(str(e))
                try:
                    return cls(b64=value)
                except UnidentifiedImageError:
                    msg = "base64 string was not recognized as a valid image type"
            
            if isinstance(value, dict):
                return cls(**value)
            
            msg = "Image value must be either a LazyLoadingImage, PIL.Image.Image or Base64 string"
            raise ValueError(msg)

        def handle_b64(value: Any) -> "LazyLoadingImage":
            if isinstance(value, str):
                return cls(b64=value)
            
            msg = "Image value must be either a LazyLoadingImage, PIL.Image.Image or a Base64 string"
            raise ValueError(msg)
            
            return core_schema.json_or_python_schema(
                json_schema=core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_before_validator_function(
                            handle_b64, core_schema.any_schema()
                        ),
                    ]
                ),
                python_schema=core_schema.no_info_before_validator_function(
                    validate, core_schema.any_schema()
                ),
                serialization=core_schema.plain_serializer_function_ser_schema(str),
            ) 
        
        @staticmethod
        def save_image_as_base64(image: "Image.Image") -> str:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            return base64.b64encode(img_bytes).decode()
        
        @staticmethod
        def load_image_from_base64(image_str: str) -> "Image.Image":
            from PIL import Image
            
            img_bytes = base64.b64decode(image_str)
            return Image.open(io.BytesIO(img_bytes))
        
        def as_base64(self):
            self._load_img()
            return self.save_image_as_base64(self._img)
        
        def as_pillow(self):
            self._load_img()
            return self._img
        
        def __str__(self):
            return self.as_base64()
        
        def __repr__(self):
            try:
                return f"<LazyLoadingImage filepath={self._lazy_filepath} url={self._lazy_url}>"
            except Exception as e:
                return f"<LazyLoadingImage RENDER EXCEPTION*(e)>"

        
class ControlInput(BaseModel):
    mode: str
    image: LazyLoadingImage | None = None
    image_raw: LazyLoadingImage | None = None
    strength: float = Field(1, ge=0, le=1000)
    
    @field_validator("image_raw")
    def image_raw_validate(cls, v, info: core_schema.FieldValidationInfo):
        if info.data.get("image") is not None and v is not None:
            raise ValueError("You cannot specify both image and image_raw")

        return v
    
    @field_validator("mode")
    def mode_validator(cls, v):
        if v not in config.CONTROL_CONFIG_SHORTCUTS:
            valid_modes = list(config.CONTROL_CONFIG_SHORTCUTS.keys())
            valid_modes = ", ".join(valid_modes)
            msg = f"Invalid controlnet mode: '{v}'. Valid modes are: {valid_modes}"
            raise ValueError(msg)
        return v
    
class WeightedPrompt(BaseModel):
    text: str
    weight: float = Field(1, ge=0)
    
    def __repr__(self):
        return f"{self.weight}*({self.text})"

class MaskMode(str, Enum):
    REPLACE = "replace"
    KEEP = "keep"
    
MaskInput = MaskMode | str
PromptInput = str | WeightedPrompt | list[WeightedPrompt] | list[str] | None
InpaintMethod = Literal["finetune", "control"]

class ImagePrompt(BaseModel, protected_namespace=()):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    prompt: List[WeightedPrompt] = Field(default=None, validate_default=True)
    
    negative_prompt: List[WeightedPrompt] = Field(
        default_factory=list, validate_default=True
    )
    
    prompt_strength: float = Field(default=7.5, le=50, ge=-50, validate_default=True)
    
    init_image: LazyLoadingImage | None = Field(
        None, description="base64 encoded image", validate_default=True
    )
    
    init_image_strength: float | None = Field(
        ge=0, le=1, default=None, validate_default=True
    )
    
    image_prompt: List[LazyLoadingImage] | None = Field(None, validate_default=True)
    
    image_prompt_strength: float = Field(ge=0, le=1, default=0.0)
    
    control_inputs: List[ControlInput] = Field(
        default_factory=list, validate_default=True
    )