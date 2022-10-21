#!/usr/bin/python3
"""Copy published PPA packages from one release pocket to another.

We build a few packages containing scripts (architecture: all).  We want them
to be available for all supported Ubuntu releases.  So we upload to the oldest
supported LTS and use this script to copy the built packages to all other
releases in the same PPA.
"""

import argparse
import functools
import logging
import sys
import time
import webbrowser
from collections import defaultdict

from launchpadlib.launchpad import Launchpad

try:
    # Suppress
    #   /usr/lib/python2.7/dist-packages/keyring/backends/Gnome.py:6:
    #   PyGIWarning: GnomeKeyring was imported without specifying a version
    #   first. Use gi.require_version('GnomeKeyring', '1.0') before import to
    #   ensure that the right version gets loaded.
    # produced by Launchpad.login_with() on Ubuntu 15.10 (+ gnome3-staging PPA)
    import gi
    gi.require_version('GnomeKeyring', '1.0')
except (ImportError, ValueError):
    pass


APP_NAME = 'ppa-copy-packages'
__author__ = 'Marius Gedminas <marius@pov.lt>'
__version__ = '1.9.4'
__url__ = 'https://github.com/mgedmin/ppa-copy-packages'


#
# Logging
#

log = logging.getLogger(APP_NAME)

STARTUP_TIME = LAST_LOG_TIME = time.time()
REQUESTS = LAST_REQUESTS = 0


class DebugFormatter(logging.Formatter):

    def format(self, record):
        global LAST_LOG_TIME, LAST_REQUESTS
        msg = super(DebugFormatter, self).format(record)
        if msg.startswith("  "):  # continuation of previous message
            return msg
        now = time.time()
        elapsed = now - STARTUP_TIME
        delta = now - LAST_LOG_TIME
        LAST_LOG_TIME = now
        delta_requests = REQUESTS - LAST_REQUESTS
        LAST_REQUESTS = REQUESTS
        return "\n%.3fs (%+.3fs) [%d/+%d] %s" % (elapsed, delta, REQUESTS,
                                                 delta_requests, msg)


def enable_http_debugging():
    import httplib2
    httplib2.debuglevel = 1


def install_request_counter():
    import httplib2
    orig = httplib2.Http.request

    @functools.wraps(orig)
    def wrapper(*args, **kw):
        global REQUESTS
        REQUESTS += 1
        return orig(*args, **kw)

    httplib2.Http.request = wrapper


def set_up_logging(level=logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    if level == logging.DEBUG:
        handler.setFormatter(DebugFormatter())
    log.addHandler(handler)
    log.setLevel(level)


#
# Caching decorators
#

class once(object):
    """A @property that is computed only once per instance.

    Also known as @reify in Pyramid and @Lazy in Zope.
    """

    def __init__(self, fn):
        self.fn = fn

    def __get__(self, obj, type=None):
        value = self.fn(obj)
        # Put the value in the instance __dict__.  Since the once
        # descriptor has no __set__ and is therefore not a data
        # descriptor, instance __dict__ will take precedence on
        # subsequent attribute accesses.
        setattr(obj, self.fn.__name__, value)
        return value


def cache(fn):
    """Trivial memoization decorator."""
    cache = fn.cache = {}

    @functools.wraps(fn)
    def inner(*args):
        # The way we use the cache is suboptimal for methods: it is
        # shared between all instances, but the instance is part of
        # the cache lookup key, negating any advantage of the sharing.
        # Luckily in this script there's only one instance.
        try:
            return cache[args]
        except KeyError:
            value = cache[args] = fn(*args)
            return value
        except TypeError:
            raise TypeError('%s argument types preclude caching: %s' %
                            (fn.__name__, repr(args)))
    return inner


#
# Launchpad API wrapper with heavy caching
#

class AnnotatedList(list):
    pass


class LaunchpadWrapper(object):
    application_name = APP_NAME

    def __init__(self, ppa_owner, ppa_name, launchpad_instance='production'):
        self.ppa_owner = ppa_owner
        self.ppa_name = ppa_name
        self.launchpad_instance = launchpad_instance
        self.queue = defaultdict(set)

    # Trivial caching wrappers for Launchpad API

    def clear_caches(self):
        log.debug("Clearing caches...")
        # self.get_series.cache can be kept
        self.get_published_sources.cache.clear()
        self.get_published_binaries.cache.clear()
        self.get_source_packages.cache.clear()
        self.get_usable_sources.cache.clear()

    @once
    def lp(self):
        log.debug("Logging in...")
        # cost: 2 HTTP requests
        return Launchpad.login_with(self.application_name,
                                    self.launchpad_instance)

    @once
    def owner(self):
        lp = self.lp                # ensure correct ordering of debug messages
        log.debug("Getting the owner...")
        # cost: 1 HTTP request
        return lp.people[self.ppa_owner]

    @once
    def ppa(self):
        owner = self.owner          # ensure correct ordering of debug messages
        log.debug("Getting the PPA...")
        # cost: 1 HTTP request
        return owner.getPPAByName(name=self.ppa_name)

    @cache
    def get_series(self, name):
        ppa = self.ppa              # ensure correct ordering of debug messages
        log.debug("Locating the series: %s...", name)
        # cost: 1 HTTP request
        return ppa.distribution.getSeries(name_or_version=name)

    @cache
    def get_arch_series(self, name, archtag):
        series = self.get_series(name)  # ensure correct ordering of messages
        log.debug("Locating the arch series: %s %s...", name, archtag)
        # cost: 1 HTTP request
        return series.getDistroArchSeries(archtag=archtag)

    @cache
    def get_published_sources(self, series_name):
        series = self.get_series(series_name)
        log.debug("Listing source packages for %s...", series_name)
        # cost: 1 HTTP request
        return self.ppa.getPublishedSources(distro_series=series)

    @cache
    def get_published_binaries(self, series_name, archtag):
        series = self.get_arch_series(series_name, archtag)
        log.debug("Listing binary packages for %s %s...", series_name, archtag)
        # cost: 1 HTTP request
        return self.ppa.getPublishedBinaries(distro_arch_series=series,
                                             status="Published")

    def get_builds_for_source(self, source):
        log.debug("Listing %s builds for %s %s...",
                  source.distro_series_link.rpartition('/')[-1],
                  source.source_package_name,
                  source.source_package_version)
        # cost: 1 HTTP request, plus another one for accessing the list
        return source.getBuilds()

    # Package availability: for a certain package name + version
    # - source package is available but not published
    # - source package is published, but binary package is not built
    # - binary package is built but not published
    # - binary package is published
    # And then there are also superseded, deleted and obsolete packages.
    # Figuring out binary package status costs extra HTTP requests.

    # We're dealing with arch: any packages only, so there's only one
    # relevant binary package.  It should be trivial to extend this to
    # arch: all.

    # A package can be copied when it has a published binary package
    # in the source series.

    # A package should be copied when it can be copied, and it doesn't
    # exist in the target series.

    @cache
    def get_source_packages(self, series_name, package_names=None):
        """Return {package_name: {version: 'Status', ...}, ...}"""
        res = defaultdict(dict)
        for source in self.get_published_sources(series_name):
            name = source.source_package_name
            if package_names is not None and name not in package_names:
                continue
            version = source.source_package_version
            res[name][version] = source
        return res

    def get_source_for(self, name, version, series_name):
        sources = self.get_source_packages(series_name)
        return sources.get(name, {}).get(version)

    def is_missing(self, name, version, series_name):
        return self.get_source_for(name, version, series_name) is None

    def get_builds_for(self, name, version, series_name):
        source = self.get_source_for(name, version, series_name)
        if not source:
            return None
        return self.get_builds_for_source(source)

    def has_published_binaries(self, name, version, series_name,
                               architectures):
        for archtag in architectures:
            binaries = self.get_published_binaries(series_name, archtag)
            if not any(b.binary_package_name == name
                       and b.binary_package_version == version
                       for b in binaries):
                log.debug("%s %s has no published binary for %s %s",
                          name, version, series_name, archtag)
                return False
        return True

    @cache
    def get_usable_sources(self, package_names, series_name):
        res = AnnotatedList()
        res.pending = []
        for source in self.get_published_sources(series_name):
            name = source.source_package_name
            if name not in package_names:
                continue
            version = source.source_package_version
            if source.status in ('Superseded', 'Deleted', 'Obsolete'):
                log.debug("%s %s is %s in %s", name, version,
                          source.status.lower(), series_name)
                continue
            if source.status != ('Published'):
                if source.status == 'Pending':
                    res.pending.append((name, version, 'pending'))
                log.warning("%s %s is %s in %s", name, version,
                            source.status.lower(), series_name)
                continue
            res.append((name, version))
        return res

    def queue_copy(self, name, source_series, target_series, pocket):
        self.queue[source_series, target_series, pocket].add(name)

    def perform_queued_copies(self, dry_run=False):
        first = True
        any_pending = set()
        for (src_series, target_series, pocket), names in self.queue.items():
            if not names:
                continue
            if first:
                log.info("")
                first = False
            if dry_run:
                log.warning("Would copy %s to %s", ', '.join(sorted(names)),
                            target_series)
            else:
                # Another thing: copying too many packages one by one
                # makes the method fail with a 503 error.
                for name in sorted(names):
                    self.sync_sources(target_series, pocket, [name])
                    any_pending.add((name, '', 'just copied'))
        self.queue.clear()
        return any_pending

    def sync_sources(self, target_series, pocket, names):
        log.warning("Copying %s to %s", ', '.join(sorted(names)),
                    target_series)
        # DEPRECATED: syncSource and syncSources are deprecated, and
        # will be removed entirely in the future. Use the asynchronous
        # copyPackage method instead, and poll getPublishedSources if
        # you need to await completion.
        # BTW the 'copyPackage()' method is not mentioned anywhere in
        # the API docs at https://launchpad.net/+apidoc/1.0.html so...
        self.ppa.syncSources(from_archive=self.ppa,
                             to_series=target_series,
                             to_pocket=pocket,
                             include_binaries=True,
                             source_names=sorted(names))


def get_ppa_url(owner, name):
    return 'https://launchpad.net/~{owner}/+archive/{name}/+packages'.format(
        owner=owner, name=name)


def process_packages(lp, dry_run, packages, source_series, target_series,
                     architectures, pocket):
    sources = lp.get_usable_sources(tuple(packages), source_series)
    any_pending = set(sources.pending)
    for (name, version) in sources:
        mentioned = False
        notices = []
        for target_series_name in target_series:
            source = lp.get_source_for(name, version, target_series_name)
            if source is None:
                mentioned = True
                log.info("%s %s missing from %s", name, version,
                         target_series_name)
                if lp.has_published_binaries(name, version,
                                             source_series,
                                             architectures):
                    lp.queue_copy(name, source_series,
                                  target_series_name, pocket)
                else:
                    builds = lp.get_builds_for(name, version, source_series)
                    if builds:
                        if builds[0].buildstate == 'Needs building':
                            any_pending.add((name, version, 'needs building'))
                        elif builds[0].buildstate == 'Currently building':
                            any_pending.add((name, version, 'building'))
                        elif builds[0].buildstate == 'Uploading build':
                            any_pending.add((name, version, 'uploading'))
                        elif builds[0].buildstate == 'Successfully built':
                            any_pending.add((name, version, 'publishing'))
                        log.info("  but binaries aren't published yet"
                                 " (state: %s) - %s",
                                 builds[0].buildstate, builds[0].web_link)
            elif source.status != 'Published':
                any_pending.add((name, version, '%s in %s' %
                                 (source.status.lower(), target_series_name)))
                notices.append("  but it is %s in %s" %
                               (source.status.lower(), target_series_name))
            elif not lp.has_published_binaries(name, version,
                                               target_series_name,
                                               architectures):
                builds = lp.get_builds_for(name, version, target_series_name)
                if builds:
                    if builds[0].buildstate == 'Successfully built':
                        any_pending.add((name, version, 'publishing'))
                    notices.append("  but binaries aren't published yet for %s"
                                   " (state: %s) - %s" %
                                   (target_series_name, builds[0].buildstate,
                                    builds[0].web_link))
        if not mentioned or notices:
            log.info("%s %s", name, version)
            for notice in notices:
                log.info(notice)

    any_pending.update(lp.perform_queued_copies(dry_run=dry_run))
    return any_pending


def _main():
    parser = argparse.ArgumentParser(
        description=(
            "copy Ubuntu PPA packages from one release pocket to another"
        ),
    )
    parser.add_argument(
        '--version', action='version',
        version='%(prog)s version ' + __version__)
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help="More verbose output (can be stacked)")
    parser.add_argument(
        '-q', '--quiet', action='count', default=0,
        help="Less verbose output")
    parser.add_argument(
        '-n', '--dry-run', action='store_true',
        help="Don't make any changes")
    parser.add_argument(
        '-w', '--wait', action='store_true',
        help="Wait for pending packages to be published")
    parser.add_argument(
        '-b', '--browse', action='store_true',
        help="Open the PPA page in a browser, don't do anything else.")
    parser.add_argument(
        '--debug', action='store_true',
        help="Very verbose logging, for debugging this script")

    group = parser.add_argument_group('PPA selection')
    group.add_argument(
        '-O', '--owner', required=True,
        help="owner of the PPA")
    group.add_argument(
        '-N', '--name', default='ppa',
        help="name of the PPA (default: %(default)s)")
    group.add_argument(
        '-p', '--packages', metavar='NAME', nargs='+', required=True,
        help="names of packages to copy")
    group.add_argument(
        '-s', '--source-series', metavar='SERIES', required=True,
        help="source series (e.g. xenial)")
    group.add_argument(
        '-t', '--target-series', metavar='SERIES', nargs='+', required=True,
        help="target series (e.g. bionic)")
    group.add_argument(
        '--architectures', metavar='ARCH', nargs='+',
        default=['i386', 'amd64'],
        help=(
            "architectures to check for published binaries"
            " (default is %(default)s)"
        ))
    group.add_argument(
        '--pocket', default='Release',
        help=(
            "pocket name (you probably don't want to change this;"
            " default is %(default)s)"
        ))
    group.add_argument(
        '--launchpad-instance', metavar='INSTANCE', default='production',
        help="Launchpad instance (default: %(default)s)")

    args = parser.parse_args()
    args.verbose -= args.quiet

    if args.browse:
        webbrowser.open(get_ppa_url(args.owner, args.name))
        sys.exit(0)

    if args.debug:
        enable_http_debugging()
        install_request_counter()
        set_up_logging(logging.DEBUG)
    elif args.verbose > 1:
        install_request_counter()
        set_up_logging(logging.DEBUG)
    elif args.verbose:
        set_up_logging(logging.INFO)
    else:
        set_up_logging(logging.WARNING)

    lp = LaunchpadWrapper(
        ppa_owner=args.owner,
        ppa_name=args.name,
        launchpad_instance=args.launchpad_instance
    )

    wait_time = 60

    while True:
        any_pending = process_packages(lp, dry_run=args.dry_run,
                                       packages=args.packages,
                                       source_series=args.source_series,
                                       target_series=args.target_series,
                                       architectures=args.architectures,
                                       pocket=args.pocket)
        if args.wait and any_pending and not args.dry_run:
            reasons = dict((name, reason)
                           for name, version, reason in sorted(any_pending))
            log.warning("\nWaiting for %s: sleeping for %d seconds\n",
                        ", ".join('%s (%s)' % (name, reason)
                                  for name, reason in sorted(reasons.items())),
                        wait_time)
            time.sleep(wait_time)
            lp.clear_caches()
        else:
            break

    log.debug("All done")


def main():
    try:
        _main()
    except KeyboardInterrupt:
        sys.exit(2)


if __name__ == '__main__':
    main()
