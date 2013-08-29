#!/usr/bin/python
"""Copy published precise PPA packages to lucid.

We build a few packages containing scripts (architecture: all), upload them to
the PPA targeting the current Ubuntu LTS (precise).  But we also want them to
be available for the previous LTS (lucid).  This script automates the copying
process I used to do manually over the web.
"""

import optparse
from collections import defaultdict
from launchpadlib.launchpad import Launchpad


PPA_OWNER = 'pov'
PPA_NAME = 'ppa'
PACKAGE_WHITELIST = ['pov-admin-tools', 'pov-check-health', 'pov-server-page', 'pov-simple-backup']

SOURCE_SERIES = 'precise'
TARGET_SERIES = 'lucid'


def main():
    parser = optparse.OptionParser('usage: %prog [options]',
        description="copy ppa:%s/%s packages from %s to %s"
                    % (PPA_OWNER, PPA_NAME, SOURCE_SERIES, TARGET_SERIES))
    parser.add_option('-v', '--verbose', action='store_true', default=True)
    parser.add_option('-q', '--quiet', action='store_false', dest='verbose')
    opts, args = parser.parse_args()

    lp = Launchpad.login_with('pov-ppa-copy-packages', 'production')

    owner = lp.people[PPA_OWNER]
    ppa = owner.getPPAByName(name=PPA_NAME)

    source_series = ppa.distribution.getSeries(name_or_version=SOURCE_SERIES)
    target_series = ppa.distribution.getSeries(name_or_version=TARGET_SERIES)

    target_packages = defaultdict(set)
    target_package_notices = defaultdict(lambda: defaultdict(list))
    for source in ppa.getPublishedSources(distro_series=target_series):
        name = source.source_package_name
        if name not in PACKAGE_WHITELIST:
            continue
        if source.status in ('Superseded', 'Deleted', 'Obsolete'):
            continue
        version = source.source_package_version
        target_packages[name].add(version)
        if source.status != ('Published'):
            target_package_notices[name][version].append(
                "  but it is %s in %s" % (source.status.lower(), TARGET_SERIES))
        else:
            builds = source.getBuilds()
            if builds and builds[0].buildstate != u'Successfully built':
                target_package_notices[name][version].append(
                    "  but it isn't built yet for %s (state: %s) - %s" % (
                        TARGET_SERIES, builds[0].buildstate, builds[0].web_link))

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
            print "%s %s is %s in %s" % (name, version, source.status.lower(), SOURCE_SERIES)
            continue
        if version not in target_packages[name]:
            # Technically we should only check the most recently published version,
            # since that's the only thing that syncSouces() will sync.  I think
            # all the other versions will be marked as Superseded/Obsolete, so
            # we're fine.
            print "%s %s missing from %s" % (name, version, TARGET_SERIES)
            builds = source.getBuilds()
            if builds and builds[0].buildstate != u'Successfully built':
                print "  but it isn't built yet (state: %s) - %s" % (
                    builds[0].buildstate, builds[0].web_link)
            else:
                sources_to_copy.add(name)
                pocket = source.pocket
        elif opts.verbose:
            print "%s %s" % (name, version)
            for notice in target_package_notices[name][version]:
                print notice

    if sources_to_copy:
        if opts.verbose:
            print
        print "Copying %s to %s" % (", ".join(sorted(sources_to_copy)), TARGET_SERIES)
        ppa.syncSources(from_archive=ppa, to_series=TARGET_SERIES, to_pocket=pocket,
                        include_binaries=True, source_names=sorted(sources_to_copy))


if __name__ == '__main__':
    main()