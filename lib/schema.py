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