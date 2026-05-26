import ast
import re

JS_IMPORT_PATTERNS = [
    re.compile(r"""import\s+.*?\s+from\s+['"]([^'"]+)['"]"""),
    re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
]

JAVA_IMPORT_PATTERN = re.compile(r"import\s+([\w\.]+)\s*;")


class LanguageParser:
    def extract_dependencies(self, code: str, language: str, file_path: str) -> list[str]:
        if language == "python":
            return self._extract_python_deps(code)
        if language in ("javascript", "typescript"):
            return self._extract_js_deps(code)
        if language == "java":
            return self._extract_java_deps(code)
        return []

    def _extract_python_deps(self, code: str) -> list[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        deps = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                deps.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                deps.append(node.module)
        return list(dict.fromkeys(deps))

    def _extract_js_deps(self, code: str) -> list[str]:
        deps = [m.group(1) for pat in JS_IMPORT_PATTERNS for m in pat.finditer(code)]
        return list(dict.fromkeys(deps))

    def _extract_java_deps(self, code: str) -> list[str]:
        deps = [m.group(1) for m in JAVA_IMPORT_PATTERN.finditer(code)]
        return list(dict.fromkeys(deps))


language_parser = LanguageParser()
