#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.1'
__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import unittest
from activity import ActivityManager

class ActivityTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(ActivityTest, self).__init__(*args, **kwargs)
        self.a = ActivityManager()

    def test_kanojo_and_user_lists(self):
        activities = [
            {
                "_id": {  "$oid": "558fda9245b41c0bebb59e91" },
                "kanojo": 1,
                "user": 1,
                "created_timestamp": 1435490962,
                "id": 1,
                "activity_type": 2
            },
            {
                "_id": { "$oid": "558ff93b45b41c0c89485ebc" },
                "kanojo": 1,
                "user": 2,
                "other_user": 1,
                "created_timestamp": 1435498811,
                "id": 2,
                "activity_type": 7
            },
            {
                "_id": {  "$oid": "55967c00333b97000afc2ab7" },
                "user": 1,
                "activity_type": 7,
                "other_user": 2,
                "created_timestamp": 1435925504,
                "id": 42,
                "kanojo": 855
            }
        ]
        kanojo_ids = self.a.kanojo_ids(activities)
        user_ids = self.a.user_ids(activities)
        kanojo_ids_set = set()
        user_ids_set = set()
        for a in activities:
            if a.has_key('kanojo'):
                kanojo_ids_set.add(a['kanojo'])
            if a.has_key('user'):
                user_ids_set.add(a['user'])
            if a.has_key('other_user'):
                user_ids_set.add(a['other_user'])
        self.assertSequenceEqual(set(kanojo_ids), kanojo_ids_set)
        self.assertSequenceEqual(set(user_ids), user_ids_set)

if __name__ == '__main__':
    unittest.main()(venv)
