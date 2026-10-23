"""Decide source refresh scope against every change in a GitHub push."""
import os
import re
import subprocess
from pathlib import Path

SOURCE_FILES = {
    'update.py', 'ai_translate.py', 'crawl.py', 'public_sources.py',
    'source_gateway.py', 'reader_gateway.py', 'requirements.txt', 'data/seed.json',
}


def should_refresh(event, before='', *, root=None):
    if event != 'push':
        return True
    if not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', before) or not before.strip('0'):
        return True

    def git(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)

    if git('cat-file', '-e', before + '^{commit}').returncode:
        if git('fetch', '--no-tags', '--depth=1', 'origin', before).returncode:
            return True
    # HEAD is the current branch checkout, including any commits made while
    # this workflow waited in the queue. Never inspect only its last commit.
    changed = git('diff', '--name-only', before, 'HEAD')
    return changed.returncode != 0 or bool(SOURCE_FILES.intersection(changed.stdout.splitlines()))


def main():
    refresh = should_refresh(os.environ.get('GITHUB_EVENT_NAME', ''),
                             os.environ.get('PUSH_BEFORE', ''))
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
            output.write('refresh=' + str(refresh).lower() + '\n')
    print('Refresh sources' if refresh else 'Publish UI using the retained archive')


if __name__ == '__main__':
    main()
