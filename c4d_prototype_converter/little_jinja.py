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
import re

try: from cStringIO import StringIO
except ImportError: from StringIO import StringIO


class RegexScanner(object):
  """
  Helper class to parse a string using regex patterns.
  """

  def __init__(self, string):
    self.string = string
    self.offset = 0
    self.rules = []
    self.previous = None
    self.current = None

  def __bool__(self):
    if self.current is not None and self.current[0] is None:
      return False
    return True

  __nonzero__ = __bool__

  def __iter__(self):
    while True:
      kind, match = self.next()
      if match is None: break
      yield kind, match

  def rule(self, name, pattern, flags=0):
    self.rules.append((name, re.compile(pattern, flags)))

  def next(self, rule_names=None):
    if self.current and self.current[0] is None:
      return self.current
    nearest = None
    nearest_index = None
    for name, pattern in self.rules:
      if rule_names is not None and name not in rule_names:
        continue
      match = pattern.search(self.string, self.offset)
      if match and (nearest is None or match.start() < nearest_index):
        nearest = (name, match)
        nearest_index = match.start()
    if nearest:
      self.offset = nearest[1].end()
      result = nearest
    else:
      result = (None, None)
    self.previous = self.current
    self.current = result
    return self.current

  def behind(self):
    """
    Returns the text that has been skipped between the current and the
    previous match.
    """

    if self.current is None:
      return ''
    if self.previous is None:
      start = 0
    else:
      start = self.previous[1].end()
    if self.current[0] is None:
      end = len(self.string)
    else:
      end = self.current[1].start()
    return self.string[start:end]

  def skipline(self):
    """
    Skip to the beginning of the next line.
    """

    newline = self.string.find('\n', self.offset)
    if newline >= 0:
      self.offset = newline + 1


def little_jinja(template_string, context):
  """
  A very lightweight implementation of the Jinja template rendering engine.
  It supports `{{ expr }}` variables as well as `{% if %}` control-flow (with
  elif, else and endif). The control-flow tags may be used as `{%-` and/or
  `-%}` to strip the preceeding/following whitespace until the next line,
  respectively.
  """

  scanner = RegexScanner(template_string)
  scanner.rule('var', r'\{\{(.*?)\}\}')
  scanner.rule('if', r'\{%-?\s*if\b(.*?)-?%\}')
  scanner.rule('elif', r'\{%-?\s*elif\b(.*?)-?%\}')
  scanner.rule('else', r'\{%-?\s*else\s*-?%\}')
  scanner.rule('endif', r'\{%-?\s*endif\s*-?%\}')

  class Node(object):
    def __init__(self, type, data, sub):
      self.type = type
      self.data = data
      self.sub = sub

  root = Node('root', None, [])
  open_blocks = [root]

  for kind, match in scanner:
    prev_text = Node('text', scanner.behind(), None)
    open_blocks[-1].sub.append(prev_text)
    if kind == 'var':
      open_blocks[-1].sub.append(Node('var', match.group(1), None))
    elif kind in ('if', 'elif', 'else', 'endif'):
      strip_left = match.group(0).startswith('{%-')
      strip_right = match.group(0).endswith('-%}')
      if kind == 'if':
        if_node = Node('if', {'elif': [], 'else': None, 'cond': match.group(1)}, [])
        open_blocks[-1].sub.append(if_node)
        open_blocks.append(if_node)
      elif kind == 'elif':
        if open_blocks[-1].type not in ('if', 'elif'):
          raise ValueError('unmatched "elif" instruction')
        elif_node = Node('elif', {'cond': match.group(1)}, [])
        if_node = next(x for x in reversed(open_blocks) if x.type == 'if')
        if_node.data['elif'].append(elif_node)
        open_blocks.append(elif_node)
      elif kind == 'else':
        if open_blocks[-1].type not in ('if', 'elif'):
          raise ValueError('unmatched "else" instruction')
        else_node = Node('else', None, [])
        if_node = next(x for x in reversed(open_blocks) if x.type == 'if')
        if if_node.data['else']:
          raise ValueError('multiple "else" instructions')
        if_node.data['else'] = else_node
        open_blocks.append(else_node)
      elif kind == 'endif':
        if open_blocks[-1].type not in ('if', 'elif', 'else'):
          raise ValueError('unmatched "endif" instruction')
        while open_blocks[-1].type in ('elif', 'else'):
          open_blocks.pop()
        assert open_blocks[-1].type == 'if'
        open_blocks.pop()
      else:
        assert False, kind
      if strip_left:
        newline = prev_text.data.rfind('\n')
        if newline >= 0:
          prev_text.data = prev_text.data[:newline]
      if strip_right:
        scanner.skipline()
    else:
      assert False, kind

  open_blocks[-1].sub.append(Node('text', scanner.behind(), None))

  if len(open_blocks) != 1:
    raise ValueError('invalid template: unclosed {} block'
      .format(open_blocks[-1].type))

  out = StringIO()
  def render(node):
    if node.type == 'text':
      out.write(node.data)
    elif node.type == 'var':
      out.write(str(eval(node.data, context)))
    elif node.type == 'if':
      tests = [node] + node.data['elif']
      for node in tests:
        if eval(node.data['cond'], context):
          for child in node.sub:
            render(child)
          break
      else:
        if node.data['else']:
          for child in node.sub:
            render(child)
    else:
      assert False, node.type
  for node in root.sub:
    render(node)

  return out.getvalue()
