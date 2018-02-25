
import collections
import os
import nr.c4d.ui
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

  if key is None:
    key = lambda x: x

  DataNode = Node[collections.namedtuple('Data', 'path isdir data')]
  entries = {}

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


class FileList(nr.c4d.ui.native.BaseWidget):

  def __init__(self, layout='fit', id=None):
    super(FileList, self).__init__(id)
    self.layout = layout
    self._file_nodes = []

  def set_files(self, files, parent):
    files = sorted(files, key=lambda x: x.lower())
    self._file_nodes = file_tree(files, parent, True)

  def render(self, dialog):
    layout_flags = nr.c4d.ui.native.get_layout_flags(self.layout)
    dialog.GroupBegin(0, layout_flags, 1, 0)
    for node in self._file_nodes:
      depth = node.depth()
      dialog.AddStaticText(0, 0, name='  ' * depth + node['path'])
    dialog.GroupEnd()
