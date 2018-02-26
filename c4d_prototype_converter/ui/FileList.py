
import c4d
import collections
import os
from nr.c4d.ui.native import BaseWidget, get_layout_flags
from ..utils import Node


def path_parents(path):
  """
  A generator that returns *path* and all its parent directories.
  """

  yield path
  prev = None
  while True:
    path = os.path.dirname(path)
    if not path or prev == path: break  # Top of relative path or of filesystem
    yield path
    prev = path


def file_tree(items, parent=None, flat=False, key=None):
  """
  Produces a tree structure from a list of filenames. Returns a list of the
  root entries. If *flat* is set to #True, the returned list contains a flat
  version of all entries in the tree.
  """

  DataNode = Node[collections.namedtuple('Data', 'path isdir data')]
  entries = {}

  if key is None:
    key = lambda x: x

  items = ((os.path.normpath(key(x)), x) for x in items)
  if parent:
    items = [(os.path.relpath(k, parent), v) for k, v in items]

  if flat:
    order = []
  for filename, data in items:
    parent_entry = None
    for path in reversed(list(path_parents(filename))):
      entry = entries.get(path)
      if not entry:
        entry = DataNode(path, path!=filename, data)
        if parent_entry:
          parent_entry.add_child(entry)
        entries[path] = entry
        base = os.path.basename(path)
      parent_entry = entry
    if flat:
      order.append(entry)

  roots = (x for x in entries.values() if not x.parent)
  if flat:
    result = []
    [x.visit(lambda y: result.append(y)) for x in roots]
    return result
  else:
    return list(roots)


COLOR_BLUE = c4d.Vector(0.5, 0.6, 0.9)
COLOR_RED = c4d.Vector(0.9, 0.3, 0.3)
COLOR_YELLOW = c4d.Vector(0.9, 0.8, 0.6)


class FileList(BaseWidget):
  """
  Shows a list of files in a tree with the single highest directory first.
  If a file already exists, it will be rendered in red unless the *overwrite*
  flag is set in the widget. Additionally, files that are only written if
  they not already exist can be marked as such and are rendered in yellow.
  """

  def __init__(self, layout_flags='left,fit-y', id=None):
    super(FileList, self).__init__(id)
    self.layout_flags = layout_flags
    self._parent_path = None
    self._flat_nodes = []
    self._optional_file_ids = set()
    self._overwrite = False

  def set_files(self, files, parent, optional_file_ids):
    files = sorted(files.items(), key=lambda x: x[1].lower())
    self._parent_path = parent
    self._flat_nodes = file_tree(files, parent=parent, flat=True, key=lambda x: x[1])
    self._optional_file_ids = set(optional_file_ids)
    self.layout_changed()

  def set_overwrite(self, overwrite):
    self._overwrite = overwrite

  def render(self, dialog):
    layout_flags = get_layout_flags(self.layout_flags)
    dialog.GroupBegin(0, layout_flags, 1, 0)
    for node in self._flat_nodes:
      depth = node.depth()
      name = '  ' * depth + os.path.basename(node['path'])
      if node['isdir']:
        name += '/'
      widget_id = self.alloc_id()
      dialog.AddStaticText(widget_id, c4d.BFH_LEFT, name=name)
      full_path = os.path.join(self._parent_path, node['path'])
      if not node['isdir'] and os.path.isfile(full_path):
        if node['data'][0] in self._optional_file_ids:
          color = COLOR_BLUE
        elif self._overwrite:
          color = COLOR_YELLOW
        else:
          color = COLOR_RED
        dialog.set_color(widget_id, c4d.COLOR_TEXT, color)
    dialog.GroupEnd()
