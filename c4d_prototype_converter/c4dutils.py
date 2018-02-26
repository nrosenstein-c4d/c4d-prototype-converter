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

import collections
import c4d

try: from cStringIO import StringIO
except ImportError: from StringIO import StringIO

from . import generics


@generics.specialize_hash_function(c4d.DescID)
def hash_descid(x):
  return hash(tuple(
    (l.id, l.dtype, l.creator) for l in (x[i] for i in xrange(x.GetDepth()))
  ))


def unicode_refreplace(ustring):
  '''
  Replaces all non-ASCII characters in the supplied unicode string with
  Cinema 4D stringtable unicode escape sequences. Returns a binary string.
  '''

  if not isinstance(ustring, unicode):
    ustring = ustring.decode('utf8')

  fp = StringIO()
  for char in ustring:
    try:
      if char in '\n\r\t\b':
        raise UnicodeEncodeError
      char = char.encode('ascii')
    except UnicodeEncodeError:
      char = '\\u' + ('%04x' % ord(char)).upper()
    fp.write(char)

  return fp.getvalue()


def get_subcontainer(bc, sub_id, create=False):
  if not has_subcontainer(bc, sub_id) and create:
    bc.SetContainer(sub_id, c4d.BaseContainer())
    assert has_subcontainer(bc, sub_id)
  return bc.GetContainerInstance(sub_id)


def has_subcontainer(bc, sub_id):
  return bc.GetType(sub_id) == c4d.DA_CONTAINER
