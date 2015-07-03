#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2014-2015'


from pymongo import MongoClient
import time
import config
import math
import copy
from activity import ActivityManager, ACTIVITY_SCAN, ACTIVITY_GENERATED, ACTIVITY_ME_ADD_FRIEND, ACTIVITY_APPROACH_KANOJO, ACTIVITY_ME_STOLE_KANOJO, ACTIVITY_MY_KANOJO_STOLEN, ACTIVITY_MY_KANOJO_ADDED_TO_FRIENDS, ACTIVITY_BECOME_NEW_LEVEL, ACTIVITY_MARRIED, ACTIVITY_JOINED
import random

CLEAR_NONE = 0
CLEAR_SELF = 1
CLEAR_OTHER = 2

class UserManager(object):
    """docstring for UserManager"""
    def __init__(self, db=None, server=None, kanojo_manager=None, store=None, activity_manager=None):
        super(UserManager, self).__init__()
        self.db = db
        self.server = server
        self.kanojo_manager = kanojo_manager
        self.store = store
        self.activity_manager = activity_manager
        self.last_uid = 1
        if self.db and self.db.seqs.find_one({ 'colection': 'users' }) is None:
            self.db.seqs.insert({
                    'colection': 'users',
                    'id': 0
                })

    def generate_name(self):
        colors = ('Aqua', 'Aquamarine', 'Azure', 'Beige', 'Bisque', 'Black', 'Blue', 'Brown', 'Burlywood', 'Chartreuse', 'Chocolate', 'Coral', 'Cornflower', 'Cornsilk', 'Crimson', 'Cyan', 'Firebrick', 'Fuchsia', 'Gainsboro', 'Gold', 'Goldenrod', 'Gray', 'Green', 'Honeydew', 'Indigo', 'Ivory', 'Khaki', 'Lavender', 'Lime', 'Linen', 'Magenta', 'Maroon', 'Moccasin', 'Olive', 'Orange', 'Orchid', 'Peru', 'Pink', 'Plum', 'Purple', 'Red', 'Salmon', 'Seashell', 'Sienna', 'Silver', 'Snow', 'Tan', 'Teal', 'Thistle', 'Tomato', 'Turquoise', 'Violet', 'Wheat', 'White', 'Yellow')
        fruits = ('Apple', 'Apricot', 'Avocado', 'Banana', 'Bilberry', 'Blackberry', 'Blackcurrant', 'Blueberry', 'Boysenberry', 'Cantaloupe', 'Currant', 'Cherry', 'Cherimoya', 'Cloudberry', 'Coconut', 'Cranberry', 'Damson', 'Date', 'Dragonfruit', 'Durian', 'Elderberry', 'Feijoa', 'Fig', 'Goji berry', 'Gooseberry', 'Grape', 'Grapefruit', 'Guava', 'Huckleberry', 'Jabouticaba', 'Jackfruit', 'Jambul', 'Jujube', 'Kiwi', 'Kumquat', 'Lemon', 'Lime', 'Loquat', 'Lychee', 'Mango', 'Melon', 'Miracle fruit', 'Mulberry', 'Nectarine', 'Olive', 'Papaya', 'Passionfruit', 'Peach', 'Pear', 'Persimmon', 'Physalis', 'Plum', 'Pineapple', 'Pomegranate', 'Pomelo', 'Quince', 'Raspberry', 'Rambutan', 'Redcurrant', 'Satsuma', 'Strawberry')
        return '%s %s'%(random.choice(colors), random.choice(fruits))

    def create(self, uuid):
        if self.db:
            uid = self.db.seqs.find_and_modify(
                    query = {'colection': 'users'},
                    update = {'$inc': {'id': 1}},
                    fields = {'id': 1, '_id': 0},
                    new = True 
                )
            uid = uid.get('id', -1) if uid else -2
        else:
            uid = self.last_uid
            self.last_uid += 1
        tm = int(time.time())
        user = {
                "create_time": tm,
                "birthday": tm,
                "id": uid,
                "uuid": [uuid],
                #"name": 'id:%d'%uid,
                "name": self.generate_name(),
                "level": 1,
                "money": 1000, 
                "sex": "not sure",
                "stamina": 100,
                "email": None,
                "description": None,
                "generate_count": 0,
                "profile_image_url": None,
                "password": None,
                "tickets": 20,
                "language": "en",
                "scan_count": 0,
                "twitter_connect": False,
                "facebook_connect": False,
                "generate_count": 0,
                "description": None,
                "password": None,
                #"stamina_max": 1080,
                #"relation_status": 2,
                #"birth_day": 27,
                #"birth_month": 7,
                #"birth_year": 2014,
                #"friend_count": 11660,
                #"enemy_count": 4839,
                #"kanojo_count": 351,
                "kanojos": [],
                "friends": [],
                "enemys": [],
                "likes": [],
                # ----
                #"stamina_recover_index": (tm % 86400) / 60
            }
        user['stamina_idx'] = (tm / 60) % (60 * 24)
        if self.db:
            try:
                self.db.users.insert(user)
                self.last_uid = uid
            except pymongo.errors.DuplicateKeyError as e:
                return self.create(uuid)

            if self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_JOINED,
                        'user': user,
                    })
        return user

    def save(self, user):
        if user and user.has_key('_id') and self.db:
            return self.db.users.save(user)
        return False

    @property
    def default_user(self):
        return {"generate_count": 0, "description": "", "language": "ja", "level": 1, "kanojo_count": 0, "money": 100, "birth_month": 10, "stamina_max": 100, "facebook_connect": False, "profile_image_url": None, "sex": "no sure", "stamina": 100, "money_max": 100, "twitter_connect": False, "scan_count": 0, "birth_day": 25, "enemy_count": 0, "wish_count": 0, "id": 0, "name": 'Unknown'}

    def fill_fields(self, usr):
        usr['stamina_max'] = (usr.get('level', 0) + 9) * 10
        dt = time.gmtime(usr.get('birthday', 0))
        usr['birth_day'] = dt.tm_mday
        usr['birth_month'] = dt.tm_mon
        usr['birth_year'] = dt.tm_year
        usr['kanojo_count'] = len(usr.get('kanojos', []))
        usr['friend_count'] = len(usr.get('friends', []))
        usr['enemy_count'] = len(usr.get('enemys', []))
        if not usr.get('profile_image_url'):
            usr['profile_image_url'] = 'http://bk-dump.herokuapp.com/images/common/no_pictire_available.png'
        return usr

    def clear(self, usr, clear, self_uid=None, self_user=None):
        if usr is None:
            # TODO: maybe should return somthing else?
            return usr
        if clear == CLEAR_NONE:
            return usr
        else:
            self.fill_fields(usr)
            allow_keys = ['id', 'name', 'level', 'money', 'sex', 'stamina', 'profile_image_url', 'scan_count', 'stamina_max', 'relation_status', 'kanojo_count', 'friend_count', 'enemy_count', 'generate_count']
            if clear == CLEAR_SELF:
                allow_keys.extend(['email', 'tickets', 'language', 'twitter_connect', 'facebook_connect', 'birth_day', 'birth_month', 'birth_year', 'description'])
                if self_uid is None:
                    self_uid = usr.get('id')
            rv = { key: usr[key] for key in allow_keys if usr.has_key(key) }
            if self_uid:
                if self_uid == usr.get('id'):
                    rv['relation_status'] = 2
                else:
                    self_user = self.user(uid=self_uid, clear=CLEAR_NONE)
            if self_user:
                rv['relation_status'] = 2 if self_user.get('id')==usr.get('id') else 3 if usr.get('id') in self_user.get('enemys') else 1
            return rv

    def user(self, uuid=None, uid=None, self_uid=None, self_user=None, clear=CLEAR_SELF):
        query = None
        if uid:
            query = { "id": uid }
        elif uuid:
            query = {
                    "uuid": {
                        "$exists": True,
                        "$elemMatch": { "$in": [ uuid  ] }
                    }        
                }
        else:
            return None
        if not self.db:
            return None
        usr = self.db.users.find_one(query)
        return self.clear(usr, clear=clear, self_uid=self_uid, self_user=self_user)

    def users(self, ids, self_uid=None, self_user=None):
        tmp_ids = list(ids)
        if self_user is None and self_uid is not None and self_uid not in ids:
            tmp_ids.append(self_uid)
        query = { "id": { '$in': tmp_ids } }
        rv = []
        for u in self.db.users.find(query):
            rv.append(u)
            if self_user is None and self_uid is not None and u.get('id') == self_uid:
                self_user = copy.copy(u)
        rv = map(lambda u: self.clear(u, clear=CLEAR_OTHER, self_user=self_user), rv)
        return rv


    def add_kanojo_as_friend(self, user, kanojo, increment_scan_couner=True, update_db_record=True):
        uid = user.get('id')
        if uid not in kanojo.get('followers'):
            kanojo['followers'].append(uid)
            if update_db_record:
                self.kanojo_manager.save(kanojo)
        if kanojo.get('id') not in user.get('friends'):
            #user['friends'].append(kanojo['id'])
            user['friends'].insert(0, kanojo.get('id'))
            self.user_change(user, stamina_change=5, money_change=-25, update_db_record=False)
            if increment_scan_couner:
                self.increment_scan_couner(user, update_db_record=False)
            if update_db_record:
                self.save(user)
            if self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_ME_ADD_FRIEND,
                        'user': user,
                        'kanojo': kanojo,
                        'other_user': kanojo.get('owner_user_id')
                    })

    def create_kanojo_from_barcode(self, user, barcode_info, kanojo_name, crop_url, full_url=None):
        if user.get('stamina') < 20:
            return False
        kanojo = self.kanojo_manager.create(barcode_info, kanojo_name, crop_url, user, profile_full_image_url=full_url)
        if kanojo:
            k = user.get('kanojos', [])
            #k.append(kanojo.get('id'))
            k.insert(0, kanojo.get('id'))
            user['kanojos'] = k
            self.increment_scan_couner(user)
            self.user_change(user, stamina_change=20, money_change=-100, update_db_record=True)

            if self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_GENERATED,
                        'user': user,
                        'kanojo': kanojo,
                    })
        return kanojo

    # x = lambda y: int(math.floor((2*math.sqrt(3)*math.sqrt(5*y+3888)-216)/5+1))
    # y = FLOOR(A3*(7.2+A3/12))
    # x - level, y - scan count 
    def increment_scan_couner(self, user, inc_value=1, update_db_record=False):
        user['scan_count'] = user.get('scan_count', 0) + inc_value
        lvl = int(math.floor((2*math.sqrt(3)*math.sqrt(5*user['scan_count']+3888)-216)/5+1))
        if user.get('level') < lvl:
            lvl_diff = lvl - user.get('level', 0)
            user['level'] = lvl
            self.user_change(user, money_change=-lvl_diff*1000, update_db_record=False)

            if self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_BECOME_NEW_LEVEL,
                        'user': user,
                        'activity': '{user_name} became Lev.\"' + str(lvl) + '\".'
                    })
        if update_db_record:
            self.save(user)

    def user_items(self, user):
        return user.get('has_items', [])

    def add_store_item(self, user, store_item):
        '''
            only add store item to user dict (tickets not changed)
        '''
        units = store_item.get('buy_units', 1)
        store_item_id = store_item.get('base_store_item_id', store_item.get('item_id'))
        has_items = user.get('has_items', [])
        _itm = filter(lambda el: el.get('store_item_id')==store_item_id, has_items)
        if len(_itm):
            _itm = _itm[0]
            _itm['units'] = _itm.get('units', 1) + units
        else:
            _itm = { 
                'store_item_id': store_item.get('base_store_item_id', store_item.get('item_id'))
            }
            if units != 1:
                _itm['units'] = units
            has_items.append(_itm)
        user['has_items'] = has_items
        self.save(user)
        return _itm

    def give_present(self, user, kanojo, store_item_id):
        has_item = filter(lambda x: x.get('store_item_id')==store_item_id, user.get('has_items', []))
        if len(has_item) and has_item[0].get('units', 1) >= 1:
            has_item = has_item[0]
            rv = { 'code': 200 }
            store_item = self.store.get_item(store_item_id)

            relation_status = self.kanojo_manager.relation_status(kanojo, user)
            if store_item.has_key('clothes_item_id'):
                weight_mult = 1 if relation_status==2 else 0.35
                self.kanojo_manager.add_clothes(kanojo, clothes_type=store_item.get('clothes_item_id'), like_weight_mult=weight_mult)

                action_dict = self.kanojo_manager.user_do_gift_calc_kanojo_love_increment(kanojo, user, store_item, is_extended=True)
                self.check_approached_kanojo(user, kanojo, action_dict.get('info', {}))
                rv.update(action_dict)

            if store_item.has_key('action'):
                if store_item.get('action') == 'dump_kanojo':
                    rv.update(self.kanojo_manager.user_breakup_with_kanojo_alert(kanojo))
                    self.breakup_with_kanojo(user, kanojo)
                    kanojo = None


            if not rv.get('info', {}).get('busy'):
                if has_item.get('units', 1)==1:
                    user['has_items'].remove(has_item)
                else:
                    has_item['units'] -= 1
                self.kanojo_manager.save(kanojo)
                self.save(user)
        else:
            rv = {
                "code": 404,
                "alerts": [ { "body": "The Requested Item was not found.", "title": "" } ]
            }
        return rv

    def do_date(self, user, kanojo, store_item_id):
        has_item = filter(lambda x: x.get('store_item_id')==store_item_id, user.get('has_items', []))
        if len(has_item) and has_item[0].get('units', 1) >= 1:
            has_item = has_item[0]
            rv = { 'code': 200 }
            store_item = self.store.get_date(store_item_id)

            action_dict = self.kanojo_manager.user_do_date_calc_kanojo_love_increment(kanojo, user, store_item, is_extended=True)
            self.kanojo_manager.apply_date(kanojo, store_item)

            self.check_approached_kanojo(user, kanojo, action_dict.get('info', {}))

            rv.update(action_dict)

            if not rv.get('info', {}).get('busy'):
                if has_item.get('units', 1)==1:
                    user['has_items'].remove(has_item)
                else:
                    has_item['units'] -= 1
                self.kanojo_manager.save(kanojo)
                self.save(user)
        else:
            rv = {
                "code": 404,
                "alerts": [ { "body": "The Requested Item was not found.", "title": "" } ]
            }
        return rv

    def user_change(self, user, stamina_change=0, money_change=0, tickets_change=0, up_stamina=False, update_db_record=True):
        '''
            change user stamina/money/tickets
        '''
        if stamina_change:
            if user.get('stamina', 0) < stamina_change:
                return False
            user['stamina'] = user.get('stamina', 0) - stamina_change
        if money_change:
            if user.get('money', 0) < money_change:
                return False
            user['money'] = user.get('money', 0) - money_change
        if tickets_change:
            if user.get('tickets', 0) < tickets_change:
                return False
            user['tickets'] = user.get('tickets', 0) - tickets_change
        if up_stamina:
            stamina_max = (user.get('level', 0) + 9) * 10
            if user.get('stamina', 0) == stamina_max:
                return False
            user['stamina'] = stamina_max
        if update_db_record:
            self.save(user)
        return user

    def check_approached_kanojo(self, user, kanojo, kanojo_love_increment_info, current_owner=None):
        if kanojo is None:
            return None
        # if user stole kanojo
        if user.get('id') != kanojo.get('owner_user_id'):
            #print user, kanojo, kanojo_love_increment_info
            if not kanojo_love_increment_info.get('busy') and self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_APPROACH_KANOJO,
                        'user': user,
                        'kanojo': kanojo,
                        'other_user': kanojo.get('owner_user_id')
                    })
        if kanojo_love_increment_info.get('change_owner'):
            if not current_owner:
                owner_id = kanojo.get('owner_user_id')
                if owner_id > 0:
                    current_owner = self.user(uid=owner_id, clear=CLEAR_NONE)
            if current_owner:
                try:
                    current_owner['kanojos'].remove(kanojo.get('id'))
                    kanojo['followers'].remove(current_owner.get('id'))
                except ValueError, e:
                    pass
                self.save(current_owner)
            try:
                user['friends'].remove(kanojo.get('id'))
            except Exception, e:
                pass
            kanojo['owner_user_id'] = user.get('id')
            user['kanojos'].append(kanojo.get('id'))

            if self.activity_manager:
                self.activity_manager.create({
                        'activity_type': ACTIVITY_ME_STOLE_KANOJO,
                        'user': user,
                        'kanojo': kanojo,
                        'other_user': current_owner
                    })
        return kanojo_love_increment_info.get('change_owner')

    def user_action(self, user, kanojo, action_string=None, do_gift=None, do_date=None, is_extended_action=False, current_owner=None):
        '''
            is_extended_action - for extended gifts and dates
        '''
        if not self.kanojo_manager:
            return { "code": 500, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "Server error.", "title": "" } ] }

        # check if user can use this action
        store_item = None
        if action_string:
            price = self.kanojo_manager.user_action_price(kanojo, action_string)
            #if not price:
            #    return False
        elif do_gift:
            store_item = self.store.get_item(do_gift)
            price = store_item
        elif do_date:
            store_item = self.store.get_date(do_date)
            price = store_item
        else:
            return { "code": 500, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "Server error.", "title": "" } ] }
        if user.get('stamina') < price.get('price_s', 0):
            return { "code": 403, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "You don't have enough stamina.", "title": "" } ] }
        if user.get('money') < price.get('price_b', 0):
            return { "code": 403, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "You don't have enough money.", "title": "" } ] }
        if user.get('tickets') < price.get('price_t', 0):
            return { "code": 403, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "You don't have enough tickets.", "title": "" } ] }
        if user.get('level') < price.get('level', 0):
            return { "code": 403, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "You level to low.", "title": "" } ] }

        # do action
        rv = { 'code': 200 }
        if action_string:
            action_dict = self.kanojo_manager.user_action(kanojo, user, action_string)
            rv.update(action_dict)
        elif do_gift:
            if is_extended_action:
                action_dict = self.add_store_item(user, store_item)
                if action_dict:
                    if store_item.get('buy_units', 1) == 1:
                        body_str = "%s was added to your item list."%store_item.get('title')
                    else:
                        body_str = "%s (x%d) was added to your item list."%(store_item.get('title'), store_item.get('buy_units'))
                    action_dict = {
                        "data": True,
                        "alerts": [
                            {
                                "body": body_str,
                                "title": ""
                            }
                        ]
                    }
                else:
                    action_dict = { 'data': False, 'code': 404 }
                rv.update(action_dict)
            else:
                action_dict = self.kanojo_manager.user_do_gift_calc_kanojo_love_increment(kanojo, user, store_item, is_extended=is_extended_action)
                rv.update(action_dict)
        elif do_date:
            if is_extended_action:
                action_dict = self.add_store_item(user, store_item)
                if action_dict:
                    if store_item.get('buy_units', 1) == 1:
                        body_str = "%s was added to your item list."%store_item.get('title')
                    else:
                        body_str = "%s (x%d) was added to your item list."%(store_item.get('title'), store_item.get('buy_units'))
                    action_dict = {
                        "data": True,
                        "alerts": [
                            {
                                "body": body_str,
                                "title": ""
                            }
                        ]
                    }
                else:
                    action_dict = { 'data': False, 'code': 404 }
                rv.update(action_dict)
            else:
                action_dict = self.kanojo_manager.user_do_date_calc_kanojo_love_increment(kanojo, user, store_item, is_extended=is_extended_action)
                rv.update(action_dict)

        self.check_approached_kanojo(user, kanojo, rv.get('info', {}), current_owner=current_owner)

        self.kanojo_manager.save(kanojo)
        if not rv.get('info', {}).get('busy'):
            self.user_change(user, stamina_change=price.get('price_s', 0), money_change=price.get('price_b', 0), tickets_change=price.get('price_t', 0), update_db_record=True)
        return rv

    def breakup_with_kanojo(self, user, kanojo, update_db_record=True):
        kid = kanojo.get('id')
        uid = user.get('id')
        if kid in user.get('kanojos', []):
            user['kanojos'].remove(kid)
        if kid in user.get('friends', []):
            user['friends'].remove(kid)
        if uid in kanojo.get('followers', []):
            kanojo['followers'].remove(uid)
        if update_db_record:
            #self.kanojo_manager.save(kanojo)
            self.kanojo_manager.delete(kanojo)
            self.save(user)



if __name__ == "__main__":
    mdb_connection_string = config.MDB_CONNECTION_STRING    
    db_name = mdb_connection_string.split('/')[-1]
    db = MongoClient(mdb_connection_string)[db_name]

    u = UserManager(db)
    print u.generate_name()
    #u.create('~')

    import json
    '''
    user = u.user(uid=1, clear=CLEAR_NONE)
    user.pop('_id', None)
    print json.dumps(user)
    '''
    print json.dumps(u.users([1,2], self_uid=1))



