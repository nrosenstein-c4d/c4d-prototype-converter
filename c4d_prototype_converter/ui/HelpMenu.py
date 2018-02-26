
import c4d
import nr.c4d.ui
import textwrap
import webbrowser


class HelpMenu(nr.c4d.ui.Component):

  def __init__(self, id=None):
    super(HelpMenu, self).__init__(id)
    self.load_xml_file('./HelpMenu.xml')
    self['about'].add_event_listener('click', self._on_about)
    self['help'].add_event_listener('click', self._on_help)
    self['report'].add_event_listener('click', self._on_report)

  def _on_about(self, item):
    c4d.gui.MessageDialog(textwrap.dedent('''
      C4D Prototype Converter

      Programming and Design: Niklas Rosenstein
      Concept and Design: Donovan Keith

      This project was sponsored by Maxon US.
    ''').strip())

  def _on_help(self, item):
    webbrowser.open('https://github.com/NiklasRosenstein/c4d-prototype-converter/wiki')

  def _on_report(self, item):
    webbrowser.open('https://github.com/NiklasRosenstein/c4d-prototype-converter/issues')
