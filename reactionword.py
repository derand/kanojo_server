#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.1'
__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import json
import random

class ReactionwordManager(object):
    """docstring for ReactionwordManager"""
    def __init__(self, reactionword_file='reactionword.json'):
        tmp = json.load(open(reactionword_file))
        self._items = tmp.get('reactionword')

    def reactionword_json(self, a, pod):
        itms = filter(lambda x: a in x.get('a') and (not x.has_key('pod') or pod in x.get('pod')), self._items)
        if len(itms):
            itm = itms[random.randrange(len(itms))]
            return json.dumps(itm.get('data'))
        else:
            return json.dumps(["…",])
