"""Utility functions for the EMPD admin"""
import os


_remote_actions = []


def remote_action(func, *args, **kwargs):
    if os.getenv('ONHERUKU'):
        return func(*args, **kwargs)
    else:
        _remote_actions.append((func, args, kwargs))
