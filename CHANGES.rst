Changelog
==========

1.9.4 (2022-10-21)
------------------

- Copy packages one by one to avoid Launchpad timeouts.
- Do not copy the same packages more than once when using --wait.
- Fix TypeError: '<' not supported between instances of 'str' and 'NoneType'
  when using --wait.


1.9.3 (2020-10-31)
------------------

- Handle 'needs building' state when using --wait.


1.9.2 (2020-07-02)
------------------

- Fix ValueError: Namespace GnomeKeyring not available (`GH #3
  <https://github.com/mgedmin/ppa-copy-packages/pull/3>`_).


1.9.1 (2019-09-06)
------------------

- Fix TypeError: unhashable type: 'Entry'.


1.9 (2019-09-05)
----------------

- First release to PyPI.
- Unified three older scripts I had lying around with hardcoded configuration.
- Replaced hardcoded configuration with command-line arguments.
