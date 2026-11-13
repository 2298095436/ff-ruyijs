"""Revalidate an existing, digest-verified wheel after fixture-only corrections."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import venv
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', required=True, type=int)
parser.add_argument('--platform', required=True, choices=('linux', 'windows'))
parser.add_argument('--native-commit', required=True)
args = parser.parse_args()
assert re.fullmatch('[0-9a-f]{40}', args.native_commit)
repo = os.environ['GITHUB_REPOSITORY']

def metadata(path):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/' + path]))

run = metadata(f'actions/runs/{args.run}')
assert run['head_sha'] == args.native_commit and run['status'] == 'completed'
subprocess.run(['git', 'diff', '--exit-code', args.native_commit, 'HEAD', '--',
                'src', 'python', 'profiles', 'tools', 'CMakeLists.txt'], check=True)
artifacts = metadata(f'actions/runs/{args.run}/artifacts?per_page=100')['artifacts']
matches = [a for a in artifacts if a['name'] == 'ruyijs-' + args.platform and not a.get('expired')]
assert len(matches) == 1
artifact = matches[0]
archive = Path('validation-runtime.zip')
with archive.open('wb') as stream:
    subprocess.run(['gh', 'api', f'repos/{repo}/actions/artifacts/{artifact["id"]}/zip'], stdout=stream, check=True)
assert artifact['digest'] == 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
with zipfile.ZipFile(archive) as bundle:
    wheels = [e for e in bundle.infolist() if e.filename.endswith('.whl')]
    assert len(wheels) == 1
    name = Path(wheels[0].filename).name
    suffix = 'win_amd64.whl' if args.platform == 'windows' else 'manylinux_2_39_x86_64.whl'
    assert name.startswith('ruyijs-') and name.endswith(suffix)
    wheel = Path(name)
    wheel.write_bytes(bundle.read(wheels[0]))
venv.EnvBuilder(with_pip=True).create('validation-venv')
python = Path('validation-venv') / ('Scripts/python.exe' if args.platform == 'windows' else 'bin/python')
subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-compile', '--only-binary=:all:', str(wheel)], check=True)
Path('artifacts').mkdir(exist_ok=True)
Path('artifacts/revalidation-provenance.json').write_text(json.dumps(dict(
    native_commit=args.native_commit, validation_commit=os.environ['GITHUB_SHA'],
    native_run=args.run, native_run_conclusion=run['conclusion'],
    archive_digest=artifact['digest'], wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
    native_compilation_performed=False), indent=2))
environment = {k:v for k,v in os.environ.items() if k not in (
    'GH_TOKEN', 'GITHUB_TOKEN', 'PYTHONPATH', 'RUYIJS_SHELL', 'LD_LIBRARY_PATH')}
raise SystemExit(subprocess.run([str(python), 'ci/browser_compatibility_check.py'], env=environment).returncode)
