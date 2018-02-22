"""
A simple script to test the behaviour of our refactoring suite.
"""

from c4d_prototype_converter import codeconv

script = '''
from __future__ import print_function, division
import c4d

def main():
  method_a(42, 55, "Hello, World",
           verbose=True, options={'spam': 'spasm'})
  method_b(
    42, 55,
    "Hello, World",
    verbose = True,
    options = {
      'spam': 'spasm'
    }
  )
  return c4d.BaseObject(c4d.Ocube)
'''

future_import, global_code, methods = codeconv.refactor_expression_script(
  script, 'ObjectData', indent='    ')

print(future_import)
print(global_code)
print(methods)
