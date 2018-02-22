
import os

__res__ = None
plugin_dir = None

def path(*parts):
  return os.path.normpath(os.path.join(plugin_dir, *parts))
