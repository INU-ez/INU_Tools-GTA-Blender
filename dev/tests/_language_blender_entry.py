import sys, json, os
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
import bpy, addon_utils
view=bpy.context.preferences.view
view.language='en_US'
view.use_translate_interface=False
before=view.use_translate_interface
addon_utils.enable('INU_tools', default_set=False)
import INU_tools
from INU_tools.ui.panels import GTATOOLS_PT_paths_panel
from INU_tools.tools.ui_language import CONTEXT
assert view.use_translate_interface == before, 'Addon changed Blender language preferences'
assert GTATOOLS_PT_paths_panel.bl_label == 'Paths', GTATOOLS_PT_paths_panel.bl_label
results=[]
for language, enabled, expected in [('en_US',False,'Paths'),('en_US',True,'Paths'),('ru_RU',True,'Пути'),('ru_RU',False,'Paths'),('es',True,'Rutas')]:
    view.language=language
    view.use_translate_interface=enabled
    dynamic=INU_tools.T('Пути')
    native=bpy.app.translations.pgettext_iface(GTATOOLS_PT_paths_panel.bl_label, CONTEXT)
    print('LANGUAGE_CHECK',language,enabled,repr(dynamic),repr(native),flush=True)
    assert dynamic == expected, (language,dynamic,expected)
    assert native == expected, (language,native,expected)
    results.append(dict(language=language,translation=enabled,dynamic=dynamic,native=native))
view.language='en_US'
view.use_translate_interface=False
settings=INU_tools.INUSceneSettings.bl_rna
names=[p.name for p in settings.properties if p.identifier!='rna_type']
print('PROPERTY_SAMPLE',names[:15],flush=True)
remaining=[]
for cls in INU_tools.classes+(INU_tools.INUSceneSettings,):
    label=getattr(cls,'bl_label','')
    if any('А' <= c <= 'я' or c in 'Ёё' for c in label):
        remaining.append((cls.__name__,label))
print('REMAINING_RUSSIAN_LABELS',remaining,flush=True)
assert not remaining, remaining
addon_utils.disable('INU_tools', default_set=False)
view.language='ru_RU'
view.use_translate_interface=True
addon_utils.enable('INU_tools', default_set=False)
view.language='en_US'
view.use_translate_interface=False
from INU_tools.ops.path_curves import GTATOOLS_OT_curves_to_nodes
from INU_tools.locale import get_translation
name=bpy.ops.gtatools.curves_to_nodes.get_rna_type().properties['entire_map'].name
assert name == get_translation('eng')['Записать всю карту'], name
assert GTATOOLS_PT_paths_panel.bl_label == 'Paths'
assert view.use_translate_interface is False
addon_utils.disable('INU_tools', default_set=False)
output=root/'dev/tests/.blender_nodes_runtime'
output.mkdir(exist_ok=True)
(output/'language-check-result.json').write_text(json.dumps(dict(status='passed',cases=results,reload=True,preferences_unchanged=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
