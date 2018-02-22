## Cinema 4D Prototype Converter

![](https://img.shields.io/badge/License-MIT-yellow.svg)

This plugin aids you in converting your Cinema 4D Python plugin prototype
to a plugin.

<table>
  <tr>
    <th colspan="2" align="left">Script Converter</th>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/OV08gew.png" width="auto"></td>
    <td>

This tool converts a Cinema 4D Python Script to a `CommandData` plugin.
Scripts you convert with this tool should have a `main()` function.

#### Features

* The `main()` function will be automatically converted to a
  `CommandData.Execute()` method

    </td>
  </tr>
  <tr>
    <th colspan="2" align="left">Prototype Converter</th>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/1b1kzsu.png" width="auto"></td>
    <td>

This tool converts a Cinema 4D Python Generator or Expression Tag to a
`ObjectData` or `TagData` plugin.

#### Features

* Converts UserData to description resource files
* Converts `main()` and `message()` functions in your Python code to the
  respective plugin member method (`GetVirtualObjects()`, `Execute()`, `Message()`)

    </td>
  </tr>
</table>

### FAQ

<details><summary>How to install the Plugin?</summary>

> Simply download the source code from the GitHub repository and unpack it
> into your Cinema 4D plugins folder.
>
> ![](https://i.imgur.com/v1KiKNf.png)

</details>

<details><summary>Where to find the Plugin in Cinema 4D?</summary>

> After you have installed the plugin, you can find it in the Cinema 4D
> Script menu.
> 
> ![](https://i.imgur.com/lgRnazt.png)

</details>

<details><summary>How does the code refactoring work?</summary>

> We use the `lib2to3` module from the Python standard library to parse and
> transform your code so that it (somewhat) matches the way it needs to be
> for Python plugins and to adjust the indentation.

</details>

### Ideas for the Future

* Report possible errors during conversion (eg. referencing the variables
  `doc` or `op` in global functions without previously declaring them)
* Automatically replace references to `op[c4d.ID_USERDATA, X]` syntax with
  the automatically generated resource symbol

### Acknowledgements

This project is sponsored by [Maxon US](https://www.maxon.net/en-us/) and was
created for [Cineversity.com](https://www.cineversity.com/)'s
[CV-Toolbox](https://www.cineversity.com/vidplaytut/cv_toolbox).

- Programming and Design: [Niklas Rosenstein](https://www.niklasrosenstein.com/)
- Initial Concept and Design: [Donovan Keith](https://www.donovankeith.com)

---

<p align="center">Copyright &copy 2018 [Niklas Rosenstein](https://www.niklasrosenstein.com/)</p>
