import pytest
from _pytest.main import Session

from step import Step


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: Session):
    pytestconfig = session.config

    # Initialize 'Step' plugin
    if hasattr(pytestconfig, 'py_test_service'):
        Step.pytest_service = pytestconfig.py_test_service
