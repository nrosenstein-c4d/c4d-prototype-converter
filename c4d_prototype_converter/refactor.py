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


def refactor_string(fixers, code, filename='<string>'):
  rt = RefactoringTool(fixers)
  code = code.rstrip() + '\n'  # ParseError without trailing newline
  return rt.refactor_string(code, filename)


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

  This fixer only matches global function defs.
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
    # Determine the node's column number by finding the first leaf.
    leaf = node
    while not isinstance(leaf, Leaf):
      leaf = leaf.children[0]
    # Only match functions and the global indentation level.
    if leaf.column != 0:
      return

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
      return None

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


class FixStripDocstrings(DelayBindBaseFix):
  """
  Strips module docstrings.
  """

  def __init__(self):
    self.docstring = None

  def match(self, node):
    return True

  def transform(self, node, results):
    if isinstance(node, Node) and node.type == python_symbols.file_input:
      for child in node.children:
        if child.type == python_symbols.simple_stmt:
          if child.children and child.children[0].type == token.STRING:
            self.docstring = child.children[0].value
            child.replace(BlankLine())


class FixUserDataAccess(DelayBindBaseFix):

  PATTERN = "power<'c4d' trailer<'.' 'ID_USERDATA' > >"

  def transform(self, node, result):
    #print(repr(node))
    # TODO
    pass


def strip_empty_lines(string):
  lines = []
  for line in string.split('\n'):
    if not lines and (not line or line.isspace()): continue
    lines.append(line)
  while lines and (not lines[-1] or lines[-1].isspace()):
    lines.pop()
  return '\n'.join(lines)


def split_docstring(code):
  fixer = FixStripDocstrings()
  return str(refactor_string([fixer], code)), strip_empty_lines(fixer.docstring or '')


def split_future_imports(code):
  fixer = FixStripFutureImports()
  return str(refactor_string([fixer], code)), strip_empty_lines(fixer.future_line or '')


def split_and_refactor_global_function(code, func_name, new_func_name=None,
    prepend_args=None, append_args=None, add_statement=None):
  fixer = FixFunctionDef(func_name, new_func_name, prepend_args, append_args,
    True, add_statement)
  code = str(refactor_string([fixer], code))
  functions = '\n'.join(strip_empty_lines(str(x)) for x in fixer.results)
  return strip_empty_lines(code), functions


def indentation(code, indent):
  fixer = FixIndentation(indent)
  return str(refactor_string([fixer], code))
