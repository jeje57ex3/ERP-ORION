from .celery import app as celery_app

__all__ = ('celery_app',)

# Python 3.14 compatibility: copy(super()) now returns the super proxy instead
# of a copy of the instance. Fix BaseContext.__copy__ to use __new__ instead.
from copy import copy as _copy


def _base_context_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate


from django.template.context import BaseContext
BaseContext.__copy__ = _base_context_copy
