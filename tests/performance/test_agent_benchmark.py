"""Performance benchmarks for PIXEL LangGraph Agent Runtime and Policy Engine."""

import tempfile
import time
from pathlib import Path

import pytest

from packages.contracts.agent import AgentState
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer
from services.agent_runtime.engine import AgentRuntimeEngine
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.builtin import WriteFileTool
from services.intent_engine.engine import DeterministicIntentEngine


@pytest.mark.asyncio
async def test_agent_performance_benchmarks() -> None:
    temp_cp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    checkpointer = SQLiteCheckpointer(db_path=temp_cp)
    agent_engine = AgentRuntimeEngine(checkpointer=checkpointer)
    policy_gate = AgentPolicyGate()
    write_tool = WriteFileTool()
    intent_engine = DeterministicIntentEngine(agent_engine=agent_engine)

    # 1. Benchmark Policy Gate Evaluation (100 evaluations)
    start_time = time.perf_counter()
    for _ in range(100):
        policy_gate.evaluate(
            tool_spec=write_tool.spec,
            arguments={"path": "safe.txt", "content": "test"},
            task_id="bench_task",
            session_id="bench_sess",
            user_id="bench_user",
        )
    policy_total_ms = (time.perf_counter() - start_time) * 1000
    avg_policy_ms = policy_total_ms / 100

    # 2. Benchmark Checkpoint Save and Retrieve (50 cycles)
    state = AgentState(user_query="Benchmark Task", session_id="s_bench", user_id="u_bench")
    start_time = time.perf_counter()
    for _ in range(50):
        await agent_engine.checkpointer.save_checkpoint(state)
        await agent_engine.checkpointer.get_latest_checkpoint(state.task_id)
    cp_total_ms = (time.perf_counter() - start_time) * 1000
    avg_cp_ms = cp_total_ms / 50

    # 3. Benchmark End-to-End Agent Task Execution (20 executions)
    with tempfile.TemporaryDirectory() as tmpdir:
        start_time = time.perf_counter()
        for i in range(20):
            target = Path(tmpdir) / f"bench_{i}.txt"
            await agent_engine.execute_task(
                user_query=f"write content to {target}",
                session_id=f"sess_bench_{i}",
                user_id="u_bench",
            )
        agent_exec_total_ms = (time.perf_counter() - start_time) * 1000
        avg_agent_exec_ms = agent_exec_total_ms / 20

    # 4. Benchmark Deterministic Fast-Path Regression (100 commands)
    start_time = time.perf_counter()
    for _ in range(100):
        await intent_engine.handle_transcript("volume 50 percent kardo")
    fast_path_total_ms = (time.perf_counter() - start_time) * 1000
    avg_fast_path_ms = fast_path_total_ms / 100

    print("\n--- PIXEL Phase 4 Agent Runtime Performance Benchmarks ---")
    print(f"Average Policy Gate Evaluation Latency: {avg_policy_ms:.3f} ms")
    print(f"Average Checkpoint Save & Restore Latency: {avg_cp_ms:.3f} ms")
    print(f"Average End-to-End Agent Task Latency: {avg_agent_exec_ms:.3f} ms")
    print(f"Average Deterministic Fast Path Latency: {avg_fast_path_ms:.3f} ms")

    # SLA Assertions
    assert avg_policy_ms < 10.0       # < 10ms
    assert avg_cp_ms < 50.0          # < 50ms
    assert avg_agent_exec_ms < 100.0  # < 100ms
    assert avg_fast_path_ms < 1.0     # < 1.0ms (Preserved sub-millisecond fast-path)
