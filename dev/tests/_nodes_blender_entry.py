"""Run native NODES integration and IFP preview tests in factory Blender.

Usage: blender --background --factory-startup --python-exit-code 1
       --python dev/tests/_nodes_blender_entry.py
Uses an existing pure-Python pytest installation; installs nothing into Blender.
If Blender cannot import pytest, set INU_PYTEST_SITE_PACKAGES to the directory
containing pytest and its pure-Python dependencies before running this script.
"""

import json
import os
from pathlib import Path
import sys
import traceback
import xml.etree.ElementTree as ET

os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'dev/tests/.blender_nodes_runtime'
OUTPUT.mkdir(exist_ok=True)
REPORT = OUTPUT / 'result.json'
result = dict(status='running')
try:
    import bpy
    result['blender'] = bpy.app.version_string
    result['native_bpy'] = True
    if hasattr(bpy.context.preferences.filepaths, 'use_save_preview'):
        bpy.context.preferences.filepaths.use_save_preview = False
    sys.path.insert(0, str(ROOT))
    # Append after Blender's own binary dependencies (numpy/mathutils).
    # pytest and its dependencies are pure Python and work on Python 3.13.
    try:
        import pytest
    except ImportError:
        pure_site = os.environ.get('INU_PYTEST_SITE_PACKAGES')
        if not pure_site or not Path(pure_site).is_dir():
            raise RuntimeError('Set INU_PYTEST_SITE_PACKAGES to an existing pytest site-packages directory')
        sys.path.append(str(pure_site))
        import pytest
    import INU_tools
    assert Path(INU_tools.__file__).resolve().parent == ROOT / 'INU_tools', INU_tools.__file__
    result['addon'] = INU_tools.__file__
    INU_tools.register()
    result['addon_registered'] = True
    print('[native-nodes] Blender:', bpy.app.version_string, flush=True)
    print('[native-nodes] Addon:', INU_tools.__file__, flush=True)
    args = ['-v', '-s', '-rs', '-p', 'no:cacheprovider',
            '--basetemp=' + str(OUTPUT / 'pytest_tmp'),
            '--junitxml=' + str(OUTPUT / 'junit.xml'),
            str(ROOT / 'dev/tests/test_ifp_preview.py'),
            str(ROOT / 'dev/tests/e2e/test_nodes_edit_e2e.py')]
    exit_code = pytest.main(args)
    result['pytest_exit_code'] = int(exit_code)
    suite = ET.parse(OUTPUT / 'junit.xml').getroot().find('testsuite')
    result['tests'] = int(suite.get('tests'))
    result['failures'] = int(suite.get('failures'))
    result['errors'] = int(suite.get('errors'))
    result['skipped'] = int(suite.get('skipped'))
    result['elapsed_seconds'] = float(suite.get('time'))
    result['status'] = 'passed' if exit_code == 0 else 'failed'
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    INU_tools.unregister()
    if exit_code:
        raise RuntimeError('Native Blender test failure: ' + str(exit_code))
except BaseException:
    result['status'] = 'failed'
    result['traceback'] = traceback.format_exc()
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    raise
