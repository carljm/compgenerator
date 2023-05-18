Comprehension fuzzer
====================

Generate random code samples including list comprehensions and try running
them on a Python build.

To use, create a Python 3.11 venv and `pip install -r frozen.txt`.

Then start the evalserver with your built Python:

    /home/carljm/cpython-builds/dbg/python evalserver.py

Then run `pytest`.

Two other useful options: `--hypothesis-show-statistics` and
`--logfile="/some/path"`; the latter will dump all valid generated samples to
the log file.

Current approach is to generate a bunch of random code samples and filter down
to the ones containing list comprehensions, then aim for samples that maximize
number of listcomps and lambdas. The problem is that too many samples are
generated without listcomps and then rejected. We probably need a more
constrained format for generating the samples initially, but without
over-constraining and possibly missing counter-examples.

Note that this will `exec()` the generated code samples on multiple
Python binaries. As the code samples cannot contain imports or calls
to builtin functions, this is probably safe, but definitely do not
run the evalserver on a publicly accessible port.
