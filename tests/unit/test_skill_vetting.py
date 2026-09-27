"""
Unit tests for Community Skill Automated Security Vetting Pipeline.
"""

import pytest

from packages.contracts.ecosystem import (
    CommunitySkillManifest,
    FindingSeverity,
    PluginCapability,
    VettingState,
)
from services.ecosystem.vetting import SkillVettingPipeline


@pytest.fixture
def vetting_pipeline() -> SkillVettingPipeline:
    return SkillVettingPipeline()


def test_vetting_passes_clean_skill(vetting_pipeline: SkillVettingPipeline) -> None:
    manifest = CommunitySkillManifest(
        skill_id="skill.clean",
        publisher="trusted_dev",
        version="1.0.0",
        display_name="Clean Tool",
        description="A completely safe tool",
        triggers=["clean"],
        capabilities=[PluginCapability.TOOL_INVOCATION],
    )
    source_files = {
        "main.py": """
import sys, json

for line in sys.stdin:
    req = json.loads(line)
    val = req.get("params", {}).get("x", 0) * 2
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": val}))
    sys.stdout.flush()
"""
    }
    report = vetting_pipeline.vet_skill(manifest, source_files)
    assert report.passed is True
    assert report.state == VettingState.PASSED
    assert len(report.findings) == 0


def test_vetting_rejects_eval_and_exec(vetting_pipeline: SkillVettingPipeline) -> None:
    manifest = CommunitySkillManifest(
        skill_id="skill.eval_exploit",
        publisher="malicious",
        version="1.0.0",
        display_name="Exploit Tool",
        description="Uses eval",
        capabilities=[],
    )
    source_files = {
        "main.py": """
import sys
user_input = sys.stdin.read()
eval(user_input)
"""
    }
    report = vetting_pipeline.vet_skill(manifest, source_files)
    assert report.passed is False
    assert report.state == VettingState.REJECTED
    assert any(f.code == "DANGEROUS_EVAL" for f in report.findings)


def test_vetting_rejects_forbidden_modules(vetting_pipeline: SkillVettingPipeline) -> None:
    manifest = CommunitySkillManifest(
        skill_id="skill.subprocess_exploit",
        publisher="malicious",
        version="1.0.0",
        display_name="Subprocess Exploit",
        description="Tries to spawn child subprocess",
        capabilities=[],
    )
    source_files = {
        "main.py": """
import subprocess
subprocess.Popen(["calc.exe"])
"""
    }
    report = vetting_pipeline.vet_skill(manifest, source_files)
    assert report.passed is False
    assert report.state == VettingState.REJECTED
    assert any(f.severity == FindingSeverity.CRITICAL for f in report.findings)


def test_vetting_flags_exposed_secrets(vetting_pipeline: SkillVettingPipeline) -> None:
    manifest = CommunitySkillManifest(
        skill_id="skill.secret_leak",
        publisher="dev",
        version="1.0.0",
        display_name="Leaky Skill",
        description="Contains hardcoded API key",
        capabilities=[],
    )
    source_files = {
        "main.py": """
API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
print(API_KEY)
"""
    }
    report = vetting_pipeline.vet_skill(manifest, source_files)
    assert report.passed is False
    assert report.state == VettingState.REJECTED
    assert any("EXPOSED_SECRET" in f.code for f in report.findings)
