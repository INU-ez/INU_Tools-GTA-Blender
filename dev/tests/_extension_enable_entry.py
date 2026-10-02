"""Enable the built ZIP in a temporary local Blender extension repository.

Run with factory settings and isolated BLENDER_USER_CONFIG and
BLENDER_USER_EXTENSIONS directories:
blender --background --factory-startup --disable-autoexec --python-exit-code 1
        --python dev/tests/_extension_enable_entry.py -- path/to/package.zip
No user preferences or installed addons are saved or replaced.
"""

import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import tomllib
import traceback
import zipfile

import addon_utils
import bpy
try:
    from _bpy_restrict_state import RestrictBlend
except ModuleNotFoundError as error:
    if error.name != '_bpy_restrict_state':
        raise
    # Blender 4.2 LTS uses the name without the leading underscore.
    from bpy_restrict_state import RestrictBlend

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'dev/tests/.blender_nodes_runtime'
OUTPUT.mkdir(exist_ok=True)
for environment_name in ('BLENDER_USER_CONFIG', 'BLENDER_USER_EXTENSIONS'):
    if environment_path := os.environ.get(environment_name):
        Path(environment_path).mkdir(parents=True, exist_ok=True)
REPORT = OUTPUT / 'extension-enable-result.json'
arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
archive = Path(arguments[0]).resolve() if arguments else ROOT / 'inu_tools_gta_sa-2.5.0.zip'
result = dict(status='running', blender=bpy.app.version_string, archive=str(archive))
repo = None
module_name = None


def fail(error):
    raise error


try:
    with zipfile.ZipFile(archive) as package:
        manifest = tomllib.loads(package.read('blender_manifest.toml').decode('utf-8'))
        package_id = manifest['id']
        assert package_id.isidentifier(), package_id
        repo_directory = Path(tempfile.mkdtemp(prefix='extension_enable_', dir=OUTPUT))
        destination = repo_directory / package_id
        destination.mkdir()
        for entry in package.infolist():
            name = PurePosixPath(entry.filename.replace('\\', '/'))
            assert not name.is_absolute() and '..' not in name.parts, entry.filename
            assert (destination / str(name)).resolve().is_relative_to(destination)
        package.extractall(destination)

    repo = bpy.context.preferences.extensions.repos.new(
        name='INU isolated enable regression', module='inu_enable_test',
        custom_directory=str(repo_directory), remote_url='', source='USER')
    repo.enabled = True
    module_name = 'bl_ext.' + repo.module + '.' + package_id
    result.update(version=manifest['version'], module=module_name,
                  archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())

    # A curve already present when the user enables the extension must be
    # initialized later, not read while Blender restricts registration.
    curve = bpy.data.curves.new('INU existing path', 'CURVE')
    spline = curve.splines.new('POLY')
    spline.points.add(1)
    spline.points[0].co = (0, 0, 0, 1)
    spline.points[1].co = (10, 0, 0, 1)
    obj = bpy.data.objects.new('INU existing path', curve)
    bpy.context.scene.collection.objects.link(obj)
    obj['path_type'] = 'path_ipl'
    obj['pn_semantics_version'] = 2
    obj['pn_count'] = 2
    for index in range(2):
        obj[f'pn_{index}_type'] = 2

    for cycle in range(3):
        enabled = addon_utils.enable(module_name, default_set=False, handle_error=fail)
        assert enabled is not None and enabled.__addon_enabled__
        if cycle == 0:
            # Blender also reloads an enabled addon during an update.
            enabled = addon_utils.enable(module_name, default_set=False, handle_error=fail)
            assert enabled is not None and enabled.__addon_enabled__
            result['reload_while_enabled'] = True
        assert hasattr(bpy.types.Scene, 'inu_settings')
        props = importlib.import_module(module_name + '.ops.path_ipl_props')
        assert bpy.app.timers.is_registered(props._path_identity_initialize)
        assert bpy.app.handlers.load_post.count(props._path_identity_load) == 1
        assert bpy.app.handlers.depsgraph_update_post.count(props._path_identity_update) == 1
        if cycle != 1:
            # Exercise both timer paths without blocking the background
            # process on Blender's interactive event loop.
            with RestrictBlend():
                assert props._path_identity_initialize() == 0.1
            assert props._path_identity_initialize() is None
            assert obj['pn_identity_version'] == 1
            assert [slot for _point, slot in props.ensure_point_slots(obj)] == [0, 1]
        addon_utils.disable(module_name, default_set=False, handle_error=fail)
        assert not enabled.__addon_enabled__
        assert not hasattr(bpy.types.Scene, 'inu_settings')
        assert not bpy.app.timers.is_registered(props._path_identity_initialize)
        assert props._path_identity_load not in bpy.app.handlers.load_post
        assert props._path_identity_update not in bpy.app.handlers.depsgraph_update_post
        result['enable_disable_cycles'] = cycle + 1

    result.update(status='passed', existing_curve_migrated=True,
                  restricted_registration=True, pending_timer_cancelled=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('[INU extension enable]', json.dumps(result), flush=True)
except BaseException:
    result.update(status='failed', traceback=traceback.format_exc())
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    raise
finally:
    if module_name and addon_utils.check(module_name)[1]:
        addon_utils.disable(module_name, default_set=False, handle_error=fail)
    if repo is not None:
        bpy.context.preferences.extensions.repos.remove(repo)
