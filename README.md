## Cinema 4D Prototype Converter

![](https://img.shields.io/badge/License-MIT-yellow.svg)

This plugin aids you in converting your Cinema 4D Python plugin prototype
to a plugin.

![](https://i.imgur.com/VcgkutH.png)

### Features

* Converts UserData to Cinema 4D description resource files
* Generates a Python plugin template file

### Planned Features

* Automatic conversion of Python Generators to ObjectData plugins (and alike) \*
* A tool to convert Scripts to CommandData plugins \*
* Reporting of possible errors during conversion (eg. referencing the
  variables `doc` or `op` in global functions without previously declaring
  them)
* Automatically replacing references to `op[c4d.ID_USERDATA, X]` syntax with
  the respectively automatically generated resource symbol

> \* Milestones set by the sponsors.

### Acknowledgements

This project is sponsored by Maxon US.

---

<p align="center">Copyright &copy 2018 Niklas Rosenstein</p>
