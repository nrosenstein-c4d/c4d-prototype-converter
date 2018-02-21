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

from __future__ import division, print_function
import c4d
import collections
import os
import re
import shutil
import sys
import webbrowser

from . import codeconv
from .c4dutils import (unicode_refreplace, get_subcontainer, has_subcontainer,
  DialogOpenerCommand, BaseDialog)
from .generics import Generic, HashDict
from .little_jinja import little_jinja
from .utils import makedirs, nullable_ref


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


def res_file(path):
  res_dir = os.path.join(os.path.dirname(__file__))
  return os.path.join(res_dir, path)


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


def userdata_tree(ud):
  """
  Builds a tree of userdata information. Returns a proxy root node that
  contains at least the main User Data group and eventually other root
  groups.
  """

  DataNode = Node[dict]
  params = HashDict()
  root = Node[None]()

  # Create a node for every parameter.
  for descid, bc in ud:
    params[descid] = DataNode(descid=descid, bc=bc)

  # The main userdata group is not described in the UserData container.
  descid = c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0))
  node = DataNode(descid=descid, bc=c4d.BaseContainer())
  params[descid] = node
  root.add_child(node)

  # Establish parent-child parameter relationships.
  for descid, bc in ud:
    node = params[descid]
    parent_id = bc[c4d.DESC_PARENTGROUP]
    try:
      parent = params[parent_id]
    except KeyError:
      root.add_child(node)
    else:
      parent.add_child(node)

  return root


def is_minvalue(x):
  """
  Checks for very low values, that might indicate that a parameter has
  no upper bounds (from a user perspective).
  """

  if isinstance(x, int):
    return x <= 2**31
  elif isinstance(x, float):
    return x < float('1e' + str(sys.float_info.min_10_exp-1))
  elif isinstance(x, c4d.Vector):
    return is_minvalue(x.x) and is_minvalue(x.y) and is_minvalue(x.z)


def is_maxvalue(x):
  """
  Checks for very high values, that might indicate that a parameter has
  no upper bounds (from a user perspective) .
  """

  if isinstance(x, int):
    return x >= 2**32-1
  elif isinstance(x, float):
    return x > float('1e+' + str(sys.float_info.max_10_exp-1))
  elif isinstance(x, c4d.Vector):
    return is_maxvalue(x.x) and is_maxvalue(x.y) and is_maxvalue(x.z)


ID_PLUGIN_CONVERTER = 1040648
ID_SCRIPT_CONVERTER = 1040671
COLOR_BLUE = c4d.Vector(0.5, 0.6, 0.9)
COLOR_RED = c4d.Vector(0.9, 0.3, 0.3)
COLOR_YELLOW = c4d.Vector(0.9, 0.8, 0.6)


class SymbolMap(object):
  """
  A map for User Data symbols used in the #PrototypeConverter.
  """

  def __init__(self, prefix):
    self.curr_id = 1000
    self.symbols = collections.OrderedDict()
    self.descid_to_symbol = HashDict()
    self.descid_to_node = HashDict()
    self.hardcoded_description = HashDict()
    self.prefix = prefix

  def translate_name(self, name, add_prefix=True, unique=True):
    result = re.sub('[^\w\d_]+', '_', name).upper().strip('_')
    if add_prefix:
      result = self.prefix + result
    if unique:
      index = 0
      while True:
        symbol = result + (str(index) if index != 0 else '')
        if symbol not in self.symbols: break
        index += 1
      result = symbol
    return result

  def allocate_symbol(self, node):
    """
    Expects a #Node[dict] as returned by #userdata_tree(). Assigns a symbol
    to the node and registers its descid in this map.
    """

    if node['descid'][-1].dtype == c4d.DTYPE_SEPARATOR and not node['bc'][c4d.DESC_NAME]:
      node['symbol'] = (None, None)
      return None, None

    # Find a unique name for the symbol.
    name = node['bc'][c4d.DESC_SHORT_NAME] or node['bc'][c4d.DESC_NAME]
    if node['descid'][-1].dtype == c4d.DTYPE_GROUP:
      name += '_GROUP'
    else:
      parent = node.parent()
      if parent.data:
        parent_name = parent['bc'].GetString(c4d.DESC_NAME)
        if parent_name:
          name = parent_name + ' ' + name

    symbol = self.translate_name(name)
    value = self.curr_id
    self.curr_id += 1
    self.symbols[symbol] = value
    descid = node['descid']
    self.descid_to_symbol[descid] = symbol
    self.descid_to_node[descid] = node
    node['symbol'] = (symbol, value)
    return symbol, value

  def get_cycle_symbol(self, node, cycle_name):
    """
    Constructs the symbolic name of a value in a cycle parameter.
    """

    symbol = node.get('symbol', (None, None))[0]
    if not symbol:
      symbol = self.allocate_symbol(node)[0]
    return symbol + '_' + self.translate_name(cycle_name, False, False)

  def add_hardcoded_description(self, node, param, value):
    params = self.hardcoded_description.setdefault(node['descid'], [])
    params.append((param, value))


class PrototypeConverter(object):
  """
  This object holds the information on how the description resource will
  be generated.
  """

  def __init__(self, link, plugin_name, plugin_id, resource_name,
               symbol_prefix, icon_file, directory, indent='  ',
               write_plugin_stub=True, write_resources=True,
               symbol_mode='c4ddev', overwrite='none'):
    assert symbol_mode in ('c4d', 'c4ddev'), symbol_mode
    self.link = link
    self.plugin_name = plugin_name
    self.plugin_id = plugin_id
    self.resource_name = resource_name
    self.symbol_prefix = symbol_prefix
    self.icon_file = icon_file
    self.directory = directory
    self.indent = indent
    self.write_plugin_stub = write_plugin_stub
    self.write_resources = write_resources
    self.symbol_mode = symbol_mode
    self.overwrite = overwrite

  def plugin_type_info(self):
    if not self.link:
      return {}
    if self.link.CheckType(c4d.Obase):
      return {'resprefix': 'O', 'resbase': 'Obase', 'plugintype': 'Object'}
    if self.link.CheckType(c4d.Tbase):
      return {'resprefix': 'T', 'resbase': 'Tbase', 'plugintype': 'Tag'}
    if self.link.CheckType(c4d.Xbase):
      return {'resprefix': 'X', 'resbase': 'Xbase', 'plugintype': 'Shader'}
    if self.link.CheckType(c4d.Mbase):
      return {'resprefix': 'M', 'resbase': 'Mbase', 'plugintype': None}
    return {}

  def autofill(self, default_plugin_name='My Plugin'):
    if not self.plugin_name:
      self.plugin_name = (self.link.GetName() if self.link else '')
    if not self.plugin_name:
      self.plugin_name = default_plugin_name
    if not self.resource_name:
      self.resource_name = re.sub('[^\w\d]+', '', self.plugin_name).lower()
      self.resource_name = self.plugin_type_info().get('resprefix', '') + self.resource_name
    if not self.symbol_prefix:
      self.symbol_prefix = re.sub('[^\w\d]+', '_', self.plugin_name).rstrip('_').upper() + '_'
    if not self.directory:
      write_dir = c4d.storage.GeGetC4DPath(c4d.C4D_PATH_STARTUPWRITE)
      dirname = re.sub('[^\w\d]+', '-', self.plugin_name).lower()
      self.directory = os.path.join(write_dir, 'plugins', dirname)

  def files(self):
    f = lambda s: s.format(**sys._getframe(1).f_locals)
    j = lambda *p: os.path.join(parent_dir, *p)
    parent_dir = self.directory or self.plugin_name
    plugin_filename = re.sub('[^\w\d]+', '-', self.plugin_name).lower()
    plugin_type_info = self.plugin_type_info()
    result = {'directory': parent_dir}
    if self.write_resources:
      result.update({
        'c4d_symbols': j('res', 'c4d_symbols.h'),
        'header': j('res', 'description', f('{self.resource_name}.h')),
        'description': j('res', 'description', f('{self.resource_name}.res')),
        'strings_us': j('res', 'strings_us', 'description', f('{self.resource_name}.str'))
      })
    if self.write_plugin_stub and plugin_type_info.get('plugintype'):
      result['plugin'] = j(f('{plugin_filename}.pyp'))
    if self.icon_file:
      suffix = os.path.splitext(self.icon_file)[1]
      result['icon'] = j('res', 'icons', f('{self.plugin_name}{suffix}'))
    return result

  def optional_file_ids(self):
    return ('directory', 'c4d_symbols')

  def create(self):
    if not self.directory:
      raise RuntimeError('PrototypeConverter.directory must be set')
    if not self.link:
      raise RuntimeError('PrototypeConverter.link must be set')
    if self.icon_file and not os.path.isfile(self.icon_file):
      raise IOError('File "{}" does not exist'.format(self.icon_file))

    plugin_type_info = self.plugin_type_info()
    files = self.files()
    optionals = self.optional_file_ids()
    if not self.overwrite:
      for k in files:
        v = files.get(k)
        if not v or k in optionals: continue
        if os.path.exists(v):
          raise IOError('File "{}" already exists'.format(v))

    makedirs(os.path.dirname(files['c4d_symbols']))
    if self.overwrite or not os.path.isfile(files['c4d_symbols']):
      makedirs(os.path.dirname(files['c4d_symbols']))
      with open(files['c4d_symbols'], 'w') as fp:
        fp.write('#pragma once\nenum {\n};\n')

    ud = self.link.GetUserDataContainer()
    symbol_map = SymbolMap(self.symbol_prefix)
    ud_tree = userdata_tree(ud)
    ud_main_group = next((
      x for x in ud_tree.children
      if x['descid'] == c4d.DescID(c4d.ID_USERDATA)
    ))
    ud_tree.visit(lambda x: symbol_map.allocate_symbol(x) if x != ud_main_group else None, False)

    # Render the symbols to the description header. This will also
    # initialize our symbols_map.
    makedirs(os.path.dirname(files['header']))
    with open(files['header'], 'w') as fp:
      fp.write('#pragma once\nenum {\n')
      if self.plugin_id:
        fp.write(self.indent + '{self.resource_name} = {self.plugin_id},\n'.format(self=self))
      ud_tree.visit(lambda x: self.render_symbol(fp, x, symbol_map))
      fp.write('};\n')

    makedirs(os.path.dirname(files['description']))
    with open(files['description'], 'w') as fp:
      fp.write('CONTAINER {self.resource_name} {{\n'.format(self=self))
      for base, propgroup in [
          ('Obase', 'ID_OBJECTPROPERTIES'), ('Tbase', 'ID_TAGPROPERTIES'),
          ('Xbase', 'ID_SHADERPROPERTIES'), ('Mbase', 'ID_MATERIALPROPERTIES')]:
        if self.link.CheckType(getattr(c4d, base)):
          fp.write(self.indent + 'INCLUDE {base};\n'.format(base=base))
          break
      else:
        propgroup = None
      fp.write(self.indent + 'NAME {self.resource_name};\n'.format(self=self))
      if propgroup:
        fp.write(self.indent + 'GROUP {0} {{\n'.format(propgroup))
        for node in ud_main_group.children:
          self.render_parameter(fp, node, symbol_map, depth=2)
        fp.write(self.indent + '}\n')
      for node in ud_tree.children:
        if node['descid'] == c4d.DescID(c4d.ID_USERDATA): continue
        self.render_parameter(fp, node, symbol_map)
      fp.write('}\n')

    makedirs(os.path.dirname(files['strings_us']))
    with open(files['strings_us'], 'w') as fp:
      fp.write('STRINGTABLE {self.resource_name} {{\n'.format(self=self))
      fp.write('{self.indent}{self.resource_name} "{self.plugin_name}";\n'.format(self=self))
      ud_tree.visit(lambda x: self.render_symbol_string(fp, x, symbol_map))
      fp.write('}\n')

    if 'plugin' in files and (self.overwrite or not os.path.isfile(files['plugin'])):
      makedirs(os.path.dirname(files['plugin']))
      with open(res_file('templates/node_plugin.txt')) as fp:
        template = fp.read()

      Opython = 1023866
      plugin_flags = ''
      if self.link.CheckType(Opython) or self.link.CheckType(c4d.Tpython):
        if self.link.CheckType(Opython):
          kind = 'ObjectData'
          code = self.link[c4d.OPYTHON_CODE]
          plugin_flags = 'c4d.OBJECT_GENERATOR'
        else:
          kind = 'TagData'
          code = self.link[c4d.TPYTHON_CODE]
          plugin_flags = 'c4d.TAG_VISIBLE | c4d.TAG_EXPRESSION'
        future_import, global_code, member_code = \
          codeconv.refactor_expression_script(code, kind, indent='  ')
      else:
        future_import, global_code, member_code = None, None, None

      if member_code:
        # Indent the code appropriately for the plugin stub.
        member_code = '\n'.join('  ' + l for l in member_code.split('\n'))

      context = {
        'c4d': c4d,
        'parameters': [
          (symbol_map.descid_to_node[did], did, bc)
          for did, bc in ud if did in symbol_map.descid_to_node],
        'hardcoded_description': [
          (symbol_map.descid_to_node[did], params)
          for did, params in symbol_map.hardcoded_description.items()
        ],
        'future_import': future_import,
        'global_code': global_code,
        'member_code': member_code,
        'plugin_class': re.sub('[^\w\d]+', '', self.plugin_name) + 'Data',
        'plugin_type': plugin_type_info['plugintype'],
        'plugin_id': self.plugin_id,
        'plugin_name': self.plugin_name,
        'plugin_info': plugin_flags,
        'plugin_desc': self.resource_name,
        'plugin_icon': 'res/icons/' + os.path.basename(files['icon']) if files.get('icon') else None,
        'symbol_mode': self.symbol_mode,
      }
      code = little_jinja(template, context)
      # Write the code for now so you can inspect it should refactoring go wrong.
      with open(files['plugin'], 'w') as fp:
        fp.write(code)
      code = codeconv.refactor_indentation(code, self.indent)
      with open(files['plugin'], 'w') as fp:
        fp.write(code)

    if self.icon_file and self.icon_file != files['icon']:
      makedirs(os.path.dirname(files['icon']))
      try:
        shutil.copy(self.icon_file, files['icon'])
      except shutil.Error as exc:
        print('Warning: Error copying icon:', exc)

  def render_symbol(self, fp, node, symbol_map):
    if not node.data or node['descid'] == c4d.DescID(c4d.ID_USERDATA):
      return

    sym, value = node['symbol']
    if not sym:
      return

    fp.write(self.indent + '{} = {},\n'.format(sym, value))

    children = node['bc'].GetContainerInstance(c4d.DESC_CYCLE)
    if children:
      for value, name in children:
        sym = symbol_map.get_cycle_symbol(node, name)
        fp.write(self.indent * 2 + '{} = {},\n'.format(sym, value))

    return sym

  def render_parameter(self, fp, node, symbol_map, depth=1):
    bc = node['bc']
    symbol = node['symbol'][0]
    dtype = node['descid'][-1].dtype
    if dtype == c4d.DTYPE_GROUP:
      fp.write(self.indent * depth + 'GROUP {} {{\n'.format(symbol))
      if bc[c4d.DESC_DEFAULT]:
        fp.write(self.indent * (depth+1) + 'DEFAULT 1;\n')
      if bc[c4d.DESC_TITLEBAR]:
        pass # TODO
      if bc.GetInt32(c4d.DESC_COLUMNS) not in (0, 1):
        fp.write(self.indent * (depth+1) + 'COLUMNS {};\n'.format(bc[c4d.DESC_COLUMNS]))
      if bc[c4d.DESC_GROUPSCALEV]:
        fp.write(self.indent * (depth+1) + 'SCALE_V;\n')
      for child in node.children:
        self.render_parameter(fp, child, symbol_map, depth+1)
      fp.write(self.indent * depth + '}\n')
    else:
      typename = None
      props = []
      default = bc[c4d.DESC_DEFAULT]

      if bc[c4d.DESC_ANIMATE] == c4d.DESC_ANIMATE_OFF:
        props.append('ANIMATE OFF;')
      elif bc[c4d.DESC_ANIMATE] == c4d.DESC_ANIMATE_MIX:
        props.append('ANIMATE MIX;')

      if dtype == c4d.DTYPE_BOOL:
        typename = 'BOOL'
        if default is not None:
          props.append('DEFAULT 1;' if default else 'DEFAULT 0;')

      elif dtype in (c4d.DTYPE_LONG, c4d.DTYPE_REAL):
        typename = 'LONG' if dtype == c4d.DTYPE_LONG else 'REAL'
        typecast = int if dtype == c4d.DTYPE_LONG else float
        cycle = bc[c4d.DESC_CYCLE]
        has_cycle = (dtype == c4d.DTYPE_LONG and cycle)
        multiplier = 100 if (not has_cycle and bc[c4d.DESC_UNIT] == c4d.DESC_UNIT_PERCENT) else 1

        if has_cycle:
          cycle_lines = []
          default_name = None
          if isinstance(default, int):
            default_name = cycle.GetString(default)
          for _, name in cycle:
            cycle_lines.append(symbol_map.get_cycle_symbol(node, name) + ';')
          cycle_lines = self.indent + ('\n'+self.indent).join(cycle_lines)
          props.append('CYCLE {\n' + cycle_lines + '\n}')
          if default_name:
            props.append('DEFAULT {};'.format(symbol_map.get_cycle_symbol(node, default_name)))
          elif isinstance(default, int):
            props.append('DEFAULT {};'.format(int(default * multiplier)))
        elif isinstance(default, (int, float)):
          props.append('DEFAULT {};'.format(typecast(default * multiplier)))

        if bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_LONGSLIDER:
          props.append('CUSTOMGUI LONGSLIDER;')
        elif bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_CYCLEBUTTON:
          props.append('CUSTOMGUI CYCLEBUTTON;')
        elif bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_REALSLIDER:
          props.append('CUSTOMGUI REALSLIDER;')
        elif bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_REALSLIDERONLY:
          props.append('CUSTOMGUI REALSLIDERONLY;')
        elif bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_LONG_LAT:
          props.append('CUSTOMGUI LONG_LAT;')
        # QuickTab CustomGUI (btw. for some reason not the same as
        # c4d.CUSTOMGUI_QUICKTAB)
        elif bc[c4d.DESC_CUSTOMGUI] == 200000281:
          symbol_map.add_hardcoded_description(node, 'c4d.DESC_CUSTOMGUI', 200000281)
        # RadioButtons CustomGUI.
        elif bc[c4d.DESC_CUSTOMGUI] == 1019603:
          symbol_map.add_hardcoded_description(node, 'c4d.DESC_CUSTOMGUI', 1019603)
        else:
          print('Note: unknown customgui:', bc[c4d.DESC_NAME], bc[c4d.DESC_CUSTOMGUI])
        # TODO: Quick Tab/Radio Button customgui

        if not has_cycle:
          if bc.GetType(c4d.DESC_MIN) == dtype and not is_minvalue(bc[c4d.DESC_MIN]):
            props.append('MIN {};'.format(bc[c4d.DESC_MIN] * multiplier))
          if bc.GetType(c4d.DESC_MAX) == dtype and not is_maxvalue(bc[c4d.DESC_MAX]):
            props.append('MAX {};'.format(bc[c4d.DESC_MAX] * multiplier))

          if bc[c4d.DESC_CUSTOMGUI] in (c4d.CUSTOMGUI_LONGSLIDER, c4d.CUSTOMGUI_REALSLIDER, c4d.CUSTOMGUI_REALSLIDERONLY):
            if bc.GetType(c4d.DESC_MINSLIDER) == dtype:
              props.append('MINSLIDER {};'.format(bc[c4d.DESC_MINSLIDER] * multiplier))
            if bc.GetType(c4d.DESC_MAXSLIDER) == dtype:
              props.append('MAXSLIDER {};'.format(bc[c4d.DESC_MAXSLIDER] * multiplier))

          if bc.GetType(c4d.DESC_STEP) == dtype:
            step = bc[c4d.DESC_STEP] * multiplier
            props.append('STEP {};'.format(step))

      elif dtype == c4d.DTYPE_BUTTON:
        typename = 'BUTTON'

      elif dtype in (c4d.DTYPE_COLOR, c4d.DTYPE_VECTOR):
        typename = 'COLOR' if dtype == c4d.DTYPE_COLOR else 'VECTOR'
        vecprop = lambda n, x: '{0} {1.x} {1.y} {1.z};'.format(n, x)
        multiplier = 100 if (bc[c4d.DESC_UNIT] == c4d.DESC_UNIT_PERCENT) else 1
        if isinstance(default, c4d.Vector):
          props.append(vecprop('DEFAULT', default))
        if dtype == c4d.DTYPE_VECTOR:
          if bc.GetType(c4d.DESC_MIN) == c4d.DTYPE_VECTOR and not is_minvalue(bc[c4d.DESC_MIN]):
            props.append(vecprop('MIN', bc.GetVector(c4d.DESC_MIN) * multiplier))
          if bc.GetType(c4d.DESC_MAX) == c4d.DTYPE_VECTOR and not is_maxvalue(bc[c4d.DESC_MAX]):
            props.append(vecprop('MAX', bc.GetVector(c4d.DESC_MAX) * multiplier))
          if bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_SUBDESCRIPTION:
            props.append('CUSTOMGUI SUBDESCRIPTION;')
          if bc.GetType(c4d.DESC_STEP) == c4d.DTYPE_VECTOR:
            props.append(vecprop('STEP', bc[c4d.DESC_STEP] * multiplier))

      elif dtype == c4d.DTYPE_FILENAME:
        typename = 'FILENAME'

      elif dtype == c4d.CUSTOMDATATYPE_GRADIENT:
        typename = 'GRADIENT'

      elif dtype == c4d.CUSTOMDATATYPE_INEXCLUDE_LIST:
        typename = 'IN_EXCLUDE'

      elif dtype == c4d.DTYPE_BASELISTLINK:
        if bc[c4d.DESC_CUSTOMGUI] == c4d.CUSTOMGUI_TEXBOX:
          typename = 'SHADERLINK'
        else:
          typename = 'LINK'
          refuse = bc[c4d.DESC_REFUSE]
          if refuse:
            props.append('REFUSE { ' + ' '.join(
              (refuse_name if refuse_name else str(refuse_id)) + ';'
              for refuse_id, refuse_name in refuse
            ) + ' }')
          accept = bc[c4d.DESC_ACCEPT]
          if accept:
            props.append('ACCEPT { ' + ' '.join(
              (accept_id if accept_name else str(accept_id)) + ';'
              for accept_id, accept_name in accept
              if accept_id != c4d.Tbaselist2d
            ) + ' }')
            if props[-1] == 'ACCEPT {  }':
              props.pop()

      elif dtype == c4d.CUSTOMDATATYPE_SPLINE:
        typename = 'SPLINE'

      elif dtype == c4d.DTYPE_STRING:
        typename = 'STRING'

      elif dtype == c4d.DTYPE_TIME:
        typename = 'TIME'

      elif dtype == c4d.DTYPE_SEPARATOR:
        typename = 'SEPARATOR'
        if bc[c4d.DESC_SEPARATORLINE]:
          props.append('LINE;')

      else:
        print('Unhandled datatype:', dtype, '({})'.format(node['bc'][c4d.DESC_NAME]))
        return

      # Handle units.
      if dtype in (c4d.DTYPE_LONG, c4d.DTYPE_REAL, c4d.DTYPE_VECTOR):
        if bc[c4d.DESC_UNIT] == c4d.DESC_UNIT_PERCENT:
          props.append('UNIT PERCENT;')
        elif bc[c4d.DESC_UNIT] == c4d.DESC_UNIT_DEGREE:
          props.append('UNIT DEGREE;')
        elif bc[c4d.DESC_UNIT] == c4d.DESC_UNIT_METER:
          props.append('UNIT METER;')

      fp.write(self.indent * depth + typename)
      if symbol:
        fp.write(' ' + symbol)
      fp.write(' {')

      if any('\n' in x for x in props):
        fp.write('\n')
        single, multi = [], []
        for prop in props:
          prop = prop.rstrip()
          if '\n' in prop: multi.append(prop)
          else: single.append(prop)
        if single:
          fp.write(self.indent * (depth+1) + ' '.join(single) + '\n')
        for prop in multi:
          for line in prop.split('\n'):
            fp.write(self.indent * (depth+1) + line + '\n')
        fp.write(self.indent * depth + '}\n')
      else:
        fp.write(' ' + ' '.join(props) + (' ' if props else ''))
        fp.write('}\n')

  def render_symbol_string(self, fp, node, symbol_map):
    if not node.data or node['descid'] == c4d.DescID(c4d.ID_USERDATA):
      return
    symbol = node['symbol'][0]
    if not symbol:
      return
    name = unicode_refreplace(node['bc'][c4d.DESC_NAME])
    fp.write(self.indent + '{} "{}";\n'.format(symbol, name))
    cycle = node['bc'][c4d.DESC_CYCLE]
    icons = node['bc'][c4d.DESC_CYCLEICONS]
    for item_id, name in (cycle or []):
      name = unicode_refreplace(name)
      strname = name
      if icons and icons[item_id]:
        strname += '&i' + str(icons[item_id])
      fp.write(self.indent * 2 + '{} "{}";\n'.format(
        symbol_map.get_cycle_symbol(node, name), strname))

  def save_to_link(self):
    if not self.link:
      raise RuntimeError('has no link')
    bc = get_subcontainer(self.link.GetDataInstance(), ID_PLUGIN_CONVERTER)
    bc[0] = self.plugin_name
    bc[1] = self.plugin_id
    bc[2] = self.resource_name
    bc[3] = self.symbol_prefix
    bc[4] = self.icon_file
    bc[5] = self.directory
    bc[6] = self.indent
    bc[7] = self.symbol_mode
    assert self.has_settings()

  def read_from_link(self):
    bc = get_subcontainer(self.link.GetDataInstance(), ID_PLUGIN_CONVERTER)
    self.plugin_name = bc.GetString(0)
    self.plugin_id = bc.GetString(1)
    self.resource_name = bc.GetString(2)
    self.symbol_prefix = bc.GetString(3)
    self.icon_file = bc.GetString(4)
    self.directory = bc.GetString(5)
    self.indent = bc.GetString(6)
    self.symbol_mode = bc.GetString(7)

  def has_settings(self):
    if self.link:
      return has_subcontainer(self.link.GetDataInstance(), ID_PLUGIN_CONVERTER)
    return False


class PrototypeConverterDialog(BaseDialog):
  """
  Implements the User Interface to convert an object's UserData to a
  Cinema 4D description resource.
  """

  ID_PLUGIN_NAME = 1000
  ID_ICON_FILE = 1001
  ID_RESOURCE_NAME = 1002
  ID_SYMBOL_PREFIX = 1003
  ID_DIRECTORY = 1004
  ID_LINK = 1005
  ID_CREATE = 1006
  ID_CANCEL = 1007
  ID_FILELIST_GROUP = 1008
  ID_OVERWRITE = 1009
  ID_PLUGIN_ID = 1010
  ID_INDENT = 1011
  ID_LINK_TEXT = 1012
  ID_PLUGIN_ID_TEXT = 1013
  ID_DIRECTORY_TEXT = 1014
  ID_MODE = 1015
  ID_PLUGIN_ID_GET = 1016
  ID_SYMBOLMODE = 1017

  INDENT_TAB = 0
  INDENT_2SPACE = 1
  INDENT_4SPACE = 2

  MODE_ALL = 0
  MODE_RESOURCE = 1
  MODE_PLUGINSTUB = 2

  SYMBOLMODE_C4D = 0
  SYMBOLMODE_C4DDEV = 1

  def get_converter(self):
    mode = self.GetInt32(self.ID_MODE)
    symbol_mode = {self.SYMBOLMODE_C4D: 'c4d', self.SYMBOLMODE_C4DDEV: 'c4ddev'}[self.GetInt32(self.ID_SYMBOLMODE)]
    return PrototypeConverter(
      link = self.GetLink(self.ID_LINK),
      plugin_name = self.GetString(self.ID_PLUGIN_NAME),
      plugin_id = self.GetString(self.ID_PLUGIN_ID).strip(),
      resource_name = self.GetString(self.ID_RESOURCE_NAME),
      symbol_prefix = self.GetString(self.ID_SYMBOL_PREFIX),
      icon_file = self.GetFileSelectorString(self.ID_ICON_FILE),
      directory = self.GetFileSelectorString(self.ID_DIRECTORY),
      write_plugin_stub = mode in (self.MODE_ALL, self.MODE_PLUGINSTUB),
      write_resources = mode in (self.MODE_ALL, self.MODE_RESOURCE),
      symbol_mode = symbol_mode,
      overwrite = self.GetBool(self.ID_OVERWRITE),
      indent = {self.INDENT_TAB: '\t', self.INDENT_2SPACE: '  ', self.INDENT_4SPACE: '    '}[self.GetInt32(self.ID_INDENT)]
    )

  def load_settings(self, update_ui=True):
    cnv = self.get_converter()
    if not cnv.link: return
    if not cnv.has_settings(): return
    cnv.read_from_link()
    self.SetString(self.ID_PLUGIN_NAME, cnv.plugin_name)
    self.SetString(self.ID_PLUGIN_ID, cnv.plugin_id)
    self.SetString(self.ID_RESOURCE_NAME, cnv.resource_name)
    self.SetString(self.ID_SYMBOL_PREFIX, cnv.symbol_prefix)
    self.SetFileSelectorString(self.ID_ICON_FILE, cnv.icon_file)
    self.SetFileSelectorString(self.ID_DIRECTORY, cnv.directory)
    if cnv.indent == '\t':
      self.SetInt32(self.ID_INDENT, self.INDENT_TAB)
    elif cnv.indent == '  ':
      self.SetInt32(self.ID_INDENT, self.INDENT_2SPACE)
    elif cnv.indent == '    ':
      self.SetInt32(self.ID_INDENT, self.INDENT_4SPACE)
    if cnv.symbol_mode == 'c4d':
      self.SetInt32(self.ID_SYMBOLMODE, self.SYMBOLMODE_C4D)
    elif cnv.symbol_mode == 'c4ddev':
      self.SetInt32(self.ID_SYMBOLMODE, self.SYMBOLMODE_C4DDEV)
    print('Loaded settings from object "{}".'.format(cnv.link.GetName()))
    if update_ui:
      self.update_filelist()
      self.update_enabling()

  def update_filelist(self):
    cnv = self.get_converter()
    cnv.autofill()
    files = cnv.files()

    parent = os.path.dirname(files.pop('directory'))
    files = sorted(files.items(), key=lambda x: x[1].lower())

    self.ReleaseIdPool('filelist')
    self.LayoutFlushGroup(self.ID_FILELIST_GROUP)
    for entry in file_tree(files, parent=parent, flat=True, key=lambda x: x[1]):
      depth = entry.depth()
      name = '  ' * depth + os.path.basename(entry['path'])
      if entry['isdir']:
        name += '/'
      widget_id = self.AllocId('filelist')
      self.AddStaticText(widget_id, c4d.BFH_LEFT, name=name)
      full_path = os.path.join(parent, entry['path'])
      if not entry['isdir'] and os.path.isfile(full_path):
        if entry['data'][0] in cnv.optional_file_ids():
          color = COLOR_BLUE
        elif cnv.overwrite:
          color = COLOR_YELLOW
        else:
          color = COLOR_RED
        self.SetColor(widget_id, c4d.COLOR_TEXT, color)
    self.LayoutChanged(self.ID_FILELIST_GROUP)

    self.SetString(self.ID_SYMBOL_PREFIX, cnv.symbol_prefix, False, c4d.EDITTEXT_HELPTEXT)
    self.SetString(self.ID_RESOURCE_NAME, cnv.resource_name, False, c4d.EDITTEXT_HELPTEXT)
    self.SetString(self.ID_PLUGIN_NAME, cnv.plugin_name, False, c4d.EDITTEXT_HELPTEXT)
    self.SetFileSelectorString(self.ID_DIRECTORY, cnv.directory, flags=c4d.EDITTEXT_HELPTEXT)

  def update_enabling(self):
    ids = [self.ID_LINK_TEXT, self.ID_PLUGIN_ID_TEXT]
    invalids = []

    if self.GetLink(self.ID_LINK) is None:
      invalids.append(self.ID_LINK_TEXT)
      enabled = False

    if not self.GetString(self.ID_PLUGIN_ID).strip().isdigit():
      invalids.append(self.ID_PLUGIN_ID_TEXT)
      enabled = False

    for param_id in ids:
      color = COLOR_RED if param_id in invalids else None
      self.SetColor(param_id, c4d.COLOR_TEXT, color)

    self.Enable(self.ID_CREATE, not invalids)

  def do_create(self):
    cnv = self.get_converter()
    cnv.autofill()
    if not cnv.link:
      c4d.gui.MessageDialog('No source object specified.')
      return
    if not cnv.directory:
      c4d.gui.MessageDialog('No output directory specified.')
      return
    try:
      cnv.create()
    except IOError as exc:
      c4d.gui.MessageDialog(str(exc))
    else:
      cnv.save_to_link()
      print('Saved settings to object "{}".'.format(cnv.link.GetName()))
      c4d.storage.ShowInFinder(cnv.files()['directory'])
    self.update_filelist()

  # c4d.gui.GeDialog

  def CreateLayout(self):
    self.SetTitle('Prototype to Node Plugin Converter')
    self.GroupBorderSpace(6, 6, 6, 6)
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 0, 1)  # MAIN {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)  # MAIN/LEFT {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)  # MAIN/LEFT/PARAMS {

    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_FIT, 2, 0, title='Export')  # MAIN/LEFT/PARAMS/EXPORTSETTINGS {
    self.GroupBorder(c4d.BORDER_THIN_IN)
    self.GroupBorderSpace(6, 6, 6, 6)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Mode')
    self.AddComboBox(self.ID_MODE, c4d.BFH_SCALEFIT)
    self.AddChild(self.ID_MODE, self.MODE_ALL, 'Resource Files + Plugin Stub')
    self.AddChild(self.ID_MODE, self.MODE_RESOURCE, 'Resource Files')
    self.AddChild(self.ID_MODE, self.MODE_PLUGINSTUB, 'Plugin Stub')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Resource Symbols')
    self.AddRadioGroup(self.ID_SYMBOLMODE, c4d.BFH_SCALEFIT)
    self.AddChild(self.ID_SYMBOLMODE, self.SYMBOLMODE_C4D, 'Cinema 4D')
    self.AddChild(self.ID_SYMBOLMODE, self.SYMBOLMODE_C4DDEV, 'C4DDev')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Indentation')
    self.AddRadioGroup(self.ID_INDENT, c4d.BFH_LEFT)
    self.AddChild(self.ID_INDENT, self.INDENT_TAB, 'Tab')
    self.AddChild(self.ID_INDENT, self.INDENT_2SPACE, '2 Spaces')
    self.AddChild(self.ID_INDENT, self.INDENT_4SPACE, '4 Spaces')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Overwrite')
    self.AddCheckbox(self.ID_OVERWRITE, c4d.BFH_SCALEFIT, 0, 0, '')
    self.GroupEnd() # } MAIN/LEFT/PARAMS/EXPORTSETTINGS

    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_FIT, 2, 0, title='Plugin')  # MAIN/LEFT/PARAMS/PLUGIN {
    self.GroupBorder(c4d.BORDER_THIN_IN)
    self.GroupBorderSpace(6, 6, 6, 6)
    self.AddStaticText(self.ID_LINK_TEXT, c4d.BFH_LEFT, name='Source *')
    self.AddLinkBoxGui(self.ID_LINK, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Name')
    self.AddEditText(self.ID_PLUGIN_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(self.ID_PLUGIN_ID_TEXT, c4d.BFH_LEFT, name='Plugin ID *')
    self.GroupBegin(0, c4d.BFH_SCALEFIT, 0, 1)
    self.AddEditText(self.ID_PLUGIN_ID, c4d.BFH_LEFT, 100)
    self.AddButton(self.ID_PLUGIN_ID_GET, c4d.BFH_LEFT, name='Get Plugin ID')
    self.GroupEnd()
    self.AddStaticText(0, c4d.BFH_LEFT, name='Resource Name')
    self.AddEditText(self.ID_RESOURCE_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Symbol Prefix')
    self.AddEditText(self.ID_SYMBOL_PREFIX, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Icon')
    self.AddFileSelector(self.ID_ICON_FILE, c4d.BFH_SCALEFIT, type='load')
    self.AddStaticText(self.ID_DIRECTORY_TEXT, c4d.BFH_LEFT, name='Plugin Directory')
    self.AddFileSelector(self.ID_DIRECTORY, c4d.BFH_SCALEFIT, type='directory')
    self.GroupEnd() # } MAIN/LEFT/PARAMS/EXPORTSETTINGS

    self.GroupEnd()  # } MAIN/LEFT/PARAMS
    self.GroupEnd()  # } MAIN/LEFT

    self.GroupBegin(self.ID_FILELIST_GROUP, c4d.BFH_RIGHT | c4d.BFV_FIT, 1, 0, title='Filelist', initw=120) # MAIN/RIGHT {
    self.GroupBorder(c4d.BORDER_THIN_IN)
    self.GroupBorderSpace(6, 6, 6, 6)
    self.GroupEnd()  # } MAIN/RIGHT
    self.GroupEnd()  # } MAIN

    self.GroupBegin(0, c4d.BFH_SCALEFIT, 0, 1) # BUTTONS {
    self.AddButton(self.ID_CREATE, c4d.BFH_CENTER, name='Create')
    self.AddStaticText(0, c4d.BFH_SCALEFIT)
    self.AddButton(self.ID_CANCEL, c4d.BFH_CENTER, name='Cancel')
    self.GroupEnd()  # } BUTTONS

    # Initialize values.
    self.SetBool(self.ID_OVERWRITE, False)
    self.SetInt32(self.ID_INDENT, self.INDENT_2SPACE)
    self.SetInt32(self.ID_SYMBOLMODE, self.SYMBOLMODE_C4DDEV)
    self.SetLink(self.ID_LINK, c4d.documents.GetActiveDocument().GetActiveObject())
    self.load_settings(update_ui=False)

    # Update UI.
    self.update_filelist()
    self.update_enabling()

    return True

  def Command(self, param_id, bc):
    if BaseDialog.Command(self, param_id, bc):
      return True

    # The actual ID that we create a widget with. The real parameter ID and
    # the virtual ID are different for compound widgets such as the file
    # selector.
    virtual_id = self.ReverseMapId(param_id)[1]

    if virtual_id in (
      # Check if anything changed that would have an influence on the filelist.
        self.ID_PLUGIN_NAME, self.ID_RESOURCE_NAME, self.ID_DIRECTORY,
        self.ID_ICON_FILE, self.ID_LINK, self.ID_MODE, self.ID_OVERWRITE):
      self.update_filelist()

    if virtual_id in (self.ID_LINK, self.ID_DIRECTORY, self.ID_PLUGIN_ID):
      # Update the create button's enable state.
      self.update_enabling()

    if virtual_id == self.ID_LINK:
      self.load_settings()
      return True
    elif virtual_id == self.ID_CREATE:
      self.do_create()
      return True
    elif virtual_id == self.ID_CANCEL:
      self.Close()
      return True
    elif virtual_id == self.ID_PLUGIN_ID_GET:
      webbrowser.open('http://www.plugincafe.com/forum/developer.asp')
      return True

    return True


class ScriptConverter(object):
  """
  Helper datastructure that contains all the information for converting
  scripts.
  """

  def __init__(self, plugin_name, plugin_id, script_file, icon_file, directory, overwrite=True):
    self.plugin_name = plugin_name
    self.plugin_id = plugin_id
    self.script_file = script_file
    self.icon_file = icon_file
    self.directory = directory
    self.overwrite = overwrite

  def autofill(self, default_plugin_name='My Plugin'):
    if not self.plugin_name:
      if self.script_file:
        self.plugin_name = os.path.splitext(os.path.basename(self.script_file))[0]
      else:
        self.plugin_name = default_plugin_name
    if not self.directory:
      write_dir = c4d.storage.GeGetC4DPath(c4d.C4D_PATH_STARTUPWRITE)
      dirname = re.sub('[^\w\d]+', '-', self.plugin_name).lower()
      self.directory = os.path.join(write_dir, 'plugins', dirname)

  def files(self):
    parent_dir = self.directory or self.plugin_name
    plugin_filename = re.sub('[^\w\d]+', '-', self.plugin_name).lower() + '.pyp'
    result = {
      'directory': parent_dir,
      'plugin': os.path.join(parent_dir, plugin_filename)
    }
    if self.icon_file:
      suffix = os.path.splitext(self.icon_file)[1]
      result['icon'] = j('res', 'icons', f('{self.plugin_name}{suffix}'))
    return result


class ScriptConverterDialog(BaseDialog):
  """
  This dialog implements the User Interface for converting Cinema 4D Python
  scripts for the Script Manager to Python plugins.
  """

  ID_PLUGIN_NAME = 1000
  ID_SCRIPT_FILE = 1001
  ID_ICON_FILE = 1002
  ID_PLUGIN_ID = 1003
  ID_PLUGIN_ID_GET = 1004
  ID_DIRECTORY = 1005
  ID_CREATE = 1006
  ID_CANCEL = 1007
  ID_PLUGIN_ID_TEXT = 1008
  ID_SCRIPT_FILE_TEXT = 1009

  def get_converter(self):
    return ScriptConverter(
      plugin_name = self.GetString(self.ID_PLUGIN_NAME),
      plugin_id = self.GetString(self.ID_PLUGIN_ID),
      script_file = self.GetFileSelectorString(self.ID_SCRIPT_FILE),
      icon_file = self.GetFileSelectorString(self.ID_ICON_FILE),
      directory = self.GetFileSelectorString(self.ID_DIRECTORY),
      overwrite = True
    )

  def update_enabling(self):
    cnv = self.get_converter()

    self.SetColor(self.ID_PLUGIN_ID_TEXT, c4d.COLOR_TEXT,
      COLOR_RED if not cnv.plugin_id.strip().isdigit() else None)
    self.SetColor(self.ID_SCRIPT_FILE_TEXT, c4d.COLOR_TEXT,
      COLOR_RED if not cnv.script_file else None)

    cnv.autofill()
    enable = True
    if not cnv.plugin_name or not cnv.script_file or \
        not cnv.plugin_id.strip().isdigit():
      enable = False
    self.Enable(self.ID_CREATE, enable)
    self.SetString(self.ID_PLUGIN_NAME, cnv.plugin_name, flags=c4d.EDITTEXT_HELPTEXT)
    self.SetFileSelectorString(self.ID_DIRECTORY, cnv.directory, flags=c4d.EDITTEXT_HELPTEXT)

  def do_create(self):
    cnv = self.get_converter()
    cnv.autofill()
    with open(cnv.script_file) as fp:
      future_import, global_code, member_code = \
        codeconv.refactor_command_script(fp.read(), indent='  ')
    # Indent the code appropriately for the plugin stub.
    member_code = '\n'.join('  ' + l for l in member_code.split('\n'))
    files = cnv.files()
    context = {
      'plugin_name': cnv.plugin_name,
      'plugin_id': cnv.plugin_id.strip(),
      'plugin_class': re.sub('[^\w\d]+', '', cnv.plugin_name),
      'plugin_icon': 'res/icons/' + os.path.basename(files['icon']) if files.get('icon') else None,
      'future_import': future_import,
      'global_code': global_code,
      'member_code': member_code,
    }
    with open(res_file('templates/command_plugin.txt')) as fp:
      template = fp.read()
    if files.get('icon') and files.get('icon') != cnv.icon_file:
      makedirs(os.path.dirname(files['icon']))
      try:
        shutil.copy(cnv.icon_file, files['icon'])
      except shutil.Error as exc:
        print('Warning: Error copying icon:', exc)
    print('Creating', files['plugin'])
    makedirs(os.path.dirname(files['plugin']))
    with open(files['plugin'], 'w') as fp:
      fp.write(little_jinja(template, context))
    c4d.storage.ShowInFinder(files['directory'])

  def CreateLayout(self):
    self.SetTitle('Script to Command Plugin Converter')
    self.GroupBorderSpace(6, 6, 6, 6)
    self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)  # MAIN {

    self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)  # MAIN/PARAMS {
    #self.GroupBorderSpace(6, 6, 6, 6)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Name')
    self.AddEditText(self.ID_PLUGIN_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(self.ID_PLUGIN_ID_TEXT, c4d.BFH_LEFT, name='Plugin ID *')
    self.GroupBegin(0, c4d.BFH_SCALEFIT, 0, 1)
    self.AddEditText(self.ID_PLUGIN_ID, c4d.BFH_LEFT, 100)
    self.AddButton(self.ID_PLUGIN_ID_GET, c4d.BFH_LEFT, name='Get Plugin ID')
    self.GroupEnd()
    self.AddStaticText(self.ID_SCRIPT_FILE_TEXT, c4d.BFH_LEFT, name='Script *')
    self.AddFileSelector(self.ID_SCRIPT_FILE, c4d.BFH_SCALEFIT, type='load')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Icon')
    self.AddFileSelector(self.ID_ICON_FILE, c4d.BFH_SCALEFIT, type='load')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Directory')
    self.AddFileSelector(self.ID_DIRECTORY, c4d.BFH_SCALEFIT, type='directory')
    self.GroupEnd()
    self.GroupEnd() # } MAIN/PARAMS

    self.GroupBegin(0, c4d.BFH_SCALEFIT, 0, 1)  # MAIN/BUTTONS {
    self.AddButton(self.ID_CREATE, c4d.BFH_LEFT, name='Create')
    self.AddStaticText(0, c4d.BFH_SCALEFIT)
    self.AddButton(self.ID_CANCEL, c4d.BFH_LEFT, name='Cancel')
    self.GroupEnd() # } MAIN/BUTTONS

    self.GroupEnd() # } MAIN

    self.update_enabling()
    return True

  def Command(self, param_id, bc):
    if super(ScriptConverterDialog, self).Command(param_id, bc):
      return True
    self.update_enabling()
    virtual_id = self.ReverseMapId(param_id)[1]
    if virtual_id == self.ID_CREATE:
      self.do_create()
      return True
    if virtual_id == self.ID_CANCEL:
      self.Close()
      return True
    return True


def main():
  DialogOpenerCommand(PrototypeConverterDialog)\
    .Register(ID_PLUGIN_CONVERTER, 'Prototype to Node Plugin Converter')
  DialogOpenerCommand(ScriptConverterDialog)\
    .Register(ID_SCRIPT_CONVERTER, 'Script to Command Plugin Converter')
