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


def get_subcontainer(bc, sub_id):
  if not has_subcontainer(bc, sub_id):
    bc.SetContainer(sub_id, c4d.BaseContainer())
    assert has_subcontainer(bc, sub_id)
  return bc.GetContainerInstance(sub_id)


def has_subcontainer(bc, sub_id):
  return bc.GetType(sub_id) == c4d.DA_CONTAINER


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

  helptext_color = c4d.Vector(0.4)

  def __init__(self):
    super(BaseDialog, self).__init__()
    self.__widgets = {}
    self.__reverse_cache = {}
    self.__idcounter = 9000000
    self.__edit_texts = set()

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

  def ForwardMapId(self, virtual_id):
    """
    A generator for IDs that of the virtual parameter *virtual_id* or just
    the *virtual_id* if it does not correspond to a virtual parameter.
    """

    widget = self.__widgets.get(virtual_id, {})
    has_id = False
    for key in widget:
      if key.startswith('id.'):
        yield widget[key]
        has_id = True
    if not has_id:
      yield virtual_id

  def GetColor(self, colorid):
    c = self.GetColorRGB(colorid)
    return c4d.Vector(c['r'] / 255., c['g'] / 255., c['b'] / 255.)

  def SetColor(self, param_id, colorid, color=None):
    if color is None:
      color = self.GetColor(colorid)
    for real_id in self.ForwardMapId(param_id):
      self.SetDefaultColor(real_id, colorid, color)

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

  # @override
  def SetString(self, param_id, value, tristate=False, flags=0):
    if flags == 0 and param_id in self.__edit_texts:
      color = None if value else self.helptext_color
      self.SetColor(param_id, c4d.COLOR_TEXT_EDIT, color)
    super(BaseDialog, self).SetString(param_id, value, tristate, flags)

  # @override
  def AddEditText(self, param_id, *args, **kwargs):
    """
    An extended version of the #GeDialog.AddEditText() function that records
    the ID in order to change the widget's text color if only the help text
    is displayed.
    """

    self.__edit_texts.add(param_id)
    return super(BaseDialog, self).AddEditText(param_id, *args, **kwargs)

  # @override
  def Command(self, param, bc):
    # Invoke virtual widget callbacks.
    event = {'type': 'command', 'param': param, 'bc': bc}
    for widget in self.__widgets.values():
      callback = widget.get('callback')
      if callback:
        if callback(widget, event):
          return True

    # Update the text color if a text widget was changed.
    if param in self.__edit_texts and bc.GetType(c4d.BFM_ACTION_VALUE) != c4d.DA_NIL:
      color = None if bc[c4d.BFM_ACTION_VALUE] else self.helptext_color
      self.SetColor(param, c4d.COLOR_TEXT_EDIT, color)

    return False

  # @override
  def InitValues(self):
    for param_id in self.__edit_texts:
      color = None if self.GetString(param_id) else self.helptext_color
      self.SetColor(param_id, c4d.COLOR_TEXT_EDIT, color)
    return True
