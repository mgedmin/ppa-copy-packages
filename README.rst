ppa-copy-packages
=================

Copy published PPA packages from one release pocket to another.

We build a few Debian packages containing various helpful scripts (i.e. the
packages have Architecture: all and do not need to be recompiled when system
library versions change).  We want them to be available for all supported
Ubuntu releases.  So we upload a version built for the oldest supported LTS
release to our PPA and use this script to copy the built packages to all other
releases in the same PPA::

  ppa-copy-packages -O pov -s xenial -t bionic disco -p pov-admin-tools ...

I do the same thing with gtimelog, which is a pure Python program and also
doesn't need to be recompiled::

  ppa-copy-packages -O gtimelog -s xenial -t bionic disco -p gtimelog

And sometimes, when I'm feeling brave, I try this trick with C programs such as
pwsafe::

  ppa-copy-packages -O mg -s xenial -t bionic disco -p pwsafe

Authentication is taken care of by launchpadlib_, which opens a browser window
on first run and asks you to log in and authorize its access token (which is
stored in the system keyring for your convenience).


.. _launchpadlib: https://pypi.org/project/launchpadlib/


Synopsis
--------

::

  $ ppa-copy-packages -h
  usage: ppa-copy-packages [-h] [--version] [-v] [-q] [-n] [-w] [-b]
                           [--debug] -O OWNER [-N NAME] -p NAME [NAME ...]
                           -s SERIES -t SERIES [SERIES ...]
                           [--architectures ARCH [ARCH ...]]
                           [--pocket POCKET] [--launchpad-instance INSTANCE]

  copy Ubuntu PPA packages from one release pocket to another

  optional arguments:
    -h, --help            show this help message and exit
    --version             show program's version number and exit
    -v, --verbose         More verbose output (can be stacked)
    -q, --quiet           Less verbose output
    -n, --dry-run         Don't make any changes
    -w, --wait            Wait for pending packages to be published
    -b, --browse          Open the PPA page in a browser, don't do anything
                          else.
    --debug               Very verbose logging, for debugging this script

  PPA selection:
    -O OWNER, --owner OWNER
                          owner of the PPA
    -N NAME, --name NAME  name of the PPA (default: ppa)
    -p NAME [NAME ...], --packages NAME [NAME ...]
                          names of packages to copy
    -s SERIES, --source-series SERIES
                          source series (e.g. xenial)
    -t SERIES [SERIES ...], --target-series SERIES [SERIES ...]
                          target series (e.g. bionic)
    --architectures ARCH [ARCH ...]
                          architectures to check for published binaries (default
                          is ['i386', 'amd64'])
    --pocket POCKET       pocket name (you probably don't want to change this;
                          default is Release)
    --launchpad-instance INSTANCE
                          Launchpad instance (default: production)
