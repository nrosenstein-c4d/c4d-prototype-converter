# The MIT License (MIT)
#
# Copyright (c) 2018 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import errno
import os
import weakref
from .generics import Generic


class nullable_ref(object):
  '''
  A weak-reference type that can represent #None.
  '''

  def __init__(self, obj):
    self.set(obj)

  def __repr__(self):
    return '<nullable_ref to {!r}>'.format(self())

  def __call__(self):
    if self._ref is not None:
      return self._ref()
    return None

  def __bool__(self):
    return self._ref is not None

  __nonzero__ = __bool__

  def set(self, obj):
    self._ref = weakref.ref(obj) if obj is not None else None


def makedirs(path, raise_on_exists=False):
  '''
  Like #os.makedirs(), but by default this function does not raise an
  exception if the directory already exists.
  '''

  try:
    os.makedirs(path)
  except OSError as exc:
    if raise_on_exists or exc.errno != errno.EEXIST:
      raise


class Node(object):
  """
  Generic tree node type.
  """

  __metaclass__ = Generic
  __generic_args__ = ['data_cls']

  def __init__(self, *args, **kwargs):
    if not self.__generic_bind__:
      raise TypeError('missing generic arguments for Node class')
    if self.data_cls is None:
      if args or kwargs:
        raise TypeError('{} takes no arguments'.format(type(self).__name__))
      self.data = None
    else:
      self.data = self.data_cls(*args, **kwargs)
    self.parent = nullable_ref(None)
    self.children = []

  def __repr__(self):
    return '<Node data={!r}>'.format(self.data)

  def __getitem__(self, key):
    if isinstance(self.data, dict):
      return self.data[key]
    return getattr(self.data, key)

  def __setitem__(self, key, value):
    if isinstance(self.data, dict):
      self.data[key] = value
    else:
      if hasattr(self.data, key):
        setattr(self.data, key, value)
      else:
        raise AttributeError('{} has no attribute {}'.format(
          type(self.data).__name__, key))

  def get(self, key, default=None):
    if isinstance(self.data, dict):
      return self.data.get(key, default)
    else:
      return getattr(self.data, key, default)

  def add_child(self, node):
    node.remove()
    node.parent.set(self)
    self.children.append(node)

  def remove(self):
    parent = self.parent()
    if parent:
      parent.children.remove(self)
    self.parent.set(None)

  def visit(self, func, with_root=True, post_order=False):
    if with_root and not post_order:
      func(self)
    for child in self.children:
      child.visit(func)
    if with_root and post_order:
      func(self)

  def depth(self, stop_cond=None):
    count = 0
    while True:
      self = self.parent()
      if not self: break
      if stop_cond is not None and stop_cond(self): break
      count += 1
    return count
