#!/usr/bin/env python3

def get_version():
    from importlib.metadata import PackageNotFoundError, version
    
    try:
        return version("pyimg")
    except PackageNotFoundError:
        return None