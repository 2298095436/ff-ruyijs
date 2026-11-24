"""The runtime pin may already carry the shared connection patch.

Validate original and patched inputs, repeated application, and refusal of
unknown or mixed inputs without downloading a runtime or building NSS.
"""
import importlib.util
from pathlib import Path


def main():
    path = Path(__file__).resolve().parents[1] / 'tools/necko_connect_patch.py'
    spec = importlib.util.spec_from_file_location('necko_connect_patch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = '# fixture prefix\n' + module.OLD + '# fixture suffix\n'
    patched = '# fixture prefix\n' + module.NEW + '# fixture suffix\n'
    assert module.apply(original) == patched
    assert module.apply(patched) == patched
    assert module.apply(module.apply(original)) == patched
    for invalid in ['# unknown source\n', module.NEW + module.NEW, module.OLD + module.NEW]:
        try:
            module.apply(invalid)
        except ValueError:
            continue
        raise AssertionError('Unknown or mixed patch state was accepted')
    print('ok original, already-patched and repeated patch inputs; unknown/mixed states refused', flush=True)


if __name__ == '__main__':
    main()
