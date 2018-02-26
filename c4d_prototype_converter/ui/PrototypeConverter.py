
from __future__ import print_function
import collections
import c4d
import os
import nr.c4d.ui
import re
import shutil
import sys
import traceback
import webbrowser
from .HelpMenu import HelpMenu
from .FileList import FileList
from ..utils import Node, makedirs
from ..generics import HashDict
from ..c4dutils import unicode_refreplace, get_subcontainer, has_subcontainer
from ..little_jinja import little_jinja
from .. import res, refactor

ID_PLUGIN_CONVERTER = 1040648


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


def refactor_expression_script(code, kind, symbols_map):
  # Replace occurences of [c4d.ID_USERDATA, X] with the symbol.
  uid_reverse_map = {did[-1].id: sym for did, sym in
    symbols_map.descid_to_symbol.iteritems()}
  def subfun(x):
    if x in uid_reverse_map:
      return 'res.' + uid_reverse_map[x]
    else:
      print('note: could not reverse map [c4d.ID_USERDATA, {}]'.format(x))
      return None
  code = refactor.fix_userdata_access(code, subfun)

  code = refactor.indentation(code, '  ')  # To match the indentation of the plugin stub.
  code, docstring = refactor.split_docstring(code)
  code, msg_code = refactor.split_and_refactor_global_function(
    code, 'message', 'Message', ['self', 'op'], add_statement='return True')

  member_code = msg_code

  if kind == 'ObjectData':
    code, gvo_code = refactor.split_and_refactor_global_function(
      code, 'main', 'GetVirtualObjects', ['self', 'op', 'hh'])
    member_code += '\n\n' + gvo_code
  elif kind == 'TagData':
    code, exec_code = refactor.split_and_refactor_global_function(
      code, 'main', 'Execute', ['self', 'op', 'doc', 'host', 'bt', 'priority', 'flags'],
      add_statement='return c4d.EXECUTIONRESULT_OK')
    member_code += '\n\n' + exec_code
  else:
    raise ValueError(kind)

  # Must be done last, as afterwards the *code* may no longer be valid
  # syntax if print_function was used.
  code, future_line = refactor.split_future_imports(code)

  return {
    'future_line': future_line,
    'docstring': docstring,
    'code': code,
    'member_code': member_code
  }


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


class Converter(object):
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
    self.plugin_id = plugin_id.strip()
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
    if not self.icon_file:
      self.icon_file = res.path('res/icons/default-icon.tiff')

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
      raise RuntimeError('Converter.directory must be set')
    if not self.link:
      raise RuntimeError('Converter.link must be set')
    if not self.plugin_id.isdigit():
      raise RuntimeError('Converter.plugin_id is invalid')
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
    # initialize our symbol_map.
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
      with open(res.local('../templates/node_plugin.txt')) as fp:
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
        code_parts = refactor_expression_script(code, kind, symbol_map)
      else:
        code_parts = {}

      if code_parts.get('member_code'):
        # Indent the code appropriately for the plugin stub.
        code_parts['member_code'] = '\n'.join('  ' + l
          for l in code_parts['member_code'].split('\n'))

      context = {
        'c4d': c4d,
        'link': self.link,
        'parameters': [
          (symbol_map.descid_to_node[did], did, bc)
          for did, bc in ud if did in symbol_map.descid_to_node],
        'hardcoded_description': [
          (symbol_map.descid_to_node[did], params)
          for did, params in symbol_map.hardcoded_description.items()
        ],
        'docstrings': code_parts.get('docstring'),
        'future_import': code_parts.get('future_line'),
        'global_code': code_parts.get('code'),
        'member_code': code_parts.get('member_code'),
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
      code = refactor.indentation(code, self.indent)
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


class PrototypeConverter(nr.c4d.ui.Component):

  def render(self, dialog):
    self.flush_children()
    self.load_xml_file('./PrototypeConverter.xml')
    self['create'].add_event_listener('click', self.on_create)
    for key in ('source', 'plugin_name', 'resource_name', 'icon_file',
                'plugin_directory', 'overwrite', 'export_mode'):
      self[key].add_event_listener('value-changed', self.on_change)
    self['get_plugin_id'].add_event_listener('click', self.on_get_plugin_id)
    super(PrototypeConverter, self).render(dialog)

  def init_values(self, dialog):
    doc = c4d.documents.GetActiveDocument()
    self['source'].set_link(doc.GetActiveObject())
    self.on_change(None)

  def get_converter(self):
    export_mode = self['export_mode'].active_item.ident
    symbol_mode = self['symbol_mode'].active_item.ident
    indent_mode = self['indent_mode'].active_item.ident
    indent = {'tab': '\t', '2space': '  ', '4space': '    '}[indent_mode]
    return Converter(
      link = self['source'].get_link(),
      plugin_name = self['plugin_name'].value,
      plugin_id = self['plugin_id'].value.strip(),
      resource_name = self['resource_name'].value,
      symbol_prefix = self['symbol_prefix'].value,
      icon_file = self['icon_file'].value,
      directory = self['plugin_directory'].value,
      write_plugin_stub = export_mode in ('all', 'plugin'),
      write_resources = export_mode in ('all', 'res'),
      symbol_mode = symbol_mode,
      overwrite = self['overwrite'].value,
      indent = indent
    )

  def on_change(self, widget):
    cnv = self.get_converter()
    cnv.autofill()
    files = cnv.files()
    parent = os.path.dirname(files.pop('directory'))
    files = files.values()
    self['filelist'].set_files(files, parent)
    self['plugin_name'].set_helptext(cnv.plugin_name)
    self['resource_name'].set_helptext(cnv.resource_name)
    self['symbol_prefix'].set_helptext(cnv.symbol_prefix)
    self['plugin_directory'].set_helptext(parent)

  def on_create(self, button):
    cnv = self.get_converter()
    cnv.autofill()
    try:
      cnv.create()
    except Exception as exc:
      traceback.print_exc()
      c4d.gui.MessageDialog(str(exc))
    else:
      cnv.save_to_link()
      print('Saved settings to object "{}".'.format(cnv.link.GetName()))
      c4d.storage.ShowInFinder(cnv.files()['directory'])
    self.on_change(None)

  def on_get_plugin_id(self, button):
    webbrowser.open('http://www.plugincafe.com/forum/developer.asp')


  #self['filelist'].set_files(['Users/Desktop', 'Users/Desktop/foo.c'], 'Users')



window = nr.c4d.ui.DialogWindow(PrototypeConverter(), title='Prototype Converter')
command = nr.c4d.ui.DialogOpenerCommand(ID_PLUGIN_CONVERTER, window)
command.Register('Prototype Converter...', c4d.PLUGINFLAG_HIDE)
