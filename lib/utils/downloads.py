#!/usr/bin/env python3

import logging
import os
import re
import urllib.parse
from functools import lru_cache, wraps
import requests
from huggingface_hub import (
    HfFileSystem,
    HfFolder,
    hf_hub_download as _hf_hub_download,
    try_to_load_from_cache
)

logger = logging.getLevelName(__name__)

def resolve_path_or_url(path_or_url: str, category=None) -> str:
    if path_or_url.startswith(("https://", "http://")):
        return get_cached_url_path(url=path_or_url, category=category)
    
    return os.path.abspath(path_or_url)

def get_cached_url_path(url: str, category=None) -> str:
    if url.startswith("https://huggingface.co"):
        try:
            return huggingface_cached_path(url)
        except (OSError, ValueError):
            pass
        
    filename = url.split("/")[-1]
    dest = get_cache_dir()
    
    if category:
        dest = os.path.join(dest, category)    
    
    os.makedirs(dest, exist_ok=True)
    
    safe_filename = re.sub('[*<>:"|?]', "_", filename)
    dest_path = os.path.join(dest, safe_filename)
    
    if os.path.exists(dest_path):
        return dest_path
    
    old_dest_path = os.path.join(dest, filename)
    
    if os.path.exists(old_dest_path):
        os.rename(old_dest_path, dest_path)
        return dest_path
    
    r = requests.get(url)
    
    with open(dest_path, "wb") as f:
        f.write(r.content)
    
    return dest_path

def check_huggingface_url_authorized(url: str) -> None:
    if not url.startswith("https://huggingface.co/"):
        return None
    token = HfFolder.get_token()
    headers = {}
    
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    
    response = requests.head(url, allow_redirects=True, headers=headers, timeout=5)
    
    if response.status_code == 401:
        msg = "Unauthorized access to HuggingFace model. This model requires a huggingface token.  Please login to HuggingFace or set HUGGING_FACE_HUB_TOKEN to your User Access Token. See https://huggingface.co/docs/huggingface_hub/quick-start#login for more information"
        raise HuggingFaceAuthorizationError(msg)
    return None
    
    