"""PIXEL — Automated Regression Test Generator.

Generates structured Python pytest cases from reproduction data, performing AST static validation
to guarantee that generated tests do not weaken safety boundaries, delete tests, or bypass L6/L8 gates.
"""

import ast
import uuid

from packages.contracts.evolution import GeneratedRegressionTest


class RegressionTestGenerator:
    """Produces verified, safety-checked regression tests."""

    def generate_test(
        self,
        target_module: str,
        test_function_name: str,
        setup_code: str,
        execution_code: str,
        assertion_code: str,
    ) -> GeneratedRegressionTest:
        """Constructs a pytest regression test and performs static safety checks."""
        test_id = f"reg-test-{uuid.uuid4().hex[:8]}"

        code_template = (
            f'"""Automated Regression Test for {target_module} (ID: {test_id})."""\n\n'
            f"import pytest\n\n"
            f"def {test_function_name}():\n"
            f"    # Setup\n"
            f"    {setup_code}\n\n"
            f"    # Execution\n"
            f"    {execution_code}\n\n"
            f"    # Assertion\n"
            f"    {assertion_code}\n"
        )

        ast_valid, safety_checked, _ = self.validate_test_safety(code_template)

        return GeneratedRegressionTest(
            test_id=test_id,
            target_module=target_module,
            test_code=code_template,
            ast_valid=ast_valid,
            safety_checked=safety_checked,
        )

    def validate_test_safety(self, test_code: str) -> tuple[bool, bool, list[str]]:
        """Parses Python AST and verifies that the test code conforms to safety invariants."""
        violations: list[str] = []

        try:
            tree = ast.parse(test_code)
        except SyntaxError as e:
            return False, False, [f"SyntaxError: {str(e)}"]

        has_assert = False
        forbidden_names = {
            "eval",
            "exec",
            "__import__",
            "os.system",
            "os.remove",
            "shutil.rmtree",
            "subprocess.run",
            "subprocess.Popen",
            "sys.exit",
        }
        forbidden_imports = {"subprocess", "shutil", "ctypes"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                has_assert = True

            # Check forbidden imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        violations.append(f"Forbidden import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in forbidden_imports:
                    violations.append(f"Forbidden from-import: {node.module}")

            # Check assignments to policy gate / action verifier
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if (
                            "policy_gate" in target.id.lower()
                            or "action_verifier" in target.id.lower()
                        ):
                            violations.append(
                                f"Forbidden attempt to alter policy or verifier: {target.id}"
                            )

            # Check forbidden calls
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                    else:
                        func_name = node.func.attr

                if (
                    func_name in forbidden_names
                    or func_name.startswith("os.")
                    or func_name.startswith("subprocess.")
                ):
                    violations.append(f"Forbidden call in regression test: {func_name}")

                # Anti-tampering: Prohibit mocking or bypassing policy gate in generated tests
                if "policy_gate" in func_name.lower() or "action_verifier" in func_name.lower():
                    violations.append(f"Forbidden attempt to alter policy or verifier: {func_name}")

        if not has_assert:
            violations.append("Regression test must contain at least one assert statement")

        is_safe = len(violations) == 0
        return True, is_safe, violations
