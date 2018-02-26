# localimport-v1.7.1-blob-mcw99
import base64 as b, types as t, zlib as z; m=t.ModuleType('localimport');
m.__file__ = __file__; blob=b'\
eJydGcuO4zby7q8QMAdJ01r1dHIIYKwGmwQJECTIIVjkEMMQZInyMC1LAklP7G7Mv29V8SlLmvFsH7pJ1oP1rqK6LKuz+jCIs\
izi3/lzV8noj0GyXirG++jfwq17Av7neKp4l9fD6X28KcuPTEg+9Ej8lH+XP8UbfhoHoaJ6GK92feyGg10P0q7G5+NZ8c5u5d\
VBlKhqdqjqZ3vwwseWd2zDW0TL7aW8b4fdu31RfLPdRA1rI67YSSaXFLaRYOos+uiS68PUYYg1LGExWSfZOseOS5U4tnfwJZ6\
EJMtuqKsuQWX66sSysVIfkB/S2MNikDme59VB4l+HDVe1g4jwrMR9BP6xDPBOB5hxcBBgEXESRJ4PE+aZx0FeVoH/ijPb2M3P\
FRjGamIZ4C8gFqwnLZS4av07BDhJzH6CvYnYpWajiv6sujP7SYhBBKajyyJ3t2WIHOuzaLiIwBb9oCwkl6oSSv7D4Ra6FXG03\
dnHqivHUFkJbkEw3AfmQC5WUC4RydvcS7SJkHc0jKz3jGIRp5Ax7Yh46B3eN+ySdbwn97D+fGKiUsBw1HaF6xAYShvrKI81Ao\
HLti/i13ef3rw+fYpz4HuqlL+U7nh4SgndGBx+2IXVCSTmiAogl8ywymIExakmMEb/oZLsJ1pCKhkOLvHyUfBelYCaEJHJCJQ\
f7y5IhRbWSfwm1mwxrBD2/t0WoYSy29LR3ulVGN0FHxNHNjU/xCwJb6yhySz474H3id2AA9Ec3lekb7qZUfVgP4o+DzduiKq+\
0QsUAhyG5QVRzeV2m/NeMqGSd+YKiqqLYn1T6rCGqLbhgjAoWKWJpBcHiHCRC619/Eh2M9Ft0/klxxVVGICOk2Qm3d8SDzl2X\
CVxTi59ISzgpzHmCLznqhyvRVyWtCzjB+AJ4ks2PsTjNXYo9SpO7ZGGVaQBkE6DNklBSoBdgqp1a2De2soOfi/NkkqEdr4LbX\
Y8FhbzLz7+bNEo/Qijahq6NQksD1QZGechfrQS56BuCuJ8Ga2+E2+wedVOCh75wlQ7+PViqy9pbaSl6CMyG37Weib87DavRqg\
6TUK4OiEpcxNrlB+q5i+9zOzRb5U4MmMsk0tjJSVUVJ/NaxI7YUFWn5mQb9o5KPa61M4VNyV1fo8JqBQNfS9y/VXYQ5ouGv0r\
bG5MrhN1NysplxSj+xIy2m/qDi1NvV7X9mQ4/M1qapAg1bfPxcIY8774FqBYHfpjqa4jk0UCuywF2YmI/JYcoG5rpMzMHjYYE\
8m6Ngs6bAkeK34foBE0QwnhKwts57iBvHRrGP+GButux+gsNamJ5vF8yDqtwFKDspdHpmiXPKV5W+KEB/3ahAzUB3QL1Ac0C6\
HZAHRi3Rbx2dCDVDvPaU+ORA0Jr9jt7SgDpVlVfW0qAmFMrJj6UN9p90TLc5Ttz/N+dDMbrVgHqnnFYWbx40wSw3BSKf6R6Yg\
7nBUQBnSmes0nNxPJFi+YzjaL+C4ep4jOXmE0l2F6m8jQCnh03dwS9GuOv+YpVur5520O5HHqvXNiqiq9i/TZ0Jw7iOfXT/bE\
xKD+Yw95X9ZDr+DuQo+aHjkM0unW5gBYigmTBOQm2z38c6MUTA5nUTMK1B4KWq0KfKjkDWMjLpIJVk46QjzWDDSqn6sjRBOSN\
gwyXDAPLqZ0Mzg57fMohY7cJVIzsf1Cirg52SqACb4slIEQY8gRxYrXWBPFW/03i2dU8XZ2lAEVelTG29dPWYzLeGsb+W67z2\
LndH3utgQ0jrLU+tmXB+NTvF04zChW/CWFC05zHl5STEPvYQLfRNEC/yJYm4rwzK4ZhCrWA/1sC4PXjyTenjuv234H1HuqjYY\
gH4cxgcOgX0e/sqv2H7bijRkwDb5mABtd2II00bX3tmQ5e+jcRXjbI+CepAWukLT24eDeR/200FjzPxShzuSy/arNvEbuxUMI\
MsJ4NI1AsJZfCiDOBVQ5xfERQvMqNEJbYj9UslJKhBxzaDuJJk4zaA4kbWlfTpAC3cyi+vkSsAPgnDTUzwa7cSkVCCoOQJlbQ\
l24w5NiIcgmJJneoHE1/W3R04/t0PlBndu6eh4cJsEbAmGuGF78QPAWLgta+s2l+rFPfeuPc6/4yXYuAycaqq2soW5FUw1pJH\
WFX5vu8cJwzpqHkHnveoY3M9eU9STcb3gHPO5iirXByuvqhItWAkpnLZoY6XBBE1/59m42mOFOr7htlFZAPEABbbcM457iL13\
MOfPdaZJzgIU9axhdI/WflyCFwjww81WGyWmHApTd4pP2cGP4Qj6ceacghvSdulGEE55ObPcIzZ7CtNYoZmBGkY1RlgSkLNYE\
+0Vhgy8TgdImkfA2dxhBUE90mn+NC4ImDevCpECvVPjw+Dw2+MlnuU981okrJK71mImQzIQ29u/83b++2QeN5hf87mJbjaexs\
4JzQ+nMEe5tZoT+MZ4Ny2tAsjfW0p7TgOxWwqc9ahwawCb3sgVcIQ567011D6qv7uNrnXY2Sdw2s+WRYp7lK9PEhOfCiLO/Yy\
K9a0K00TGb2/ZzFgvza153rBL649uXkRci2QyQFMcLg6k198o8Tx3acTPtaqaLfcmSFP7h9QX9kwmBLqQ38erh+83Xdu8b7ig\
5pGg9wDPePzpML7bM/qm6Z2fNxLUwT05NnLTVQoadOnjaauDq43an5wXDbvpJAugoMuxH7EieD6WZvzT4AbIzaDv0SFuvUAvj\
HSAWhlek6cLP2/4+U1NvCxlcryfUm3qxhYIx+WT9haIWneaD9P9V6u6qdcGHd4zqz9e91AzaWo/vAZcfzsr/z8N+nbu7wa9Nu\
p97m5BFMO7CAdJFLt7bDVXDRKb/ySAhiN0E4yI99XOoZaET4k30o2BwbxMdrtF4PfGet5yJKPmg1Ci3j49HCIbzAf9z+AjjuB\
ra9tGjpZvN/wAj+NGJ'
exec(z.decompress(b.b64decode(blob)), vars(m)); _localimport=m;localimport=getattr(m,"localimport")
del blob, b, t, z, m;

import os

with localimport(['.', 'lib']) as _importer:
  from c4d_prototype_converter import main, res
  res.__res__ = __res__
  res.plugin_dir = os.path.dirname(__file__)
  PluginMessage = main.PluginMessage
