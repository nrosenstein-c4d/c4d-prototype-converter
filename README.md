## Cinema 4D Prototype Converter

![](https://img.shields.io/badge/License-MIT-yellow.svg)

This plugin aids you in converting your Cinema 4D Python plugin prototype
to a plugin.

![](https://i.imgur.com/1b1kzsu.png)

![](https://i.imgur.com/OV08gew.png)

### Features

* Converts UserData to Cinema 4D description resource files
* Generates a Python plugin template file
* Automatically converts code from Python Generators or Expression Tags
  to valid code in the plugin template (WIP)
* A tool to convert Scripts to CommandData plugins (WIP)

### Ideas for the Future

* Report possible errors during conversion (eg. referencing the variables
  `doc` or `op` in global functions without previously declaring them)
* Automatically replace references to `op[c4d.ID_USERDATA, X]` syntax with
  the automatically generated resource symbol

### Acknowledgements

This project is sponsored by Maxon US.

---

<p align="center">Copyright &copy 2018 Niklas Rosenstein</p>
