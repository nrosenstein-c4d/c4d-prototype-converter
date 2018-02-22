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
from lib2to3.fixer_util import Leaf, Node, BlankLine, find_indentation
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


class FixIndentation(DelayBindBaseFix):

  # Code from http://python3porting.com/fixers.html#modifying-the-parse-tree

  def __init__(self, new_indent):
    self.indents = []
    self.compounds = []
    self.line = 0
    self.new_indent = new_indent

  def match(self, node):
    if isinstance(node, Leaf):
      return True
    return False

  def transform(self, node, results):
    if node.type == token.INDENT:
      self.line = node.lineno
      self.indents.append(len(node.value))
      new_indent = self.new_indent * len(self.indents)
      if node.value != new_indent:
        node.value = new_indent
        return node
    elif node.type == token.DEDENT:
      self.line = node.lineno
      if node.column == 0:
        self.indents = []
      else:
        level = self.indents.index(node.column)
        self.indents = self.indents[:level+1]
        if node.prefix:
          # During INDENT's the indentation level is
          # in the value. However, during OUTDENT's
          # the value is an empty string and then
          # indentation level is instead in the last
          # line of the prefix. So we remove the last
          # line of the prefix and add the correct
          # indententation as a new last line.
          prefix_lines = node.prefix.split('\n')[:-1]
          prefix_lines.append(self.new_indent * len(self.indents))
          new_prefix = '\n'.join(prefix_lines)
          if node.prefix != new_prefix:
            node.prefix = new_prefix
            # Return the modified node:
            return node
    elif node.type in (token.LPAR, token.LBRACE, token.LSQB): # (, {, [
      self.compounds.append(node.type)
    elif node.type in (token.RPAR, token.RBRACE, token.RSQB): # ), }, ]
      m = {token.RPAR: token.LPAR, token.RBRACE: token.LBRACE, token.RSQB: token.LSQB}
      assert self.compounds[-1] == m[node.type], (self.compounds[-1], node.type)
      self.compounds.pop()
    if self.line != node.lineno:  # New line
      self.line = node.lineno
      if not self.indents:
        return None  # First line, do nothing
      elif node.prefix:
        # Continues the same indentation
        # This lines intentation is the last line
        # of the prefix, as during DEDENTS. Remove
        # the old indentation and add the correct
        # indententation as a new last line.
        prefix_lines = node.prefix.split('\n')[:-1]
        indent_depth = len(self.indents) + len(self.compounds)
        prefix_lines.append(self.new_indent * indent_depth)
        new_prefix = '\n'.join(prefix_lines)
        if node.prefix != new_prefix:
          node.prefix = new_prefix
          # Return the modified node:
          return node

    return None


class FixStripFutureImports(DelayBindBaseFix):

  PATTERN = '''
    import_from< 'from' module_name="__future__" 'import' any >
  '''

  def __init__(self):
    self.imports = []

  @property
  def future_line(self):
    if self.imports:
      return 'from __future__ import {}'.format(', '.join(self.imports))
    else:
      return ''

  def transform(self, node, results):
    passed_import = False
    for child in node.children:
      if isinstance(child, Leaf) and child.type == token.NAME and child.value == 'import':
        passed_import = True
        continue
      if not passed_import:
        continue
      if isinstance(child, Node) and child.type == python_symbols.import_as_names:
        # from x import a, b
        for leaf in child.children:
          if leaf.type == token.NAME and leaf.value not in self.imports:
            self.imports.append(leaf.value)
      elif isinstance(child, Leaf) and child.type == token.NAME:
        # from x import a
        if child.value not in self.imports:
          self.imports.append(child.value)
    new = BlankLine()
    new.prefix = node.prefix
    return new


def strip_empty_lines(string):
  lines = []
  for line in string.split('\n'):
    if not lines and (not line or line.isspace()): continue
    lines.append(line)
  while lines and (not lines[-1] or lines[-1].isspace()):
    lines.pop()
  return '\n'.join(lines)


def refactor_expression_script(code, kind, indent=None):
  """
  Refactors Python code that is used in Python Generator or Expression Tag.
  Returns a tuple of three values strings:

  1. A string that represents imports from the `__future__` module
  2. The code without functions that are moved to member functions
  3. The refactored member functions (indentation unchanged)

  If *indent* is specified, it must be a string that represents a single
  indentation level. The indent of the code will be adjusted accordingly.

  The *kind* must be either the string `'ObjectData'` or `'TagData'`.
  """

  fixers = []
  fixers.append(FixStripFutureImports())
  fixers.append(FixFunctionDef('message', 'Message', ['self', 'op'],
      add_statement='return True', remove=True))

  if kind == 'ObjectData':
    fixers.append(FixFunctionDef('main', 'GetVirtualObjects',
      ['self', 'op', 'hh'], remove=True))
  elif kind == 'TagData':
    fixers.append(FixFunctionDef('main', 'Execute',
      ['self', 'op', 'doc', 'host', 'bt', 'priority', 'flags'], remove=True))
  else:
    raise ValueError(kind)

  if indent:
    fixers.append(FixIndentation(indent))

  rt = RefactoringTool(fixers)
  code = str(rt.refactor_string(code, '<string>'))
  methods = (x for fixer in fixers if isinstance(fixer, FixFunctionDef)
              for x in fixer.results)
  methods = '\n\n'.join(strip_empty_lines(str(x)) for x in methods)

  return map(strip_empty_lines, (fixers[0].future_line, code, methods))


def refactor_command_script(code, indent=None):
  """
  Refactors Python code that is used as a script in the Cinema 4D Sript
  Manager. The return value is the same as for #refactor_expression_script().
  """

  fixers = []
  fixers.append(FixStripFutureImports())
  fixers.append(FixFunctionDef('main', 'Execute', ['self', 'doc'],
    add_statement='return True', remove=True))

  if indent:
    fixers.append(FixIndentation(indent))

  rt = RefactoringTool(fixers)
  code = str(rt.refactor_string(code, '<string>'))

  if not fixers[1].results:
    lines = ['def Execute(self, doc):']
    for line in code.split('\n'):
      lines.append('  ' + line)
    lines.append('  return True')
    result = (fixers[0].future_line, '', '\n'.join(lines))  # Everything is member code
  else:
    result = (fixers[0].future_line, code, str(fixers[1].results[0]))

  return map(strip_empty_lines, result)


def refactor_indentation(code, indent):
  """
  Updates the indentation of the specified Python code.
  """

  fixer = FixIndentation(indent)
  rt = RefactoringTool([fixer])
  return str(rt.refactor_string(code, '<string>'))
