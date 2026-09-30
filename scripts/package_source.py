from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
output = root.parent / 'starclinch-notifications-source.zip'
excluded_dirs = {'.venv', 'node_modules', '__pycache__', 'staticfiles', 'dist', '.git', '.vercel', '.pytest_cache'}

def include(path):
    relative = path.relative_to(root)
    if any(part in excluded_dirs for part in relative.parts):
        return False
    if path.name.startswith('.env') and path.name != '.env.example':
        return False
    if path.name == '.local-access.txt' or path.suffix in {'.sqlite3', '.pyc', '.log'}:
        return False
    return path.is_file()

with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        if include(path):
            archive.write(path, Path(root.name) / path.relative_to(root))
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert not any(name.endswith('/.env') or name.endswith('/.local-access.txt') for name in archive.namelist())
    print(f'Packaged {len(archive.namelist())} source files: {output}')
