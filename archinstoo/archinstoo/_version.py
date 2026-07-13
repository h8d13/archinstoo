import subprocess

def git_shash() -> str:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
def git_branch() -> str:
         return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('ascii').strip()

__license__ = '- Copyright (C) 2026 - Hadean Eon'
__version__ = f'0.1.13-4 ({git_branch()}-{git_shash()}) {__license__}'
