## Cinema 4D Prototype Converter

![](https://img.shields.io/badge/License-MIT-yellow.svg)

This plugin aids you in converting your Cinema 4D Python plugin prototype
to a plugin. It uses `lib2to3` to refactor your code.

### Features

<table>
  <tr>
    <th colspan="2" align="left">Script Converter</th>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/OV08gew.png" width="auto"></td>
    <td>

This tool converts a Cinema 4D Python Script to a `CommandData` plugin. The
script should contain a `main()` function. This function will be automatically
refactored to match the `CommandData.Execute()` method function.
    </td>
  </tr>
  <tr>
    <th colspan="2" align="left">Prototype Converter</th>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/1b1kzsu.png" width="auto"></td>
    <td>

This tool converts a Cinema 4D Python Generator or Expression Tag to a
`ObjectData` or `TagData` plugin. It will also convert any User Data on
the object/tag to a Cinema 4D description resource. The `main()` and
`message()` functions will be automatically refactored to match the
`ObjectData.GetVirtualObjects()`/`TagData.Execute()` and `NodeData.Message()`
methods respectively.
    </td>
  </tr>
</table>

### Ideas for the Future

* Report possible errors during conversion (eg. referencing the variables
  `doc` or `op` in global functions without previously declaring them)
* Automatically replace references to `op[c4d.ID_USERDATA, X]` syntax with
  the automatically generated resource symbol

### Acknowledgements

This project is sponsored by Maxon US.

---

<p align="center">Copyright &copy 2018 Niklas Rosenstein</p>
