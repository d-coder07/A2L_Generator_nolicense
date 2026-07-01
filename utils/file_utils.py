"""Path handling and validation."""

import os


def is_valid_file(path):
    return os.path.isfile(path)
