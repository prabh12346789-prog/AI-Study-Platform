import inspect

from src.services.orchestrator.service import AIOrchestrator


def test_orchestrator_process_is_async():
    assert inspect.iscoroutinefunction(AIOrchestrator.process)
