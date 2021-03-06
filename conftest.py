import pytest

from step import Step


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: pytest.Session):
    pytestconfig = session.config

    # Initialize 'Step' plugin
    if hasattr(pytestconfig, 'py_test_service'):
        Step.pytest_service = getattr(pytestconfig, 'py_test_service')
