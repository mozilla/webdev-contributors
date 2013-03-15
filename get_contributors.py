#!/usr/bin/env python
import os
import time
from os.path import dirname
import hashlib
import urllib
import requests
import logging
import json


# Quick & dirty env-based config
# See also: https://developer.github.com/v3/#rate-limiting
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', None)
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', None)
GITHUB_EMAIL_CACHE_AGE = int(os.getenv('GITHUB_EMAIL_CACHE_AGE',
                                       60 * 60 * 24 * 7))
GITHUB_REPOS_CACHE_AGE = int(os.getenv('GITHUB_REPOS_CACHE_AGE',
                                       60 * 60))

CACHE_PATH_TMPL = 'cache/%s/%s'

repos = [
    'amo-validator',
    'app-validator',
    'bedrock',
    'django-browserid',
    'elasticutils',
    'elmo',
    'firefox-flicks',
    'fireplace',
    'fjord',
    'funfactory',
    'high-fidelity',  # Mozilla's Podcasts Reference App
    'input.mozilla.org',
    'kitsune',
    'kuma',
    'mozillians',
    'nocturnal',
    'playdoh',
    'playdoh-docs',
    'remo',
    'socorro',
    'solitude',
    'webdev-bootcamp',
    'zamboni',
    'airmozilla',
    'socorro',
    'socorro-crashstats',
    'unicode-slugify',
    'webdev-contributors',
]
base_url = 'https://api.github.com/repos/mozilla'
commit_levels = [100, 50, 25, 10, 1]
contributors = {}
contributors_by_level = {}


def main():
    # Figure out the number of contributions per contributor:
    for repo in repos:
        print 'Fetching contributors for %s' % repo

        repocontributors = api_get('%s/contributors' % repo, None,
                                   'repocontributors', GITHUB_REPOS_CACHE_AGE)
        for repocontributor in repocontributors:
            username = repocontributor['login']
            contributions = repocontributor['contributions']
            contributor = contributors.setdefault(username, {
                'username': username, 'email': None
            })
            contributor['contributions'] = (
                contributor.get('contributions', 0) + contributions)
            contributor.setdefault('repos', []).append(repo)
            if not contributor['email']:
                print 'Fetching email for %s' % (username,)
                commits = api_get('%s/commits' % repo, dict(author=username),
                                  'email', GITHUB_EMAIL_CACHE_AGE)
                try:
                    first = commits[0]['commit']
                    contributor['email'] = first['author']['email']
                except:
                    pass

    # Group the contributors into levels by number of contributions:
    for user, contributor in contributors.items():
        contributions = contributor['contributions']
        for level in commit_levels:
            if contributions >= level:
                contributors_by_level.setdefault(level, []).append(contributor)
                break

    print_contributors_by_level()


def print_contributors():
    """Output contributors and their number of contributions."""
    for user, contributor in contributors.items():
        print '%s, %s, %s' % (
            user, contributor['contributions'], ' '.join(contributor['repos']))


def print_contributors_by_level():
    """Output contributors, based on their contribution levels."""
    for level in commit_levels:
        if level in contributors_by_level:
            print '========== %s+ ==========' % level
            for contributor in contributors_by_level[level]:
                print '%s <%s>' % (contributor['username'], contributor['email'])


def api_url(url, params=None):
    """Append the GitHub client details, if available"""
    url = '%s/%s' % (base_url, url)
    if not params:
        params = {}
    if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
        params.update(dict(
            client_id = GITHUB_CLIENT_ID,
            client_secret = GITHUB_CLIENT_SECRET
        ))
    if params:
        url = '%s?%s' % (url, urllib.urlencode(params))
    return url


def api_get(path, params=None, cache_name=False, cache_timeout=3600):
    """Cached HTTP GET to GitHub repos API"""
    url = api_url(path, params)

    # If no cache name, then cache is disabled.
    if not cache_name:
        return requests.get(url).json()

    # Build a cache path based on MD5 of URL
    path_hash = hashlib.md5(url).hexdigest()
    cache_path = CACHE_PATH_TMPL % (cache_name, path_hash)

    # Create the cache path, if necessary
    cache_dir = dirname(cache_path)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    # Attempt to load up data from cache
    data = None
    if os.path.exists(cache_path) and file_age(cache_path) < cache_timeout:
        try:
            data = json.load(open(cache_path, 'r'))
        except ValueError:
            pass

    # If data was missing or stale from cache, finally perform GET
    if not data:
        data = requests.get(url).json()
        json.dump(data, open(cache_path, 'w'))

    return data


def file_age(fn):
    """Get the age of a file in seconds"""
    return time.time() - os.stat(fn).st_mtime


if __name__ == '__main__':
    main()
