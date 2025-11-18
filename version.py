import subprocess
import os

def get_version():
    try:
        # Check if we're in a git repo
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback version
    return '1.1.0'

__version__ = get_version()
