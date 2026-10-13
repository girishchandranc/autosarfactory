# --- DEFINITION-REF post-processing -------------------------------------------
# No ECUC definition arxml is loaded, so set_definition() cannot be used (it needs
# the definition object). Each value object is registered with its definition
# path + DEST here, and the DEFINITION-REF elements are written into the saved
# file after AF.save(). AF.save() rebuilds dirty nodes, so this MUST run after it.
from lxml import etree

_DEF_REFS = []  # (value object, definition path, DEST tag)
_DEFREF_AFTER = {"SHORT-NAME", "SHORT-NAME-FRAGMENTS", "LONG-NAME", "DESC", "CATEGORY",
                 "ADMIN-DATA", "INTRODUCTION", "ANNOTATIONS", "UUID"}


def _defref(obj, def_path, dest):
    _DEF_REFS.append((obj, def_path, dest))


def _apply_definition_refs(arxml_path):
    tree = None
    for obj, def_path, dest in _DEF_REFS:
        node = obj._node
        tree = node.getroottree()
        ns = etree.QName(node).namespace
        for old in node.findall("{*}DEFINITION-REF"):
            node.remove(old)
        ref = etree.Element(f"{{{ns}}}DEFINITION-REF" if ns else "DEFINITION-REF", DEST=dest)
        ref.text = def_path
        pos = 0
        for i, child in enumerate(node):
            if isinstance(child.tag, str) and etree.QName(child).localname in _DEFREF_AFTER:
                pos = i + 1
        node.insert(pos, ref)
    if tree is not None:
        etree.indent(tree, space="  ")
        tree.write(arxml_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    print(f"[post] wrote {len(_DEF_REFS)} DEFINITION-REF element(s)")
# -------------------------------------------------------------------------------
