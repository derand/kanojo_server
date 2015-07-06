#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import time
from cgi import escape
import copy

CLEAR_NONE = 0
CLEAR_SELF = 1

FILL_TYPE_PLAIN = 0
FILL_TYPE_HTML = 1

# after add new activity type add them to ALL_ACTIVITIES list
#    and fix "user_activity" and "all_activities" if need
ACTIVITY_SCAN = 1                           #   "Nightmare has scanned on 2014/10/04 05:31:50.\n"
ACTIVITY_GENERATED = 2                      # + "Violet was generated from 星光産業 ."
ACTIVITY_ME_ADD_FRIEND = 5                  # + "Filter added 葵 to friend list."
ACTIVITY_APPROACH_KANOJO = 7                # + "KH approached めりい."
ACTIVITY_ME_STOLE_KANOJO = 8                # + "Devourer stole うる from Nobody."
ACTIVITY_MY_KANOJO_STOLEN = 9               # + "ふみえ was stolen by Nobody."
ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS = 10    # + "呪いのBlu-ray added ぽいと to friend list."
ACTIVITY_BECOME_NEW_LEVEL = 11              # + "Everyone became Lev.\"99\"."
ACTIVITY_MARRIED = 15                       #   "Devourer get married with うる."
# user defined
# can change "activity_type" in "clear" function to show in client
ACTIVITY_JOINED = 101                       # +
ACTIVITY_BREAKUP = 102                      # +

ALL_ACTIVITIES = (ACTIVITY_SCAN, ACTIVITY_GENERATED, ACTIVITY_ME_ADD_FRIEND, ACTIVITY_APPROACH_KANOJO, ACTIVITY_ME_STOLE_KANOJO, ACTIVITY_MY_KANOJO_STOLEN, ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS, ACTIVITY_BECOME_NEW_LEVEL, ACTIVITY_MARRIED, ACTIVITY_JOINED, ACTIVITY_BREAKUP)

class ActivityManager(object):
    """docstring for ActivityManager"""
    def __init__(self, db=None):
        super(ActivityManager, self).__init__()
        self._db = db
        self.last_aid = 1
        if self._db and self._db.seqs.find_one({ 'colection': 'activities' }) is None:
            self._db.seqs.insert({
                    'colection': 'activities',
                    'id': 0
                })

    def create(self, activity_info):
        '''
                {
                    'kanojo': null,
                    'scanned': null,
                    'user': null,
                    'other_user': null,
                    'activity': 'human readeble string',
                    'created_timestamp': 0,
                    'id': 0,
                    'activity_type': 0
                }
        '''
        activity_required_fields = ['activity_type', ]
        for key in activity_required_fields:
            if not activity_info.has_key(key):
                print 'Error: "%s" key not found in activity'%key
                return None

        if self._db:
            aid = self._db.seqs.find_and_modify(
                    query = {'colection': 'activities'},
                    update = {'$inc': {'id': 1}},
                    fields = {'id': 1, '_id': 0},
                    new = True 
                )
            aid = aid.get('id', -1) if aid else -2
        else:
            aid = self.last_aid
            self.last_aid += 1

        activity = { key: activity_info[key] for key in activity_required_fields }

        activity['id'] = aid
        activity['created_timestamp'] = int(time.time())
        if activity_info.has_key('user'):
            if isinstance(activity_info.get('user'), dict):
                activity['user'] = activity_info.get('user').get('id')
            else:
                activity['user'] = activity_info.get('user')
        if activity_info.has_key('other_user'):
            if isinstance(activity_info.get('other_user'), dict):
                activity['other_user'] = activity_info.get('other_user').get('id')
            else:
                activity['other_user'] = activity_info.get('other_user')

        if activity_info.has_key('kanojo'):
            if isinstance(activity_info.get('kanojo'), dict):
                activity['kanojo'] = activity_info.get('kanojo').get('id')
            else:
                activity['kanojo'] = activity_info.get('kanojo')

        if activity_info.has_key('scanned'):
            activity['scanned'] = activity_info.get('scanned')

        if activity_info.has_key('activity'):
            activity['activity'] = activity_info.get('activity')

        if self._db:
            try:
                self._db.activity.insert(activity)
                self.last_aid = aid
            except pymongo.errors.DuplicateKeyError as e:
                return self.create(activity_info)
        return activity

    def clear(self, activity, clear=CLEAR_SELF, user_id=None):
        if activity is None:
            # TODO: maybe should return somthing else?
            return activity
        if activity == CLEAR_NONE:
            return activity

        allow_keys = ('kanojo', 'scanned', 'user', 'other_user', 'activity', 'created_timestamp', 'id', 'activity_type', )
        rv = { key: activity[key] for key in allow_keys if activity.has_key(key) }

        if user_id and rv.get('activity_type') == ACTIVITY_ME_STOLE_KANOJO and rv.get('other_user') == user_id:
            rv['activity_type'] = ACTIVITY_MY_KANOJO_STOLEN

        if user_id and rv.get('activity_type') == ACTIVITY_ME_ADD_FRIEND and rv.get('other_user') == user_id:
            rv['activity_type'] = ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS
            #(rv['user'], rv['other_user']) = (rv.get('other_user'), rv.get('user'))

        # exchenge user and other_user
        if rv.get('activity_type') in [ACTIVITY_APPROACH_KANOJO, ACTIVITY_MY_KANOJO_STOLEN, ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS]:
            (rv['user'], rv['other_user']) = (rv.get('other_user'), rv.get('user'))


        if not rv.has_key('activity'):
            at = rv.get('activity_type')
            if ACTIVITY_SCAN == at:
                human_time = time.strftime("%d %b %Y %H:%M:%S", time.localtime(rv.get(created_timestamp)))
                rv['activity'] = '{user_name} has scanned on ' + human_time+ '.'
            elif ACTIVITY_GENERATED == at:
                rv['activity'] = '{kanojo_name} was generated.'
            elif ACTIVITY_ME_ADD_FRIEND == at:
                rv['activity'] = '{user_name} added {kanojo_name} to friend list.'
            elif ACTIVITY_APPROACH_KANOJO == at:
                rv['activity'] = '{other_user_name} approached {kanojo_name}.'
            elif ACTIVITY_ME_STOLE_KANOJO == at:
                rv['activity'] = '{user_name} stole {kanojo_name} from {other_user_name}.'
            elif ACTIVITY_MY_KANOJO_STOLEN == at:
                rv['activity'] = '{kanojo_name} was stolen by {other_user_name}.'
            elif ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS == at:
                rv['activity'] = '{other_user_name} added {kanojo_name} to friend list.'
            elif ACTIVITY_BECOME_NEW_LEVEL == at:
                rv['activity'] = '{user_name} became Lev.\"{user_level}\".'
            elif ACTIVITY_MARRIED == at:
                rv['activity'] = '{user_name} get married with {kanojo_name}.'
            elif ACTIVITY_JOINED == at:
                rv['activity'] = '{user_name} has joined.'
            elif ACTIVITY_BREAKUP == at:
                rv['activity'] = '{user_name} break up with {kanojo_name}.'
                rv['activity_type'] = ACTIVITY_ME_ADD_FRIEND
                rv['activity_type2'] = ACTIVITY_BREAKUP
        return rv

    def user_activity(self, user_id, skip=0, limit=6):
        rv = []
        if self._db:
            activity_types = copy.copy(list(ALL_ACTIVITIES))
            activity_types.remove(ACTIVITY_APPROACH_KANOJO)
            activity_types.remove(ACTIVITY_JOINED)
            query = {
                '$or': [
                    {
                        'user': user_id,
                        'activity_type': { '$in': activity_types },
                    },
                    {
                        'other_user': user_id,
                        'activity_type': { '$in': [ACTIVITY_APPROACH_KANOJO, ACTIVITY_ME_STOLE_KANOJO, ACTIVITY_ME_ADD_FRIEND] },
                    }
                ],
            }
            if limit > -1:
                iterator = self._db.activity.find(query).sort([('created_timestamp', -1), ('id', -1), ]).skip(skip).limit(limit)
            else:
                iterator = self._db.activity.find(query).sort([('created_timestamp', -1), ('id', -1), ]).skip(skip)
            for a in iterator:
                rv.append(self.clear(a, clear=CLEAR_SELF, user_id=user_id))
        return rv

    def all_activities(self, skip=0, limit=20, since_id=0):
        rv = []
        if self._db:
            activity_types = copy.copy(list(ALL_ACTIVITIES))
            activity_types.remove(ACTIVITY_APPROACH_KANOJO)
            activity_types.remove(ACTIVITY_SCAN)
            query = {
                'activity_type': { '$in': activity_types },
            }
            if since_id > 0:
                query['id'] = { '$gt': since_id }
            if limit > -1:
                iterator = self._db.activity.find(query).sort([('created_timestamp', -1), ('id', -1), ]).skip(skip).limit(limit)
            else:
                iterator = self._db.activity.find(query).sort([('created_timestamp', -1), ('id', -1), ]).skip(skip)
            for a in iterator:
                rv.append(self.clear(a, clear=CLEAR_SELF))
        return rv

    def kanojo_ids(self, activities):
        rv = map(lambda el: el.get('kanojo'), filter(lambda a: a.get('kanojo'), activities))
        return list(set(rv))

    def user_ids(self, activities):
        rv = map(lambda el: el.get('user'), filter(lambda a: a.get('user'), activities))
        rv.extend(map(lambda el: el.get('other_user'), filter(lambda a: a.get('other_user'), activities)))
        return list(set(rv))

    def fill_format_activities(self, activities, fill_type=FILL_TYPE_PLAIN):
        rv = []
        for a in activities:
            f = {}
            if a.get('kanojo'):
                if FILL_TYPE_PLAIN == fill_type:
                    f['kanojo_name'] = a['kanojo'].get('name').encode('utf-8')
                elif FILL_TYPE_HTML == fill_type:
                    a['kanojo_url'] = '/kanojo/%d.html'%a['kanojo'].get('id')
                    if a['kanojo'].get('id'):
                        f['kanojo_name'] = '<a href="%s">%s</a>'%(a['kanojo_url'], escape(a['kanojo'].get('name').encode('utf-8')))
                    else:
                        f['kanojo_name'] = '%s'%escape(a['kanojo'].get('name').encode('utf-8'))
            if a.get('user'):
                if FILL_TYPE_PLAIN == fill_type:
                    f['user_name'] = a['user'].get('name').encode('utf-8')
                elif FILL_TYPE_HTML == fill_type:
                    a['user_url'] = '/user/%d.html'%a['user'].get('id')
                    if a['user'].get('id'):
                        f['user_name'] =  '<a href="%s">%s</a>'%(a['user_url'], escape(a['user'].get('name').encode('utf-8')))
                    else:
                        f['user_name'] =  '%s'%escape(a['user'].get('name').encode('utf-8'))
                f['user_level'] = a['user'].get('level')
            if a.get('other_user'):
                if FILL_TYPE_PLAIN == fill_type:
                    f['other_user_name'] = a['other_user'].get('name').encode('utf-8')
                elif FILL_TYPE_HTML == fill_type:
                    a['other_user_url'] = '/user/%d.html'%a['other_user'].get('id')
                    if a['other_user'].get('id'):
                        f['other_user_name'] =  '<a href="%s">%s</a>'%(a['other_user_url'], escape(a['other_user'].get('name').encode('utf-8')))
                    else:
                        f['other_user_name'] = '%s'%escape(a['other_user'].get('name').encode('utf-8'))
                f['other_user_level'] = a['other_user'].get('level')
            try:
                a['activity'] = a['activity'].format(**f)
            except KeyError, err:
                print 'Error in activity format(KeyError): ', err, a
                continue
            rv.append(a)
        return rv

    def fill_activities(self, activities, users, kanojos, def_user, def_kanojo, fill_type=FILL_TYPE_PLAIN):
        for a in activities:
            if a.has_key('kanojo'):
                kanojo = next((k for k in kanojos if k.get('id') == a.get('kanojo')), None)
                a['kanojo'] = kanojo if kanojo else def_kanojo
            if a.has_key('user'):
                user = next((u for u in users if u.get('id') == a.get('user')), None)
                a['user'] = user if user else def_user
            if a.has_key('other_user'):
                other_user = next((u for u in users if u.get('id') == a.get('other_user')), None)
                a['other_user'] = other_user if other_user else def_user
        activities = self.fill_format_activities(activities, fill_type=fill_type)
        return activities



if __name__ == "__main__":

    from pymongo import MongoClient
    import config

    mdb_connection_string = config.MDB_CONNECTION_STRING    
    db_name = mdb_connection_string.split('/')[-1]
    db = MongoClient(mdb_connection_string)[db_name]

    a = ActivityManager(db)
    #a = ActivityManager()

    '''
    print a.create({
            'activity_type': ACTIVITY_GENERATED,
            'user': 1,
            'kanojo': 1
        })
    '''
    '''
    print a.create({
            'activity_type': ACTIVITY_APPROACH_MY_KANOJO,
            'user': 2,
            'other_user': 1,
            'kanojo': 1
        })
    '''
    print a.user_activity(2)
    tmp = a.all_activities()
    print tmp
    print a.user_ids(tmp)