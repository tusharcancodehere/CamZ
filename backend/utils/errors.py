from __future__ import annotations

import traceback
from typing import Any


class StructuredError(Exception):
    """Production-grade structured exception providing complete failure details."""

    def __init__(
        self,
        component: str,
        problem: str,
        root_cause: str,
        impact: str,
        recovery_attempt: str = "None",
        suggested_fix: str = "Refer to troubleshooting guide",
        doc_reference: str = "README.md",
        exit_code: int = 1,
        original_exception: Exception | None = None,
    ) -> None:
        self.component = component
        self.problem = problem
        self.root_cause = root_cause
        self.impact = impact
        self.recovery_attempt = recovery_attempt
        self.suggested_fix = suggested_fix
        self.doc_reference = doc_reference
        self.exit_code = exit_code
        self.original_exception = original_exception

        # Capture formatted traceback if an exception is active or provided
        if original_exception:
            self.traceback_str = "".join(
                traceback.format_exception(
                    type(original_exception),
                    original_exception,
                    original_exception.__traceback__,
                )
            )
        else:
            self.traceback_str = "".join(traceback.format_stack()[:-1])

        super().__init__(f"[{self.component.upper()}] {self.problem}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize structured details to a JSON-compatible dict."""
        return {
            "component": self.component,
            "problem": self.problem,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "recovery_attempt": self.recovery_attempt,
            "suggested_fix": self.suggested_fix,
            "doc_reference": self.doc_reference,
            "exit_code": self.exit_code,
            "original_exception": str(self.original_exception) if self.original_exception else None,
            "traceback": self.traceback_str,
        }

    def format_terminal(self) -> str:
        """Format the error as a highly visible, colored terminal report."""
        red = "\033[91m"
        yellow = "\033[93m"
        cyan = "\033[96m"
        bold = "\033[1m"
        reset = "\033[0m"

        report = [
            f"{red}{bold}=================================================={reset}",
            f"{red}{bold}           CRITICAL SYSTEM FAILURE: {self.component.upper()}{reset}",
            f"{red}{bold}=================================================={reset}",
            f"{bold}PROBLEM:{reset}           {self.problem}",
            f"{bold}ROOT CAUSE:{reset}        {self.root_cause}",
            f"{bold}IMPACT:{reset}            {self.impact}",
            f"{bold}RECOVERY ATTEMPT:{reset}  {self.recovery_attempt}",
            f"{yellow}{bold}AUTOMATIC FIX:{reset}     {self.recovery_attempt if self.recovery_attempt != 'None' else 'No automatic recovery available.'}",
            f"{cyan}{bold}MANUAL FIX:{reset}        {self.suggested_fix}",
            f"{bold}DOC REFERENCE:{reset}     {self.doc_reference}",
            f"{bold}EXIT CODE:{reset}         {self.exit_code}",
            f"{red}{bold}--------------------------------------------------{reset}",
        ]
        if self.original_exception:
            report.append(f"{bold}UNDERLYING EXCEPTION:{reset} {self.original_exception}")
        return "\n".join(report)
