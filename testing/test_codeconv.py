"""
A simple script to test the behaviour of our refactoring suite.
"""

from __future__ import print_function
from c4d_prototype_converter import codeconv

script = '''
# Copyright text here
"""
Name-US: Test Thing
Description-US: A description.
"""

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

results = codeconv.refactor_expression_script(
  script, 'ObjectData', indent='    ')

for k, v in results.iteritems():
  print(k)
  print('=' * len(k))
  print(v)
  print()
