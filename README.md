Comprehension fuzzer
====================

Generate random code samples including list comprehensions and try compiling
them against a Python build.

To use, create a Python 3.11 venv and `pip install -r frozen.txt`.

Then run `pytest`.

By default this will generate samples valid on Python 3.11 and then test them
on 3.11; not very useful. Instead, point it to a 3.12 build:

    pytest --python="/home/carljm/cpython-builds/dbg/python"
    
Two other useful options: `--hypothesis-show-statistics` and
`--logfile="/some/path"`; the latter will dump all valid generated samples to
the log file.

Current approach is to generate a bunch of random code samples and filter down
to the ones containing list comprehensions, then aim for samples that maximize
number of listcomps and lambdas. The problem is that too many samples are
generated without listcomps and then rejected. We probably need a more
constrained format for generating the samples initially, but without
over-constraining and possibly missing counter-examples.

It would be ideal to run samples and validate output, not just test compiling
them, but this will definitely require much more constrained samples; currently
most samples are not runnable at all, and there's no structured output to
validate.
