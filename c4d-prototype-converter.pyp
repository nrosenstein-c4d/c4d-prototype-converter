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

import c4d
import collections
import errno
import os
import re
import sys


# ============================================================================
# Helpers
# ============================================================================

class DialogOpenerCommand(c4d.plugins.CommandData):
  """
  Command plugin that opens a dialog.
  """

  def __init__(self, dlg_factory, dlgtype=c4d.DLG_TYPE_ASYNC, *open_args, **open_kwargs):
    super(DialogOpenerCommand, self).__init__()
    self.dlg_factory = dlg_factory
    self.open_args = (dlgtype,) + open_args
    self.open_kwargs = open_kwargs
    self.dlg = None

  def Execute(self, doc):
    if not self.dlg: self.dlg = self.dlg_factory()
    self.dlg.Open(*self.open_args, **self.open_kwargs)
    return True

  def Register(self, plugin_id, name, info=0, icon=None, help=''):
    return c4d.plugins.RegisterCommandPlugin(
      plugin_id, name, info, icon, help, self)


class BaseDialog(c4d.gui.GeDialog):
  """
  A new base class for Cinema 4D dialogs that provides a bunch of useful
  methods for managing widgets.
  """

  def __init__(self):
    super(BaseDialog, self).__init__()
    self.__widgets = {}
    self.__reverse_cache = {}
    self.__idcounter = 9000000

  def AllocId(self):
    """
    Allocates a new ID. Used for widgets that require more than one real widget.
    """

    result = self.__idcounter
    self.__idcounter += 1
    return result

  def ReverseMapId(self, param_id):
    """
    Reverse-maps a real parameter ID to the ID of a virtual widget. If there
    is no virtual widget that allocated *param_id*, returns (None, param_id).
    If a widget has been found that uses *param_id*, returns (name, widget_id).
    """

    try:
      return self.__reverse_cache[param_id]
    except KeyError:
      result = None
      for widget_id, widget in self.__widgets.items():
        for key in widget:
          if key.startswith('id.') and widget[key] == param_id:
            result = key[3:], widget_id
            break
        if result: break
      if not result:
        result = (None, param_id)
      self.__reverse_cache[param_id] = result
      return result

  def SendCommand(self, param_id, bc=None):
    if bc is None:
      bc = c4d.BaseContainer()
    bc.SetId(c4d.BFM_ACTION)
    bc.SetInt32(c4d.BFM_ACTION_ID, param_id)
    return self.Message(bc, c4d.BaseContainer())

  def __FileSelectorCallback(self, widget, event):
    if event['type'] == 'command' and event['param'] == widget['id.button']:
      flags = {
        'load': c4d.FILESELECT_LOAD,
        'save': c4d.FILESELECT_SAVE,
        'directory': c4d.FILESELECT_DIRECTORY
      }[widget['fileselecttype']]
      path = c4d.storage.LoadDialog(flags=flags)
      if path:
        self.SetString(widget['id.string'], path)
        self.SendCommand(widget['id.string'])
      return True

  def AddFileSelector(self, param_id, flags, type='load'):
    if type not in ('load', 'save', 'directory'):
      raise ValueError('invalid type: {!r}'.format(type))
    widget = {
      'type': 'fileselector',
      'id.string': self.AllocId(),
      'id.button': self.AllocId(),
      'callback': self.__FileSelectorCallback,
      'fileselecttype': type
    }
    self.__widgets[param_id] = widget
    self.GroupBegin(0, flags, 2, 0)
    self.AddEditText(widget['id.string'], c4d.BFH_SCALEFIT | c4d.BFV_FIT)
    self.AddButton(widget['id.button'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='...')
    self.GroupEnd()

  def GetFileSelectorString(self, param_id):
    return self.GetString(self.__widgets[param_id]['id.string'])

  def SetFileSelectorString(self, param_id, *args, **kwargs):
    self.SetString(self.__widgets[param_id]['id.string'], *args, **kwargs)

  def AddLinkBoxGui(self, param_id, flags, minw=0, minh=0, customdata=None):
    if customdata is None:
      customdata = c4d.BaseContainer()
    elif isinstance(customdata, dict):
      bc = c4d.BaseContainer()
      for key, value in customdata.items():
        bc[key] = value
      customdata = bc
    elif not isinstance(customdata, c4d.BaseContainer):
      raise TypeError('expected one of {NoneType,dict,c4d.BaseContainer}')
    widget = {
      'type': 'linkbox',
      'gui': self.AddCustomGui(param_id, c4d.CUSTOMGUI_LINKBOX, "", flags, minw, minh, customdata)
    }
    self.__widgets[param_id] = widget
    return widget['gui']

  def GetLink(self, param_id, doc=None, instance=0):
    return self.__widgets[param_id]['gui'].GetLink(doc, instance)

  def SetLink(self, param_id, obj):
    self.__widgets[param_id]['gui'].SetLink(obj)

  # c4d.gui.GeDialog

  def Command(self, param, bc):
    event = {'type': 'command', 'param': param, 'bc': bc}
    for widget in self.__widgets.values():
      callback = widget.get('callback')
      if callback:
        if callback(widget, event):
          return True
    return False


class HashableDescid(object):

  def __init__(self, descid):
    self.descid = descid

  def __hash__(self):
    return hash(tuple(
      (l.id, l.dtype, l.creator)
      for l in (
        self.descid[i] for i in xrange(self.descid.GetDepth())
      )
    ))

  def __eq__(self, other):
    if isinstance(other, HashableDescid):
      return other.descid == self.descid
    return False

  def __ne__(self, other):
    return not (self == other)


def makedirs(path, raise_on_exists=False):
  try:
    os.makedirs(path)
  except OSError as exc:
    if raise_on_exists or exc.errno != errno.EEXIST:
      raise


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


def file_tree(files, parent=None, flat=False):
  """
  Produces a tree structure from a list of filenames. Returns a list of the
  root entries. If *flat* is set to #True, the returned list contains a flat
  version of all entries in the tree.
  """

  Entry = collections.namedtuple('Entry', 'path isdir sub parent')
  entries = {}

  files = (os.path.normpath(x) for x in files)
  if parent:
    files = (os.path.relpath(x, parent) for x in files)

  if flat:
    order = []
  for filename in files:
    parent_entry = None
    for path in reversed(list(path_parents(filename))):
      entry = entries.get(path)
      if not entry:
        entry = Entry(path, path!=filename, {}, parent_entry)  # TODO: Use weak references -- but can't be used with tuples/namedtuples
        entries[path] = entry
        base = os.path.basename(path)
        if parent_entry:
          parent_entry.sub[base] = entries
      parent_entry = entry
    if flat:
      order.append(entry)

  if flat:
    result = []
    for entry in order:
      index = len(result)
      while entry:
        if entry in result: break
        result.insert(index, entry)
        entry = entry.parent
    return result
  else:
    return [x for x in entries.values() if not x.parent]


# ============================================================================
# UserData to Description Resource Converter
# ============================================================================

class UserDataConverter(object):
  """
  This object holds the information on how the description resource will
  be generated.
  """

  class SymbolMap(object):

    def __init__(self, prefix):
      self.curr_id = 1000
      self.symbols = collections.OrderedDict()
      self.descid_to_symbol = {}
      self.prefix = prefix

    def get_unique_symbol(self, descid, name, value=None):
      base = self.prefix + re.sub('[^\w\d_]', '_', name).upper().rstrip('_')
      index = 0
      while True:
        symbol = base + (str(index) if index != 0 else '')
        if symbol not in self.symbols: break
        index += 1
      if value is None:
        value = self.curr_id
        self.curr_id += 1
      self.symbols[symbol] = value
      if descid is not None:
        self.descid_to_symbol[HashableDescid(descid)] = symbol
      return symbol, value

  def __init__(self, link, plugin_name, plugin_id, resource_name,
               symbol_prefix, icon_file, directory, indent='  '):
    self.link = link
    self.plugin_name = plugin_name
    self.plugin_id = plugin_id
    self.resource_name = resource_name
    self.symbol_prefix = symbol_prefix
    self.icon_file = icon_file
    self.directory = directory
    self.indent = indent

  def autofill(self, default_plugin_name='My Plugin'):
    if not self.plugin_name:
      self.plugin_name = (self.link.GetName() if self.link else '')
    if not self.plugin_name:
      self.plugin_name = default_plugin_name
    if not self.resource_name:
      resource_prefix = 'O'
      if self.link:
        if self.link.CheckType(c4d.Obase): resource_prefix = 'O'
        elif self.link.CheckType(c4d.Tbase): resource_prefix = 'T'
        elif self.link.CheckType(c4d.Xbase): resource_prefix = 'X'
        else: resource_prefix = ''
      self.resource_name = re.sub('[^\w\d]+', '', self.plugin_name).lower()
      self.resource_name = resource_prefix + self.resource_name

  def files(self):
    f = lambda s: s.format(**sys._getframe(1).f_locals)
    j = os.path.join
    parent_dir = self.directory or self.plugin_name
    result = {
      'directory': parent_dir,
      'c4d_symbols': j(parent_dir, 'res', 'c4d_symbols.h'),
      'header': j(parent_dir, 'res', 'description', f('{self.resource_name}.h')),
      'description': j(parent_dir, 'res', 'description', f('{self.resource_name}.res')),
      'strings_us': j(parent_dir, 'res', 'strings_us', 'description', f('{self.resource_name}.str'))
    }
    if self.icon_file:
      suffix = os.path.splitext(self.icon_file)[1]
      result['icon'] = j(parent_dir, 'res', 'icons', f('{self.plugin_name}{suffix}'))
    return result

  def create(self, overwrite=False):
    if not self.directory:
      raise RuntimeError('UserDataConverter.directory must be set')
    if not self.link:
      raise RuntimeError('UserDataConverter.link must be set')
    if self.icon_file and not os.path.isfile(self.icon_file):
      raise IOError('File "{}" does not exist'.format(self.icon_file))

    files = self.files()
    if not overwrite:
      for k in ('header', 'description', 'icon', 'strings_us'):
        v = files.get(k)
        if not v: continue
        if os.path.exists(v):
          raise IOError('File "{}" already exists'.format(v))

    makedirs(os.path.dirname(files['c4d_symbols']))
    if not os.path.isfile(files['c4d_symbols']):
      makedirs(os.path.dirname(files['c4d_symbols']))
      with open(files['c4d_symbols'], 'w') as fp:
        fp.write('#pragma once\nenum {\n};\n')

    # TODO: Collect resource symbol information from userdata.

    ud = self.link.GetUserDataContainer()
    symbol_map = self.SymbolMap(self.symbol_prefix)

    # Render the symbols to the description header. This will also
    # initialize our symbols_map.
    makedirs(os.path.dirname(files['header']))
    with open(files['header'], 'w') as fp:
      fp.write('#pragma once\nenum {\n')
      if self.plugin_id:
        fp.write(self.indent + '{self.resource_name} = {self.plugin_id},\n'.format(self=self))
      for descid, bc in ud:
        self.render_symbol(fp, descid, bc, symbol_map)
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
        # TODO: Render UserData parameters
        fp.write(self.indent + '}\n')
      # TODO: Render UserData parameters that are not inside the main UserData group
      fp.write('}\n')

    makedirs(os.path.dirname(files['strings_us']))
    with open(files['strings_us'], 'w') as fp:
      fp.write('STRINGTABLE {self.resource_name} {{\n'.format(self=self))
      fp.write('{self.indent}{self.resource_name} "{self.plugin_name}";\n'.format(self=self))
      # TODO: Render UserData symbols
      fp.write('}\n')

    if self.icon_file:
      makedirs(os.path.dirname(files['icon']))
      shutil.copy(self.icon_file, files['icon'])

  def render_symbol(self, fp, descid, bc, symbol_map):
    # Find a unique name for the symbol.
    name = bc[c4d.DESC_NAME]
    if descid[-1].dtype == c4d.DTYPE_GROUP:
      name += '_GROUP'

    sym, value = symbol_map.get_unique_symbol(descid, name)
    fp.write(self.indent + '{} = {},\n'.format(sym, value))
    children = bc.GetContainerInstance(c4d.DESC_CYCLE)
    if children:
      for value, name in children:
        child_sym = symbol_map.get_unique_symbol(None, sym + '_' + name, value)[0]
        fp.write(self.indent * 2 + '{} = {},\n'.format(child_sym, value))

    return sym


class UserDataToDescriptionResourceConverterDialog(BaseDialog):
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

  INDENT_TAB = 0
  INDENT_2SPACE = 1
  INDENT_4SPACE = 2

  def get_converter(self):
    return UserDataConverter(
      link = self.GetLink(self.ID_LINK),
      plugin_name = self.GetString(self.ID_PLUGIN_NAME),
      plugin_id = self.GetString(self.ID_PLUGIN_ID),
      resource_name = self.GetString(self.ID_RESOURCE_NAME),
      symbol_prefix = self.GetString(self.ID_SYMBOL_PREFIX),
      icon_file = self.GetFileSelectorString(self.ID_ICON_FILE),
      directory = self.GetFileSelectorString(self.ID_DIRECTORY),
      indent = {self.INDENT_TAB: '\t', self.INDENT_2SPACE: '  ', self.INDENT_4SPACE: '    '}[self.GetInt32(self.ID_INDENT)]
    )

  def update_filelist(self):
    cnv = self.get_converter()
    cnv.autofill()
    files = cnv.files()

    parent = os.path.dirname(files.pop('directory'))
    files = sorted(files.values(), key=str.lower)

    self.LayoutFlushGroup(self.ID_FILELIST_GROUP)
    for entry in file_tree(files, parent=parent, flat=True):
      depth = 0
      parent = entry.parent
      while parent:
        depth += 1
        parent = parent.parent
      name = '  ' * depth + os.path.basename(entry.path)
      if entry.isdir:
        name += '/'
      self.AddStaticText(0, c4d.BFH_LEFT, name=name)
    self.LayoutChanged(self.ID_FILELIST_GROUP)

  def update_create_enabling(self):
    # TODO: We could also update the default color of the parameters
    #        to visually indicate which parameters need to be filled.
    enabled = True
    if self.GetLink(self.ID_LINK) is None: enabled = False
    if not self.GetFileSelectorString(self.ID_DIRECTORY): enabled = False
    if not self.GetString(self.ID_PLUGIN_ID).isdigit(): enabled = False
    self.Enable(self.ID_CREATE, enabled)

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
      cnv.create(overwrite=self.GetBool(self.ID_OVERWRITE))
    except IOError as exc:
      c4d.gui.MessageDialog(str(exc))

  # c4d.gui.GeDialog

  def CreateLayout(self):
    self.SetTitle('UserData to Description Resource (.res) Converter')
    self.GroupBorderSpace(6, 6, 6, 6)
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 0, 1)  # MAIN {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)  # MAIN/LEFT {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_FIT, 2, 0)  # MAIN/LEFT/PARAMS {
    self.AddStaticText(0, c4d.BFH_LEFT, name='Source')
    self.AddLinkBoxGui(self.ID_LINK, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Name')
    self.AddEditText(self.ID_PLUGIN_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin ID')
    self.AddEditText(self.ID_PLUGIN_ID, c4d.BFH_LEFT, 100)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Resource Name')
    self.AddEditText(self.ID_RESOURCE_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Symbol Prefix')
    self.AddEditText(self.ID_SYMBOL_PREFIX, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Icon')
    self.AddFileSelector(self.ID_ICON_FILE, c4d.BFH_SCALEFIT, type='load')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Directory')
    self.AddFileSelector(self.ID_DIRECTORY, c4d.BFH_SCALEFIT, type='directory')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Indentation')
    self.AddComboBox(self.ID_INDENT, c4d.BFH_LEFT)
    self.AddChild(self.ID_INDENT, self.INDENT_TAB, 'Tab')
    self.AddChild(self.ID_INDENT, self.INDENT_2SPACE, '2 Spaces')
    self.AddChild(self.ID_INDENT, self.INDENT_4SPACE, '4 Spaces')
    self.AddCheckbox(self.ID_OVERWRITE, c4d.BFH_LEFT, 0, 0, name='Overwrite')
    self.GroupBegin(0, c4d.BFH_CENTER, 0, 1) # MAIN/LEFT/PARAMS/BUTTONS {
    self.AddButton(self.ID_CREATE, c4d.BFH_CENTER, name='Create')
    self.AddButton(self.ID_CANCEL, c4d.BFH_CENTER, name='Cancel')
    self.GroupEnd()  # } MAIN/LEFT/PARAMS/BUTTONS
    self.GroupEnd()  # } MAIN/LEFT/PARAMS
    self.GroupEnd()  # } MAIN/LEFT
    self.AddSeparatorV(0, c4d.BFV_SCALEFIT)
    self.GroupBegin(self.ID_FILELIST_GROUP, c4d.BFH_RIGHT | c4d.BFV_SCALEFIT, 1, 0) # MAIN/RIGHT {
    self.GroupBorderSpace(4, 4, 4, 4)
    self.GroupEnd()  # } MAIN/RIGHT
    self.GroupEnd()  # } MAIN
    self.update_filelist()
    self.update_create_enabling()
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
        self.ID_ICON_FILE, self.ID_LINK):
      self.update_filelist()

    if virtual_id in (self.ID_LINK, self.ID_DIRECTORY, self.ID_PLUGIN_ID):
      # Update the create button's enable state.
      self.update_create_enabling()

    if virtual_id == self.ID_CREATE:
      self.do_create()
      return True
    elif virtual_id == self.ID_CANCEL:
      self.Close()
      return True

    return True


def main():
  DialogOpenerCommand(UserDataToDescriptionResourceConverterDialog)\
    .Register(1040648, 'UserData to .res Converter')


if __name__ == '__main__':
  main()
