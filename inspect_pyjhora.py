import importlib
import ast
import inspect
import json
import pkgutil

import jhora


OUTPUT_FILE = "pyjhora_inventory.json"

CANDIDATE_KEYWORDS = {
    "dashas": ("dasha", "dhasa", "dasas", "vimsottari", "vimshottari"),
    "divisional_charts": ("division", "divisional", "charts", "d_chart", "varga"),
    "arudhas": ("arudha", "arud"),
    "planetary_motion": ("planet", "graha", "motion", "retro", "longitude"),
    "strengths": ("strength", "bala", "ashtakavarga", "shadbala"),
    "houses": ("house", "bhava"),
    "jaimini": ("jaimini", "chara", "karaka"),
    "yogas": ("yoga",),
    "transits": ("transit", "gochara"),
}


def source_members(module_name, source_file):
    functions = []
    classes = []

    if not source_file or not source_file.endswith(".py"):
        return functions, classes

    try:
        with open(source_file, "r", encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=source_file)
    except Exception:
        return functions, classes

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name.startswith("_"):
            continue

        qualified_name = f"{module_name}.{node.name}"
        if isinstance(node, ast.ClassDef):
            classes.append(qualified_name)
        else:
            functions.append(qualified_name)

    return functions, classes


def public_members(module):
    functions = []
    classes = []

    for name, value in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        qualified_name = f"{module.__name__}.{name}"

        if inspect.isfunction(value):
            functions.append(qualified_name)
        elif inspect.isclass(value):
            classes.append(qualified_name)

    return functions, classes


def categorize(name):
    lowered = name.lower()
    categories = []

    for category, keywords in CANDIDATE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            categories.append(category)

    return categories


def main():
    modules = []
    candidate_functions = {
        "dashas": [],
        "divisional_charts": [],
        "arudhas": [],
        "planetary_motion": [],
        "strengths": [],
        "houses": [],
        "jaimini": [],
        "yogas": [],
        "transits": [],
    }

    package_prefix = f"{jhora.__name__}."
    module_infos = sorted(
        pkgutil.walk_packages(jhora.__path__, package_prefix),
        key=lambda info: info.name,
    )

    for module_info in module_infos:
        spec = module_info.module_finder.find_spec(module_info.name)
        module_record = {
            "name": module_info.name,
            "is_package": module_info.ispkg,
            "file": getattr(spec, "origin", None),
            "public_functions": [],
            "public_classes": [],
            "import_error": None,
        }

        for category in categorize(module_info.name):
            if module_info.name not in candidate_functions[category]:
                candidate_functions[category].append(module_info.name)

        try:
            module = importlib.import_module(module_info.name)
        except Exception as error:
            module_record["import_error"] = str(error)
            functions, classes = source_members(
                module_info.name,
                module_record["file"],
            )
            module_record["public_functions"] = functions
            module_record["public_classes"] = classes

            for item_name in [*functions, *classes]:
                for category in categorize(item_name):
                    if item_name not in candidate_functions[category]:
                        candidate_functions[category].append(item_name)

            modules.append(module_record)
            continue

        module_record["file"] = getattr(module, "__file__", None)
        functions, classes = public_members(module)
        module_record["public_functions"] = functions
        module_record["public_classes"] = classes

        for item_name in [module_info.name, *functions, *classes]:
            for category in categorize(item_name):
                if item_name not in candidate_functions[category]:
                    candidate_functions[category].append(item_name)

        modules.append(module_record)

    inventory = {
        "package": {
            "name": jhora.__name__,
            "file": getattr(jhora, "__file__", None),
            "package": getattr(jhora, "__package__", None),
        },
        "modules": modules,
        "candidate_functions": candidate_functions,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as output:
        json.dump(inventory, output, indent=2)

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Inspected {len(modules)} modules")


if __name__ == "__main__":
    main()
