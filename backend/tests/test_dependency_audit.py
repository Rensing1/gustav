"""The online audit must report every ecosystem even after an earlier failure."""

from subprocess import CompletedProcess

import pytest

from backend.tools.dependency_audit import run_audits


@pytest.mark.parametrize("failed_index", [None, 0, 1, 2])
def test_all_ecosystems_run_and_failures_are_aggregated(failed_index):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(command, 1 if len(calls) - 1 == failed_index else 0)

    assert run_audits(run=run) == (0 if failed_index is None else 1)
    assert len(calls) == 3
    assert calls[0][0] == ["npm", "audit", "--audit-level=low"]
    assert calls[1][0] == ["npm", "audit", "--omit=dev", "--audit-level=low"]
    assert "pip_audit" in calls[2][0]
    assert "--ignore-vuln" not in calls[2][0]


def test_missing_executable_does_not_hide_other_ecosystems():
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise FileNotFoundError()
        return CompletedProcess(command, 0)

    assert run_audits(run=run) == 1
    assert len(calls) == 3
