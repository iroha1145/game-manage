"""Build cloud frontend explicitly and mark the resulting index for hosting."""
import argparse
import os
from pathlib import Path
import subprocess


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', required=True, help='Repository frontend directory')
    args = parser.parse_args(argv)
    frontend = Path(args.frontend).resolve(strict=True)
    environment = dict(os.environ, VITE_SERVICE_MODE='cloud')
    result = subprocess.run(['npm.cmd' if os.name == 'nt' else 'npm','run','build'],
                            cwd=frontend, env=environment, check=False)
    if result.returncode:
        return result.returncode
    index = frontend / 'dist/index.html'
    text = index.read_text(encoding='utf-8')
    if '<html ' not in text:
        raise ValueError('Build index missing html element')
    index.write_text(text.replace('<html ', '<html data-service-mode="cloud" ', 1), encoding='utf-8')
    print('cloud_frontend_built')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
