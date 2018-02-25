
import c4d
import nr.c4d.ui
import webbrowser


class HelpMenu(nr.c4d.ui.native.SubComponent):

  def __init__(self, id=None):
    super(HelpMenu, self).__init__(id)
    self.load_xml_file('./HelpMenu.xml')
    self['about'].add_event_listener('click', self._on_about)
    self['help'].add_event_listener('click', self._on_help)
    self['report'].add_event_listener('click', self._on_report)

  def _on_about(self, item):
    c4d.gui.MessageDialog('C4D Prototype Converter')

  def _on_help(self, item):
    webbrowser.open('https://github.com/NiklasRosenstein/c4d-prototyping-converter/wiki')

  def _on_report(self, item):
    webbrowser.open('https://github.com/NiklasRosenstein/c4d-prototyping-converter/issues')
