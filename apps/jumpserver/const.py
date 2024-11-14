# -*- coding: utf-8 -*-
#
import os

from .conf import ConfigManager

__all__ = ['BASE_DIR', 'PROJECT_DIR', 'VERSION', 'CONFIG']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
VERSION = '3.10.15-lts'
CONFIG = ConfigManager.load_user_config()


