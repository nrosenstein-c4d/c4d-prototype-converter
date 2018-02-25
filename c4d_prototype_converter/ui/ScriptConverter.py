
import nr.c4d.ui
from .HelpMenu import HelpMenu
from .FileList import FileList


class ScriptConverter(nr.c4d.ui.native.DialogWindow):

  def CreateLayout(self):
    self.load_xml_file('./ScriptConverter.xml')
    self.widgets['filelist'].set_files(['Users/niklas', 'Users/niklas/test.c'], 'Users')
    return super(ScriptConverter, self).CreateLayout()
