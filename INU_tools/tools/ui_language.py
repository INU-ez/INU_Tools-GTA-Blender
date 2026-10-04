"""English RNA source labels, translated by Blender when UI translation is on."""

import ast

CONTEXT = 'INU Tools'


def source_translator(english, languages):
    reverse = {}
    for mapping in languages:
        for source, translated in mapping.items():
            reverse.setdefault(translated, source)

    def translate(text):
        if not isinstance(text, str):
            return text
        return english.get(text, english.get(reverse.get(text), text))
    return translate


def _literal(node, translate):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'T' and len(node.args) == 1:
        node = node.args[0]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ast.Constant(translate(node.value))
    return node


def _annotation(value, translate):
    # Blender evaluates postponed Property annotations during registration.
    # Rewrite only their display literals, without evaluating addon code here.
    if not hasattr(ast, 'unparse'):
        return value
    try:
        tree = ast.parse(value, mode='eval')
    except SyntaxError:
        return value
    call = tree.body
    if not isinstance(call, ast.Call):
        return value
    name = getattr(call.func, 'id', getattr(call.func, 'attr', ''))
    if not name.endswith('Property'):
        return value
    context = None
    for keyword in call.keywords:
        if keyword.arg in ('name', 'description'):
            keyword.value = _literal(keyword.value, translate)
        elif keyword.arg == 'translation_context':
            context = keyword
        elif keyword.arg == 'items' and isinstance(keyword.value, (ast.List, ast.Tuple)):
            for item in keyword.value.elts:
                if isinstance(item, (ast.List, ast.Tuple)) and len(item.elts) >= 3:
                    item.elts[1] = _literal(item.elts[1], translate)
                    item.elts[2] = _literal(item.elts[2], translate)
    if context is None:
        call.keywords.append(ast.keyword(arg='translation_context', value=ast.Constant(CONTEXT)))
    elif isinstance(context.value, ast.Constant) and context.value.value == '*':
        context.value = ast.Constant(CONTEXT)
    return ast.unparse(ast.fix_missing_locations(tree))


def prepare_class(cls, translate):
    cls.bl_translation_context = CONTEXT
    for name in ('bl_label', 'bl_description'):
        value = cls.__dict__.get(name)
        if isinstance(value, str):
            setattr(cls, name, translate(value))
    annotations = cls.__dict__.get('__annotations__', {})
    for key, prop in list(annotations.items()):
        if isinstance(prop, str):
            annotations[key] = _annotation(prop, translate)
            continue
        keywords = getattr(prop, 'keywords', None)
        if not isinstance(keywords, dict):
            continue
        if keywords.get('translation_context', '*') == '*':
            keywords['translation_context'] = CONTEXT
        for name in ('name', 'description'):
            if name in keywords:
                keywords[name] = translate(keywords[name])
        items = keywords.get('items')
        if isinstance(items, (list, tuple)):
            keywords['items'] = [None if item is None else
                                 (item[0], translate(item[1]), translate(item[2]), *item[3:])
                                 for item in items]


def translation_entries(english, target, contexts, *, russian=False):
    entries = {}
    for source, translated in english.items():
        value = source if russian else target.get(source, translated)
        for context in contexts:
            entries[(context, translated)] = value
    return entries
