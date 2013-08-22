#!/usr/bin/python
"""Copy published precise PPA packages to lucid.

We build a few packages containing scripts (architecture: all), upload them to the PPA targeting the current Ubuntu LTS (precise).  But we also want them to be available for the previous LTS (lucid).  This script automates the copying process
I used to do manually over the web.
"""

from collections import defaultdict
from launchpadlib.launchpad import Launchpad

PPA_OWNER = 'pov'
PPA_NAME = 'ppa'
PACKAGE_WHITELIST = ['pov-admin-tools', 'pov-check-health', 'pov-server-page']

SOURCE_SERIES = 'precise'
TARGET_SERIES = 'lucid'


lp = Launchpad.login_with('pov-ppa-copy-packages', 'production')

owner = lp.people[PPA_OWNER]
ppa = owner.getPPAByName(name=PPA_NAME)

source_series = ppa.distribution.getSeries(name_or_version=SOURCE_SERIES)
target_series = ppa.distribution.getSeries(name_or_version=TARGET_SERIES)

target_packages = defaultdict(set)
for source in ppa.getPublishedSources(distro_series=target_series):
    name = source.source_package_name
    if name not in PACKAGE_WHITELIST:
        continue
    target_packages[name].add(source.source_package_version)

sources_to_copy = set()
for source in ppa.getPublishedSources(distro_series=source_series):
    name = source.source_package_name
    if name not in PACKAGE_WHITELIST:
        continue
    if name in sources_to_copy:
        # we already know we're going to copy this
        continue
    if source.status in ('Superseded', 'Deleted', 'Obsolete'):
        continue
    version = source.source_package_version
    if source.status != ('Published'):
        print "%s %s %s is %s" % (SOURCE_SERIES, name, version, source.status.lower())
        continue
    if version not in target_packages[name]:
        # Technically we should only check the most recently published version,
        # since that's the only thing that syncSouces() will sync.  I think
        # all the other versions will be marked as Superseded/Obsolete, so
        # we're fine.
        print "%s doesn't have %s %s" % (TARGET_SERIES, name, version)
        sources_to_copy.add(name)
        pocket = source.pocket

if sources_to_copy:
    print "Copying %s to %s" % (", ".join(sorted(sources_to_copy)), TARGET_SERIES)
    ppa.syncSources(from_archive=ppa, to_series=TARGET_SERIES, to_pocket=pocket,
                    include_binaries=True, source_names=sorted(sources_to_copy))
