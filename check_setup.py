"""Read-only local prerequisites check. Never prints credentials or opens a database."""
import importlib.metadata
import subprocess
import sys


def main():
    failures = []
    if sys.version_info < (3, 11):
        failures.append('Python 3.11 or later required')
    print('Python: ' + sys.version.split()[0])
    for name in ('Pillow', 'imageio-ffmpeg'):
        try:
            print(name + ': ' + importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:
            failures.append(name + ' is missing; install OrderThread/requirements.txt')
    try:
        import imageio_ffmpeg
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-version'], capture_output=True, timeout=10)
        if result.returncode:
            raise RuntimeError()
        print('Local FFmpeg executable: OK')
    except Exception:
        failures.append('Local FFmpeg executable unavailable')
    try:
        from demo import load_app
        app = load_app()  # reads configuration only; no database/network access
        configured = [p['name'] for p in app.provider_status()['providers'] if p.get('configured')]
        print('Providers with a local key present: ' + (', '.join(configured) or 'none'))
        print('Key presence does not verify access, credits, modalities or live output.')
    except Exception:
        failures.append('Application configuration could not be loaded; check local setup privately')
    for failure in failures:
        print('FAIL: ' + failure)
    if not failures:
        print('Local runtime prerequisites passed. Browser/microphone and live provider rehearsal remain separate.')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
