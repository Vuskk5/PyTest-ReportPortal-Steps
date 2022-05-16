import functools
import inspect
import logging
import re
import typing
from copy import copy
from typing import Literal

from pytest_reportportal.service import PyTestServiceClass, timestamp
from reportportal_client import ReportPortalService

log = logging.getLogger('plugin.step')


class Step:
    pytest_service: PyTestServiceClass = None

    def __init__(self,
                 name,
                 step_exit_status: Literal['PASSED', 'FAILED', 'STOPPED', 'SKIPPED', 'INTERRUPTED', 'CANCELLED', 'INFO', 'WARN'] = 'INFO'):
        self.name = name
        self.step_exit_status = step_exit_status

        if not self.__class__.pytest_service:
            return

        self.nested_step_id = None
        self.cached_log_item_id = self.__class__.pytest_service.log_item_id

    def __enter__(self):
        if not self.__class__.pytest_service:
            log.info(self.name)
            return

        pytest_service: PyTestServiceClass = self.__class__.pytest_service
        rp_service: ReportPortalService = pytest_service.rp

        self.nested_step_id = rp_service.start_test_item(name=self.name,
                                                         start_time=timestamp(),
                                                         item_type='STEP',
                                                         has_stats=False,
                                                         parent_item_id=self.cached_log_item_id)

        pytest_service.log_item_id = self.nested_step_id

    def __exit__(self, type, value, traceback):
        if not self.__class__.pytest_service:
            return

        pytest_service: PyTestServiceClass = self.__class__.pytest_service
        rp_service: ReportPortalService = pytest_service.rp

        rp_service.finish_test_item(item_id=self.nested_step_id,
                                    end_time=timestamp(),
                                    status='FAILED' if type else self.step_exit_status)
        # Post logs
        rp_service.terminate()

        pytest_service.log_item_id = self.cached_log_item_id


ReturnValue = typing.TypeVar('ReturnValue')


def step(name: str) -> typing.Callable[..., ReturnValue]:
    def decorator(fn: typing.Callable[..., ReturnValue]):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            nonlocal name
            step_name = copy(name)

            # Parse names wrapped in curly brackets
            required_parameters = re.findall(r'{(.+?)}', name)
            function_parameters = inspect.signature(fn).parameters
            parameter_names = list(function_parameters.keys())
            kwargs_ = copy(kwargs)

            # Parse positional arguments
            if args:
                for index, argument in enumerate(args):
                    kwargs_[parameter_names[index]] = argument

            # Handle default arguments
            default_arguments = list()

            for parameter in function_parameters.values():
                if parameter.default != inspect._empty:
                    default_arguments.append(parameter.name)

            # Convert defaults to kwargs
            if len(kwargs_) < len(function_parameters):
                for argument in default_arguments:
                    if argument not in kwargs_:
                        kwargs_[argument] = function_parameters[argument].default

            # Parse any sub-attributes
            for parameter in required_parameters:
                if parameter in kwargs_:
                    continue

                if '.' in parameter:
                    hierarchy = parameter.split('.')
                    value = kwargs_[hierarchy[0]]
                    # Evaluate each item until the last attribute
                    for attribute in hierarchy[1:]:
                        try:
                            value = getattr(value, attribute)
                        except AttributeError:
                            log.exception('Internal error')
                            value = 'Internal Error'

                    # Python variable cannot contain dots, replacing them with underscores
                    formatted_parameter = parameter.replace('.', '_')

                    if formatted_parameter in kwargs_:
                        raise ValueError(f'Parameter "{formatted_parameter}" cannot be evaluated, '
                                         f'a similar variable is already defined in the function.')

                    # Replace the variable in the step's name
                    step_name = name.replace(parameter, formatted_parameter)
                    required_parameters[required_parameters.index(parameter)] = formatted_parameter
                    kwargs_[formatted_parameter] = value

            # Remove kwargs which are not in the step's name
            kwargs_ = {key: value for key, value in kwargs_.items() if key in required_parameters}

            with Step(name=step_name.format(**kwargs_)):
                return fn(*args, **kwargs)
        return wrapper
    return decorator
