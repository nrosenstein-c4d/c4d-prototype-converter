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
"""
This module implements the core of converting Python scripts for the
Cinema 4D Script Manager, Python Generator or Expression Tags to actual
Python Plugins.
"""

from lib2to3.fixer_base import BaseFix
from lib2to3.fixer_util import Leaf, Node, find_indentation
from lib2to3.pgen2 import token
from lib2to3.pygram import python_symbols
from lib2to3 import refactor


class RefactoringTool(refactor.RefactoringTool):

  def get_fixers(self):
    pre_order_fixers = []
    post_order_fixers = []
    for fixer_cls in self.fixers:
      fixer = fixer_cls(self.options, self.fixer_log)
      if fixer.order == 'pre':
        pre_order_fixers.append(fixer)
      elif fixer.order == 'post':
        post_order_fixers.append(fixer)
      else:
        raise refactor.FixerError('Illegal fixer order: {!r}'.format(fixer.order))
    key_func = lambda x: x.run_order
    pre_order_fixers.sort(key=key_func)
    post_order_fixers.sort(key=key_func)
    return (pre_order_fixers, post_order_fixers)


class DelayBindBaseFix(BaseFix):

  def __init__(self):
    self.options = None
    self.log = None

  def __call__(self, options, log):
    super(DelayBindBaseFix, self).__init__(options, log)
    return self


class FixFunctionDef(DelayBindBaseFix):
  """
  Used to adapt a function definition by changing its name and parameter
  list. Additionally, *remove* can be set to #True in order to remove any
  matching occurences and store them in the #results list instead.
  """

  PATTERN = "funcdef< 'def' name='{}' any* >"

  def __init__(self, funcname, newname, pre_params=None, post_params=None,
               remove=False, add_statement=None):
    super(FixFunctionDef, self).__init__()
    self.PATTERN = self.PATTERN.format(funcname)
    self.funcname = funcname
    self.newname = newname
    self.pre_params = pre_params or []
    self.post_params = post_params or []
    self.remove = remove
    self.add_statement = add_statement
    self.results = []

  def transform(self, node, results):
    indent = None
    for child in node.children:
      if isinstance(child, Node) and child.type == python_symbols.suite:
        indent = find_indentation(child)
      if isinstance(child, Leaf) and child.type == token.NAME and child.value == self.funcname:
        child.value = self.newname
      elif isinstance(child, Node) and child.type == python_symbols.parameters:
        pre_params = []
        for param in self.pre_params:
          pre_params.append(Leaf(token.NAME, param))
          pre_params.append(Leaf(token.COMMA, ', '))
        child.children[1:1] = pre_params
        post_params = []
        for param in self.post_params:
          post_params.append(Leaf(token.COMMA, ','))
          post_params.append(Leaf(token.NAME, param))
        child.children[-1:-1] = post_params
        if child.children[-2].type == token.COMMA:
          child.children.pop(-2)
        child.changed()
    if self.add_statement:
      node.children.append(Leaf(0, indent + self.add_statement.rstrip() + '\n'))
    if self.remove:
      self.results.append(node)
      node.replace([])
      return None
    else:
      return node


def refactor_expression_script(code, kind):
  """
  Refactors Python code that is used in Python Generator or Expression Tag.
  Returns a tuple of two strings -- the first being *code* without the
  functions that are moved to member functions and the second being the
  refactored member functions (indentation unchanged).

  The *kind* must be either the string `'ObjectData'` or `'TagData'`.
  """

  fixers = {
    'message': FixFunctionDef('message', 'Message', ['self', 'op'], add_statement='return True', remove=True)
  }
  if kind == 'ObjectData':
    fixers['main'] = FixFunctionDef('main', 'GetVirtualObjects', ['self', 'op', 'hh'], remove=True)
  elif kind == 'TagData':
    fixers['main'] = FixFunctionDef('main', 'Execute', ['self', 'op', 'doc', 'host', 'bt', 'priority', 'flags'], remove=True)
  else:
    raise ValueError(kind)

  rt = RefactoringTool(fixers.values())
  code = rt.refactor_string(code, '<string>')
  return (code, '\n'.join(str(n) for fixer in fixers.values() for n in fixer.results))

print(refactor_expression_script('''
def main():
  pass
''', 'ObjectData')[1])

