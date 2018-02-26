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
from nr.c4d.gui import find_menu_resource
from .ui.ScriptConverter import ID_SCRIPT_CONVERTER
from .ui.PrototypeConverter import ID_PLUGIN_CONVERTER


def PluginMessage(msg_id, data):
  if msg_id == c4d.C4DPL_BUILDMENU:
    bc = find_menu_resource('M_EDITOR', 'IDS_SCRIPTING_MAIN')
    bc.InsData(c4d.MENURESOURCE_SEPERATOR, True)
    bc.InsData(c4d.MENURESOURCE_COMMAND, 'PLUGIN_CMD_' + str(ID_SCRIPT_CONVERTER))
    bc.InsData(c4d.MENURESOURCE_COMMAND, 'PLUGIN_CMD_' + str(ID_PLUGIN_CONVERTER))
    return True
  return False
