#!/usr/bin/env python3

from functools import lru_cache

def get_debug_info():
    import os.path
    import platform
    import sys
    import psutil
    import torch