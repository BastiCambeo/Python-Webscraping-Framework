""" Hooks into django and prints exceptions directly to the console """
__author__ = 'Sebastian Hofstetter'

import logging
import traceback
logger = logging.getLogger(__name__)


class ExceptionMiddleware:
    def process_exception(self, request, exception):
        logger.error(traceback.format_exc())