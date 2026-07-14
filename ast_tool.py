# -*- coding: utf-8 -*-
"""
ast_tool.py — Accès chirurgical au code Odoo (Lazy Loading)
============================================================

But : récupérer UNIQUEMENT le code d'une méthode précise d'un modèle Odoo,
sans jamais charger le fichier entier. Utilise le module `ast` de Python,
donc le code commenté est ignoré automatiquement (seule la version active
d'une méthode est renvoyée, même s'il en existe 3 en commentaire).

Fichier ISOLÉ : n'importe rien du projet, ne casse rien.

Usage en ligne de commande (pour tester) :
  python ast_tool.py --root=. --model=hr.payslip --method=unlink
  python ast_tool.py --root=. --model=hr.payslip --method=action_compute_sheet
  python ast_tool.py --root=. --model=hr.contract --list-methods

Usage comme fonction (pour la suite du projet) :
  from ast_tool import get_method_code
  code = get_method_code("/chemin/module", "hr.payslip", "unlink")
"""

import ast
import os
import sys


EXCLUDED_DIRS = {'__pycache__', 'static', 'tests', 'node_modules', '.git'}


def _iter_python_files(root):
    """Parcourt tous les fichiers .py sous `root` en ignorant les dossiers inutiles."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def _class_model_names(class_node):
    """
    Retourne l'ensemble des noms de modèles Odoo portés par une classe :
    la valeur de _name et de _inherit (str ou liste de str).
    Le code commenté est déjà absent de l'AST, donc pas de faux positifs.
    """
    names = set()
    for stmt in class_node.body:
        # On cherche les affectations simples : _name = "..."  /  _inherit = "..."
        if isinstance(stmt, ast.Assign):
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if '_name' in targets or '_inherit' in targets:
                val = stmt.value
                # _name = "hr.payslip"
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    names.add(val.value)
                # _inherit = ["hr.payslip", "mail.thread"]
                elif isinstance(val, (ast.List, ast.Tuple)):
                    for elt in val.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
    return names


def _find_classes_for_model(root, model_name):
    """
    Cherche dans tout le module toutes les classes dont _name ou _inherit
    correspond à `model_name`. Retourne une liste de tuples :
    (chemin_fichier, source_complet_du_fichier, class_node).
    """
    matches = []
    for path in _iter_python_files(root):
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                source = f.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if model_name in _class_model_names(node):
                    matches.append((path, source, node))
    return matches


def get_method_code(root, model_name, method_name):
    """
    Retourne le code source EXACT d'une méthode `method_name` du modèle
    Odoo `model_name`, cherché sous le dossier `root`.

    Retourne un dict :
      {
        "found": bool,
        "file": chemin du fichier (relatif à root) si trouvé,
        "lines": "12-45" (numéros de ligne) si trouvé,
        "code": le code source de la méthode,
        "message": explication si non trouvé
      }
    """
    classes = _find_classes_for_model(root, model_name)
    if not classes:
        return {
            "found": False,
            "message": f"Aucune classe avec _name/_inherit = '{model_name}' "
                       f"trouvée sous {root}.",
        }

    for path, source, class_node in classes:
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == method_name:
                    # ast.get_source_segment extrait le code exact (décorateurs
                    # inclus si on remonte, mais on prend le corps de la méthode).
                    code = ast.get_source_segment(source, item)
                    start = item.lineno
                    end = getattr(item, 'end_lineno', start)
                    return {
                        "found": True,
                        "file": os.path.relpath(path, root),
                        "lines": f"{start}-{end}",
                        "model": model_name,
                        "method": method_name,
                        "code": code,
                    }

    # Le modèle existe mais pas la méthode : liste ce qui existe pour aider.
    available = []
    for path, source, class_node in classes:
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                available.append(item.name)
    return {
        "found": False,
        "message": f"Le modèle '{model_name}' existe mais la méthode "
                   f"'{method_name}' est introuvable. "
                   f"Méthodes disponibles : {', '.join(sorted(set(available)))}",
    }


def list_methods(root, model_name):
    """Liste toutes les méthodes (actives) d'un modèle Odoo."""
    classes = _find_classes_for_model(root, model_name)
    if not classes:
        return {
            "found": False,
            "message": f"Aucune classe pour '{model_name}' sous {root}.",
        }
    methods = []
    for path, source, class_node in classes:
        rel = os.path.relpath(path, root)
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append({"method": item.name, "file": rel,
                                "line": item.lineno})
    return {"found": True, "model": model_name, "methods": methods}


# ── CLI de test ───────────────────────────────────────────────────────────────

def _parse_args(argv):
    args = {"root": ".", "model": None, "method": None, "list_methods": False}
    for a in argv:
        if a.startswith("--root="):
            args["root"] = a.split("=", 1)[1]
        elif a.startswith("--model="):
            args["model"] = a.split("=", 1)[1]
        elif a.startswith("--method="):
            args["method"] = a.split("=", 1)[1]
        elif a == "--list-methods":
            args["list_methods"] = True
    return args


def main():
    args = _parse_args(sys.argv[1:])
    if not args["model"]:
        print("Usage : python ast_tool.py --root=. --model=hr.payslip --method=unlink")
        print("        python ast_tool.py --root=. --model=hr.payslip --list-methods")
        sys.exit(1)

    if args["list_methods"]:
        res = list_methods(args["root"], args["model"])
        if not res["found"]:
            print(res["message"])
            sys.exit(1)
        print(f"Méthodes du modèle '{res['model']}' :")
        for m in res["methods"]:
            print(f"  - {m['method']}  ({m['file']}, ligne {m['line']})")
        return

    if not args["method"]:
        print("Précise --method=<nom> ou utilise --list-methods")
        sys.exit(1)

    res = get_method_code(args["root"], args["model"], args["method"])
    if not res["found"]:
        print(res["message"])
        sys.exit(1)

    print(f"# Modèle : {res['model']}")
    print(f"# Méthode : {res['method']}")
    print(f"# Fichier : {res['file']} (lignes {res['lines']})")
    print("# " + "-" * 60)
    print(res["code"])


if __name__ == "__main__":
    main()
