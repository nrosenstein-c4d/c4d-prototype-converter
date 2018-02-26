
import c4d
import os
import sys

__res__ = None
plugin_dir = None

def path(*parts):
  return os.path.normpath(os.path.join(plugin_dir, *parts))


def local(*parts, **kwargs):
  _stackdepth = kwargs.get('_stackdepth', 0)
  parent_dir = os.path.dirname(sys._getframe(_stackdepth+1).f_globals['__file__'])
  return os.path.normpath(os.path.join(parent_dir, *parts))


def bitmap(path):
  bmp = c4d.bitmaps.BaseBitmap()
  if bmp.InitWith(path)[0] != c4d.IMAGERESULT_OK:
    bmp = None
  return bmp
