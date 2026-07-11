pydateinfer
===========

Python library to infer date format from examples.  This is an actively
 maintained fork of the original [dateinfer](https://github.com/jeffreystarr/dateinfer)
 library by Jeffery Starr.  It maintains python 2/3 compatibility and is
 released on PyPI as [pydateinfer](https://pypi.org/project/pydateinfer/).  Pull
 requests and issues welcome.

Note on naming: the package is **distributed** as `pydateinfer` but is
 **imported** as `dateinfer` (`import dateinfer`). If you installed a package
 named `hidateinfer`, that is a separate third-party fork and not this project —
 install `pydateinfer` to get the `dateinfer` import used throughout these docs.

Table of Contents
-----------------

* [Problem Statement](#problem-statement)
* [Installation](#installation)
* [Usage](#usage)
* [Comparison with pandas](#pandas)

<a name="problem-statement"></a>Problem Statement
-------------------------------------------------

Imagine that you are given a large collection of documents and, as part of the extraction process, extract date
 information and store it in a normalized format. If the documents follow a single schema, the ideal approach
 is to craft a date parsing string for the schema. However, if the documents follow different schemas or if the
 contents are noisy (e.g. date fields were hand-populated), the development can become onerous.

This library makes a "best guess" on the proper date parsing string (`datetime.strptime`) based on examples in
the file.

<a name="installation"></a>Installation
---------------------------------------

Install from PyPI:

````
$ pip install pydateinfer
````

Then import it as `dateinfer`:

````Python
import dateinfer
````

<a name="usage"></a>Usage
-------------------------

````Python
>>> import dateinfer
>>> dateinfer.infer(['Mon Jan 13 09:52:52 MST 2014', 'Tue Jan 21 15:30:00 EST 2014'])
'%a %b %d %H:%M:%S %Z %Y'
>>>
````

Give `dateinfer.infer` a list of example date strings. `infer` returns a `datetime.strftime`/`strptime`-compliant
date format string for its "best guess" of a format string that will correctly parse the majority of the examples.

<a name="pandas"></a>Comparison with pandas
------------------------------------------

pandas ships its own format guesser,
[`pandas.tseries.api.guess_datetime_format`](https://pandas.pydata.org/docs/reference/api/pandas.tseries.api.guess_datetime_format.html),
which is the right tool if pandas is already a dependency:

````Python
>>> from pandas.tseries.api import guess_datetime_format
>>> guess_datetime_format('09/13/2023')
'%m/%d/%Y'
````

The two differ in a couple of ways worth knowing:

* **Single string vs. a set of examples.** pandas guesses the format of one
  string at a time. `dateinfer.infer` takes a *list* of examples and picks the
  single format that best parses the majority of them — useful for noisy or
  mixed-schema data where no one string is authoritative.
* **No hard dependency on pandas.** `dateinfer` depends only on `pytz`, so it is
  a lighter option when you don't already have pandas installed.

If you are only inferring the format of individual strings and already use
pandas, prefer the built-in.


