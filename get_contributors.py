#!/usr/bin/env python
import hashlib
import json
import logging
import os
import requests
import time
import urllib
from os.path import dirname


# Quick & dirty env-based config
# See also: https://developer.github.com/v3/#rate-limiting
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', None)
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', None)
GITHUB_EMAIL_CACHE_AGE = int(os.getenv('GITHUB_EMAIL_CACHE_AGE',
                                       60 * 60 * 24 * 7))
GITHUB_REPOS_CACHE_AGE = int(os.getenv('GITHUB_REPOS_CACHE_AGE',
                                       60 * 60))

BADGES_BASE_URL = 'https://badges.mozilla.org/en-US/badges/badge/'
BADGES_VALET_USERNAME = os.getenv('BADGES_VALET_USERNAME', None)
BADGES_VALET_PASSWORD = os.getenv('BADGES_VALET_PASSWORD', None)

CACHE_PATH_TMPL = 'cache/%s/%s'

REPOS = [
    'airmozilla',
    'amo-validator',
    'app-validator',
    'badges.mozilla.org',
    'basket',
    'basket-client',
    'bedrock',
    'django-badger',
    'django-browserid',
    'elasticutils',
    'elmo',
    'firefox-flicks',
    'fireplace',
    'fjord',
    'funfactory',
    'high-fidelity',  # Mozilla's Podcasts Reference App
    'input.mozilla.org',
    'KitchenSink',
    'kitsune',
    'kuma',
    'mozillians',
    'nocturnal',
    'playdoh',
    'playdoh-docs',
    'remo',
    'scrumbugz',
    'SocialShare',
    'socorro',
    'solitude',
    'unicode-slugify',
    'webdev-bootcamp',
    'webdev-contributors',
    'zamboni',
]
GITHUB_BASE_URL = 'https://api.github.com/repos/mozilla'
COMMIT_LEVELS = [100, 50, 25, 10, 1]
COMMIT_BADGES = {
    1: 'webdev-1-pull-request-merged',
    10: 'webdev-10-pull-requests-merged',
    25: 'webdev-25-pull-requests-merged',
    50: 'webdev-50-pull-requests-merged',
    100: 'webdev-100-pull-requests-merged',
}
FORK_BADGE = 'webdev-fork-a-repo'
PULL_REQUEST_BADGE = 'webdev-submit-a-pull-request'


def main():
    contributors = {}

    # Figure out the number of contributions per contributor:
    for repo in REPOS:
        print 'Fetching contributors for %s' % repo

        repocontributors = github_api_get('%s/contributors' % repo, None,
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
                commits = github_api_get('%s/commits' % repo, dict(author=username),
                                  'email', GITHUB_EMAIL_CACHE_AGE)
                try:
                    first = commits[0]['commit']
                    contributor['email'] = first['author']['email']
                except:
                    pass

    # For now, just make all of them part of forked and pull request submitted.
    # They probably forked and PR'd to contribute.
    # TODO: Add users that havent commited yet but have forks and PRs.
    for user, contributor in contributors.items():
        contributor['forked'] = True
        contributor['pull_requests'] = True

    award_badges(contributors)

    #print_contributors_by_level(contributors)


def print_contributors(contributors):
    """Output contributors and their number of contributions."""
    for user, contributor in contributors.items():
        print '%s, %s, %s' % (
            user, contributor['contributions'], ' '.join(contributor['repos']))


def print_contributors_by_level(contributors):
    """Output contributors, based on their contribution levels."""
    contributors_by_level = {}

    # Group the contributors into levels by number of contributions:
    for user, contributor in contributors.items():
        contributions = contributor['contributions']
        for level in COMMIT_LEVELS:
            if contributions >= level:
                contributors_by_level.setdefault(level, []).append(contributor)
                break

    for level in COMMIT_LEVELS:
        if level in contributors_by_level:
            print '========== %s+ ==========' % level
            for contributor in contributors_by_level[level]:
                print '%s <%s>' % (contributor['username'], contributor['email'])


def github_api_url(url, params=None):
    """Append the GitHub client details, if available"""
    url = '%s/%s' % (GITHUB_BASE_URL, url)
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


def github_api_get(path, params=None, cache_name=False, cache_timeout=3600):
    """Cached HTTP GET to GitHub repos API"""
    url = github_api_url(path, params)

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


def award_badges(contributors):
    """Award badges to contributors based on their contributions."""

    if not BADGES_VALET_USERNAME or not BADGES_VALET_PASSWORD:
        print ('You must set BADGES_VALET_USERNAME and BADGES_VALET_PASSWORD'
               ' for awarding badges.')
        return

    badges_to_award = collect_badges_to_award(contributors)

    for badge, emails in badges_to_award.items():
        award_badge(badge, emails)
        # print 'Badge: %s' % badge
        # for email in emails:
        #     print '    %s' % email


def collect_badges_to_award(contributors):
    """Group all the badges with the emails they need to be awarded to."""
    badges_to_award = {}

    for user, contributor in contributors.items():
        if 'email' not in contributor:
            print 'No email found for %s' % contributor['username']
            continue

        email = contributor['email']

        if contributor['forked']:
            badges_to_award.setdefault(FORK_BADGE, []).append(email)

        if contributor['pull_requests']:
            badges_to_award.setdefault(
                PULL_REQUEST_BADGE, []).append(email)


        if 'contributions' not in contributor:
            continue

        for commits, badge in COMMIT_BADGES.items():
            if contributor['contributions'] >= commits:
                badges_to_award.setdefault(badge, []).append(email)

    return badges_to_award


def award_badge(badge_slug, contributor_emails):
    """Award a badge with the specified slug to the specified emails."""
    print 'Awarding the %s badge.' % badge_slug

    r = requests.post(
        '%s%s/awards' % (BADGES_BASE_URL, badge_slug),
        data=json.dumps({'emails': contributor_emails, 'description': ''}),
        headers={'content-type': 'application/json'},
        verify=False, # To workaround SSL cert issue.
        auth=(BADGES_VALET_USERNAME, BADGES_VALET_PASSWORD),)

    if r.status_code != 200:
        print 'Something went wrong awarding badge %s (Status=%s).' % (
            badge_slug, r.status_code)
        print r.content
        return

    response = json.loads(r.content)

    if 'successes' in response:
        successes = response['successes']
        print 'Badge awarded to: %s' % [k for k in successes.keys()]

    if 'errors' in response:
        errors = response['errors']
        already_awarded = [x for x in errors.keys()
                           if errors[x] == 'ALREADYAWARDED']
        print 'Badge had already been awarded to: %s' % (
            [k for k in already_awarded])
        print 'Error awarding badge to: %s' % (
            [k for k in errors if k not in already_awarded])


def file_age(fn):
    """Get the age of a file in seconds"""
    return time.time() - os.stat(fn).st_mtime


if __name__ == '__main__':
    main()
