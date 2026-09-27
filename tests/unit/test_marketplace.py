"""
Unit tests for Community Skill Marketplace Registry and Installation.
"""

import tempfile
from collections.abc import Generator

import pytest

from packages.contracts.ecosystem import (
    CommunitySkillManifest,
    PluginCapability,
    PluginLifecycleState,
    SkillInstallRequest,
)
from services.ecosystem.lifecycle import PluginLifecycleManager
from services.ecosystem.marketplace import MarketplaceRegistry
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver
from services.ecosystem.vetting import SkillVettingPipeline


@pytest.fixture
def marketplace() -> Generator[MarketplaceRegistry, None, None]:
    with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as skills_dir:
        driver = SubprocessSandboxDriver()
        lifecycle = PluginLifecycleManager(
            db_path=":memory:",
            sandbox_driver=driver,
            base_plugins_dir=base_dir,
        )
        vetting = SkillVettingPipeline()
        reg = MarketplaceRegistry(
            lifecycle_manager=lifecycle,
            vetting_pipeline=vetting,
            skills_store_dir=skills_dir,
        )
        yield reg
        lifecycle.close()


def test_marketplace_lists_and_searches_curated_skills(marketplace: MarketplaceRegistry) -> None:
    skills = marketplace.list_skills()
    assert len(skills) >= 2

    weather_results = marketplace.list_skills(query="weather")
    assert len(weather_results) == 1
    assert "Weather" in weather_results[0].skill.display_name


def test_marketplace_installs_verified_skill(marketplace: MarketplaceRegistry) -> None:
    req = SkillInstallRequest(
        skill_id="skill.community.weather",
        accepted_capabilities=[PluginCapability.NETWORK_OUTBOUND],
        auto_enable=True,
    )
    state = marketplace.install_skill(req, actor="admin")
    assert state == PluginLifecycleState.ENABLED

    # Check plugin in lifecycle manager
    plugin = marketplace.lifecycle_manager.get_plugin("skill.community.weather")
    assert plugin is not None
    assert plugin["state"] == PluginLifecycleState.ENABLED
    assert PluginCapability.NETWORK_OUTBOUND in plugin["granted_capabilities"]


def test_marketplace_blocks_installation_of_unverified_skill(
    marketplace: MarketplaceRegistry,
) -> None:
    bad_manifest = CommunitySkillManifest(
        skill_id="skill.evil",
        publisher="attacker",
        version="1.0.0",
        display_name="Evil Skill",
        description="Shell execution",
        capabilities=[],
    )
    bad_code = {"main.py": "import os\nos.system('calc.exe')"}
    marketplace.publish_skill(bad_manifest, bad_code)

    req = SkillInstallRequest(skill_id="skill.evil")
    with pytest.raises(ValueError, match="Cannot install unverified"):
        marketplace.install_skill(req)
