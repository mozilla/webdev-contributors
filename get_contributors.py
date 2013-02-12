#!/usr/bin/env python
import requests


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
]
base_url = 'https://api.github.com/repos/mozilla'
commit_levels = [100, 50, 25, 10, 1]
contributors = {}
contributors_by_level = {}


# Figure out the number of contributions per contributor:
for repo in repos:
    url = '%s/%s/contributors' % (base_url, repo)
    for repocontributor in requests.get(url).json():
        username = repocontributor['login']
        contributions = repocontributor['contributions']
        contributor = contributors.setdefault(username, {})
        contributor['contributions'] = (
            contributor.get('contributions', 0) + contributions)
        contributor.setdefault('repos', []).append(repo)

# Group the contributors into levels by number of contributions:
for user, contributor in contributors.items():
    contributions = contributor['contributions']
    for level in commit_levels:
        if contributions >= level:
            contributors_by_level.setdefault(level, []).append(user)
            break


def print_contributors():
    """Output contributors and their number of contributions."""
    for user, contributor in contributors.items():
        print '%s, %s, %s' % (
            user, contributor['contributions'], ' '.join(contributor['repos']))


def print_contributors_by_level():
    """Output contributors, based on their contribution levels."""
    for level in commit_levels:
        print '========== %s+ ==========' % level
        for user in contributors_by_level[level]:
            print user


print_contributors_by_level()
