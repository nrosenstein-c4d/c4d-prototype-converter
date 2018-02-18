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

import types


class Generic(type):
  """
  Metaclass that can be used for classes that need one or more datatypes
  pre-declared to function properly. The datatypes must be declared using
  the `__generic_args__` member and passed to the classes' `__getitem__()`
  operator to bind the class to these arguments.

  A generic class constructor may check it's `__generic_bind__` member to
  see if its generic arguments are bound or not.
  """

  def __init__(cls, *args, **kwargs):
    if not hasattr(cls, '__generic_args__'):
      raise TypeError('{}.__generic_args__ is not set'.format(cls.__name__))
    had_optional = False
    for index, item in enumerate(cls.__generic_args__):
      if not isinstance(item, tuple):
        item = (item,)
      arg_name = item[0]
      arg_default = item[1] if len(item) > 1 else NotImplemented
      if arg_default is NotImplemented and had_optional:
        raise ValueError('invalid {}.__generic_args__, default argument '
          'followed by non-default argument "{}"'
          .format(cls.__name__, arg_name))
      cls.__generic_args__[index] = (arg_name, arg_default)
    super(Generic, cls).__init__(*args, **kwargs)
    if not hasattr(cls, '__generic_bind__'):
      cls.__generic_bind__ = None
    else:
      assert len(cls.__generic_args__) == len(cls.__generic_bind__)
      for i in xrange(len(cls.__generic_args__)):
        value = cls.__generic_bind__[i]
        if isinstance(value, types.FunctionType):
          value = staticmethod(value)
        setattr(cls, cls.__generic_args__[i][0], value)

  def __getitem__(cls, args):
    cls = getattr(cls, '__generic_base__', cls)
    if not isinstance(args, tuple):
      args = (args,)
    if len(args) > cls.__generic_args__:
      raise TypeError('{} takes at most {} generic arguments ({} given)'
        .format(cls.__name__, len(cls.__generic_args__), len(args)))
    # Find the number of required arguments.
    for index in xrange(len(cls.__generic_args__)):
      if cls.__generic_args__[index][1] != NotImplemented:
        break
    else:
      index = len(cls.__generic_args__)
    min_args = index
    if len(args) < min_args:
      raise TypeError('{} takes at least {} generic arguments ({} given)'
        .format(cls.__name__, min_args, len(args)))
    # Bind the generic arguments.
    bind_data = []
    for index in xrange(len(cls.__generic_args__)):
      arg_name, arg_default = cls.__generic_args__[index]
      if index < len(args):
        arg_value = args[index]
      else:
        assert arg_default is not NotImplemented
        arg_value = arg_default
      bind_data.append(arg_value)
    type_name = '{}[{}]'.format(cls.__name__, ', '.join(repr(x) for x in bind_data))
    data = {
      '__generic_bind__': bind_data,
      '__generic_base__': cls
    }
    return type(type_name, (cls,), data)


class BaseHashDict(object):
  """
  Allows using a different hash key for the key objects in the dictionary.
  """

  __metaclass__ = Generic
  __generic_args__ = ['key_hash']

  class KeyWrapper(object):
    def __init__(self, key, hash_func):
      self.key = key
      self.hash_func = hash_func
    def __repr__(self):
      return repr(self.key)
    def __hash__(self):
      return self.hash_func(self.key)
    def __eq__(self, other):
      return self.key == other.key
    def __ne__(self, other):
      return self.key != other.key

  def __init__(self):
    if not self.__generic_bind__:
      raise TypeError('BaseHashDict object must be bound to generic arguments')
    self._dict = {}

  def __repr__(self):
    return repr(self._dict)

  def __getitem__(self, key):
    key = self.KeyWrapper(key, self.key_hash)
    return self._dict[key]

  def __setitem__(self, key, value):
    key = self.KeyWrapper(key, self.key_hash)
    self._dict[key] = value

  def __delitem__(self, key):
    key = self.KeyWrapper(key, self.key_hash)
    del self._dict[key]

  def __iter__(self):
    return self.iterkeys()

  def __contains__(self, key):
    return self.KeyWrapper(key, self.key_hash) in self._dict

  def items(self):
    return list(self.iteritems())

  def keys(self):
    return list(self.iterkeys())

  def values(self):
    return self._dict.values()

  def iteritems(self):
    for key, value in self._dict.iteritems():
      yield key.key, value

  def iterkeys(self):
    for key in self._dict.keys():
      yield key.key

  def itervalues(self):
    return self._dict.itervalues()

  def get(self, key, *args):
    key = self.KeyWrapper(key, self.key_hash)
    return self._dict.get(key, *args)

  def setdefault(self, key, value):
    key = self.KeyWrapper(key, self.key_hash)
    return self._dict.setdefault(key, value)


hash_function_map = {}


def specialize_hash_function(type):
  """
  Decorator for a function that is a hash function that specializes on the
  specified *type* (without its subclasses!).
  """

  def decorator(func):
    hash_function_map[type] = func
    return func
  return decorator


HashDict = BaseHashDict[lambda v: (hash_function_map.get(type(v), hash))(v)]
