#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2014-2015'


from pymongo import MongoClient
import config
import time
from datetime import datetime
import pytz
#from user import CLEAR_NONE, CLEAR_SELF, CLEAR_OTHER
import json
import copy
from random import randint
import hashlib
from collections import OrderedDict


CLEAR_NONE = 0
CLEAR_SELF = 1
CLEAR_BARCODE = 3

def kanojo_order_dict_cmp(x, y):
    order = ('status', 'avatar_background_image_url', 'in_room', 'mascot_enabled', 'mouth_type', 'skin_color', 'body_type', 'race_type', 'spot_type', 'birth_day', 'sexual', 'id', 'recognition', 'on_advertising', 'clothes_type', 'brow_type', 'consumption', 'like_rate', 'eye_position', 'source', 'location', 'birth_month', 'follower_count', 'goods_button_visible', 'accessory_type', 'birth_year', 'possession', 'hair_type', 'clothes_color', 'relation_status', 'ear_type', 'brow_position', 'barcode', 'love_gauge', 'profile_image_url', 'voted_like', 'eye_color', 'glasses_type', 'hair_color', 'face_type', 'nationality', 'advertising_product_url', 'geo', 'emotion_status', 'eye_type', 'mouth_position', 'name', 'fringe_type', 'nose_type', 'advertising_banner_url', 'advertising_product_title', )
    x,y = x[0], y[0]
    if x in order and y in order:
        return order.index(x)-order.index(y)
    elif x in order:
        return -1
    elif y in order:
        return 1
    return cmp(x, y)


class KanojoManager(object):
    """docstring for KanojoManager"""
    def __init__(self, db=None, server=None, clothes_magic=51212494783, generate_secret=''):
        super(KanojoManager, self).__init__()
        self.db = db
        self.server = server
        self.clothes_magic = clothes_magic
        self.generate_secret = generate_secret
        tmp = json.loads(open('dress_up_clothes_time.json').read())
        self.dress_up_time1 = filter(lambda el: el.get('dress_up_from')<el.get('dress_up_to'), tmp.get('info'))
        self.dress_up_time2 = filter(lambda el: el.get('dress_up_from')>el.get('dress_up_to'), tmp.get('info'))
        if self.db and self.db.seqs.find_one({ 'colection': 'kanojos' }) is None:
            self.db.seqs.insert({
                    'colection': 'kanojos',
                    'id': 0
                })

    def create(self, barcode_info, kanojo_name, profile_image_url, owner_user=None, profile_full_image_url=None):
        '''

        '''
        barcode_fields = ['barcode',
                'mouth_type', 'body_type', 'race_type', 'spot_type', 'clothes_type', 'brow_type', 'accessory_type', 'hair_type', 'ear_type', 'glasses_type', 'face_type', 'eye_type', 'fringe_type', 'nose_type',
                'skin_color', 'clothes_color', 'eye_color', 'hair_color', 
                'eye_position', 'brow_position', 'mouth_position', 
                'consumption', 'possession', 'recognition', 'sexual', 'flirtable']
        for key in barcode_fields:
            if not barcode_info.has_key(key):
                print 'Error: "%s" key not found'%key
                return None

        kid = self.db.seqs.find_and_modify(
                query = {'colection': 'kanojos'},
                update = {'$inc': {'id': 1}},
                fields = {'id': 1, '_id': 0},
                new = True 
            )
        kid = kid.get('id', -1) if kid else -2

        kanojo = { key: barcode_info[key] for key in barcode_fields }
        kanojo.update({
                'id': kid,
                'profile_image_url': profile_image_url,
                "name": kanojo_name,
                "mascot_enabled": "0",
                "like_rate": 0,
                "love_gauge": 50,
                #"emotion_status": 50,
                "location": "Somewhere",
                "nationality": "Japan",
                "avatar_background_image_url": None,
                "advertising_product_url": None,
                "birthday": int(time.time()),
                #"status": "Born in Nov. 30, 2013 @ Somewhere. Area: Japan. 0 users are following.\nShe has relationship with Nightmare.",
                #"in_room": True,
                #"birth_day": 30,
                #"birth_month": 11,
                #"birth_year": 2013,
                #"on_advertising": None,
                #"source": "\u82a5\u5ddd\u9f8d\u4e4b\u4ecb\u5168\u96c6\u30085\u3009 (\u3061\u304f\u307e\u6587\u5eab)",
                #"follower_count": 0,
                #"goods_button_visible": True,
                #"relation_status": 2,
                #"geo": "35.517161,139.466934",
                #"advertising_banner_url": None,
                #"advertising_product_title": None
                #"voted_like": True,
                "likes": [],

                # defined by me
                "scan_count": 1,
            })
        if owner_user:
            kanojo.update({
                    'owner_user_id': owner_user.get('id'),
                    'followers': [owner_user.get('id'), ],
                })
        else:
            kanojo['owner_user_id'] = 0
            kanojo['followers'] = []
        if profile_full_image_url:
            kanojo['profile_image_full_url'] = profile_full_image_url
        try:
            self.db.kanojos.insert(kanojo)
        except pymongo.errors.DuplicateKeyError as e:
            return self.create(barcode_info, kanojo_name, profile_image_url, owner_user)
        return kanojo

    def bits2int(self, data, bit_start, bit_end):
        last_bits_move = 8-((bit_end) % 8)
        first_bits_move = ((bit_start) % 8)

        rv = data[bit_start/8] & ~(-1 << (8 - first_bits_move))
        for i in range(bit_start/8, bit_end/8):
            rv = rv << 8 | data[i+1]
        rv = rv >> last_bits_move
        return rv

    def generate(self, barcode):
        '''
            Generate kanojo params from barcode
            Return:
                barcode_info 
        '''
        if not barcode or len(barcode)==0:
            return None

        bc = '%s%s%s'%(self.generate_secret[:len(self.generate_secret)/2], barcode, self.generate_secret[len(self.generate_secret)/2:])
        hash_arr = bytearray(hashlib.md5(bc).digest())

        rv = { 'barcode': barcode, 'body_type': 1 }
        order =    [
                'hair_color', 'eye_color', 'skin_color', 'clothes_color',
                'mouth_type', 'race_type', 'spot_type', 'clothes_type', 'brow_type', 'accessory_type', 'hair_type', 'ear_type', 'glasses_type', 'face_type', 'eye_type', 'fringe_type', 'nose_type',
                'eye_position', 'brow_position', 'mouth_position', 
                'consumption', 'possession', 'recognition', 'sexual', 'flirtable'
            ]
        defaults =  {
                'hair_color':    { 'bounds': (1, 24), 'bits': (0, 24), },
                'eye_color':     { 'bounds': (1, 12), 'bits': (16, 40), },
                'skin_color':    { 'bounds': (1, 12), 'bits': (32, 56), },
                'clothes_color': { 'bounds': (1, 6), 'bits': (48, 59), },

                'mouth_type':    { 'bounds': (1, 12), 'bits': (51, 63), },
                'race_type':     { 'bounds': (1, 10), 'bits': (55, 67), },
                'spot_type':     { 'bounds': (1, 7), 'bits': (59, 70), },
                'clothes_type':  { 'bounds': (1, 5), 'bits': (62, 73), },
                'brow_type':     { 'bounds': (1, 12), 'bits': (65, 77), },
                'accessory_type':{ 'bounds': (1, 5), 'bits': (69, 79), },
                'hair_type':     { 'bounds': (1, 26), 'bits': (71, 84), },
                'ear_type':      { 'bounds': (1, 2), 'bits': (76, 77), },
                'glasses_type':  { 'bounds': (1, 2), 'bits': (77, 78), },
                'face_type':     { 'bounds': (1, 6), 'bits': (78, 89), },
                'eye_type':      { 'bounds': (101, 115), 'bits': (81, 92), },
                'fringe_type':   { 'bounds': (1, 22), 'bits': (84, 97), },
                'nose_type':     { 'bounds': (1, 6), 'bits': (89, 100), },

                'eye_position':  { 'bounds': (-10, 10), 'bits': (92, 105), },
                'brow_position': { 'bounds': (-10, 10), 'bits': (97, 110), },
                'mouth_position':{ 'bounds': (-10, 10), 'bits': (102, 115), },

                'consumption':   { 'bounds': (1, 100), 'bits': (107, 123), },
                'possession':    { 'bounds': (1, 100), 'bits': (99, 115), },
                'recognition':   { 'bounds': (1, 100), 'bits': (91, 107), },
                'sexual':        { 'bounds': (1, 100), 'bits': (83, 99), },
                'flirtable':     { 'bounds': (1, 100), 'bits': (75, 91), },
            }
        while len(order) > 0:
            if not defaults.has_key(order[0]):
                return None
            info = defaults[order[0]]
            (_min, _max) = info['bounds']
            bit_start, bit_end = info['bits']
            val = self.bits2int(hash_arr, bit_start, bit_end)
            l = _max - _min + 1
            rv[order[0]] = _min + val % l
            #print '%s: %d(%d), %d-%d(%d) %d-%d'%(order[0], rv[order[0]], val, _min, _max, l, bit_start, bit_end)
            del order[0]
        return rv

    def save(self, kanojo):
        if kanojo and kanojo.has_key('_id') and self.db:
            # check date_info
            date_info = kanojo.get('date_info')
            if date_info and len(date_info) > 0:
                tm = int(time.time())
                date_info = filter(lambda x: x.get('back_time', 0) > tm, date_info)
                if len(date_info):
                    kanojo['date_info'] = date_info
                else:
                    kanojo.pop('date_info', None)

            return self.db.kanojos.save(kanojo)
        return False

    @property
    def default_kanojo(self):
        rv = {"mascot_enabled": "0", "avatar_background_image_url": None, "in_room": True, "mouth_type": 1, "nose_type": 1, "body_type": 1, "race_type": 10, "spot_type": 1, "birth_day": 12, "sexual": 61, "id": 0, "recognition": 11, "on_advertising": None, "clothes_type": 701, "brow_type": 10, "consumption": 17, "like_rate": 1, "eye_position": 0, "source": "", "location": "Somewhere", "birth_month": 10, "follower_count": 1, "goods_button_visible": True, "accessory_type": 1, "birth_year": 2014, "possession": 11, "hair_type": 3, "clothes_color": 3, "relation_status": 2, "ear_type": 1, "brow_position": 0, "barcode": "************", "love_gauge": 50, "voted_like": False, "eye_color": 5, "glasses_type": 1, "hair_color": 23, "face_type": 3, "nationality": "Italy", "advertising_product_url": None, "geo": "0.0000,0.0000", "emotion_status": 50, "eye_type": 101, "mouth_position": 0, "name": 'Unknown', "fringe_type": 22, "skin_color": 2, "advertising_banner_url": None, "status": "Born in  12 Oct 2014 @ Somewhere. Area: Online. 0 users are following.\nShe has no relationship.", "advertising_product_title": None, "profile_image_url": "http://bk-dump.herokuapp.com/images/common/no_kanojo_picture.png", 'profile_image_full_url': "http://bk-dump.herokuapp.com/images/common/no_kanojo_picture_f.png"}
        return rv

    def increment_scan_couner(self, kanojo, update_db_record=False):
        kanojo['scan_count'] = kanojo.get('scan_count', 0) + 1
        self.recalc_like_rate(kanojo)
        if update_db_record:
            self.save(kanojo)

    def recalc_like_rate(self, kanojo):
        kanojo['like_rate'] = len(kanojo.get('likes', [])) * 0.6 + kanojo.get('scan_count', 0) / 30.0

    def set_like(self, kanojo, like_value, user_or_id, update_db_record=False):
        '''
            call this method only from user_manager (need also update user record)
        '''
        uid = user_or_id.get('id') if isinstance(user_or_id, dict) else user_or_id
        changed = False
        likes = kanojo.get('likes', [])
        if like_value:
            if uid not in likes:
                likes.insert(0, uid)
                kanojo['likes'] = likes
                changed = True
        else:
            if uid in likes:
                likes.remove(uid)
                kanojo['likes'] = likes
                changed = True
        if changed:
            self.recalc_like_rate(kanojo)
            if update_db_record:
                self.save(kanojo)
        return changed

    def delete(self, kanojo):
        if kanojo and kanojo.has_key('_id') and self.db:
            _id = kanojo.pop('_id')
            self.db.kanojos_deleted.insert(kanojo)
            #print self.db.kanojos.find_one({ 'id': kanojo.get('id') })
            self.db.kanojos.remove({ '_id': _id })

    def relation_status(self, kanojo, user):
        '''
            1 - don't know this kanojo_name
            2 - my kanojo
            3 - kanojo in my friends 
        '''
        return 2 if kanojo.get('id') in user.get('kanojos') else 3 if kanojo.get('id') in user.get('friends') else 1

    def fill_fields(self, kanojo, self_user=None, owner_user=None):
        kanojo['status'] = 'Born in  %s.\n%d users are following.\n'%(time.strftime('%d %b %Y', time.gmtime(kanojo.get('birthday', 0))), len(kanojo.get('followers', [])))
        if owner_user:
            kanojo['status'] += 'She has relationship with %s.'%owner_user.get('name')
        elif self_user and self_user.get('id') == kanojo.get('owner_user_id'):
           kanojo['status'] += 'She has relationship with %s.'%self_user.get('name')
        else:
            kanojo['status'] += 'She has not in relationship.'

        dt = time.gmtime(kanojo.get('birthday', 0))
        kanojo['birth_day'] = dt.tm_mday
        kanojo['birth_month'] = dt.tm_mon
        kanojo['birth_year'] = dt.tm_year
        kanojo['emotion_status'] = kanojo.get('love_gauge')
        kanojo['on_advertising'] = None
        kanojo['source'] = ''
        kanojo['follower_count'] = len(kanojo.get('followers'))
        kanojo['geo'] = '0.0000,0.0000'
        kanojo['advertising_banner_url'] = None  # TODO: shows when open kanojo ("reactionword" api call format)
        kanojo['advertising_product_title'] = None
        #kanojo['status'] = 'Born in  %s @ %s. Area: %s. %d users are following.\nShe has relationship with '%(time.strftime('%d %b %Y', time.gmtime(kanojo.get('birthday'))), kanojo.get('location'), kanojo.get('nationality'), kanojo.get('follower_count'))
        if self_user is not None:
            kanojo['goods_button_visible'] = self_user.get('id')==kanojo.get('owner_user_id')
            kanojo['voted_like'] = kanojo.get('id') in self_user.get('likes', [])
            kanojo['relation_status'] = self.relation_status(kanojo, self_user)
            #kanojo['status'] += owner_user.get('name') if owner_user else self_user.get('name') if kanojo.get('relation_status') == 2 else 'Nobody'
        else:
            kanojo['goods_button_visible'] = False
            kanojo['voted_like'] = False
            kanojo['relation_status'] = 1
            #kanojo['status'] += 'Nobody'
        kanojo['in_room'] = True
        if not kanojo.get('profile_image_url'):
            kanojo['profile_image_url'] = 'http://bk-dump.herokuapp.com/images/common/no_kanojo_picture.png'
        if not kanojo.get('profile_image_url').startswith('http') and self.server:
            kanojo['profile_image_url'] = self.server + kanojo.get('profile_image_url')
        if not kanojo.get('profile_image_full_url'):
            kanojo['profile_image_full_url'] = 'http://bk-dump.herokuapp.com/images/common/no_kanojo_picture_f.png'
        if not kanojo.get('profile_image_full_url').startswith('http') and self.server:
            kanojo['profile_image_full_url'] = self.server + kanojo.get('profile_image_full_url')

        kanojo['like_rate'] = int(round(kanojo.get('like_rate', 0)))
        if kanojo.get('like_rate') > 5:
            kanojo['like_rate'] = 5
        return kanojo

    def kanojo_date(self, kanojo):
        date_info = kanojo.get('date_info')
        if date_info and len(date_info) > 0:
            tm = int(time.time())
            for d in date_info:
                if d.get('back_time') > tm:
                    return d
        return None

    def kanojo_date_alert(self, kanojo, user=None):
        kanojo_date = self.kanojo_date(kanojo)
        if kanojo_date:
            relation_status = None
            if not kanojo.has_key('relation_status') and user:
                relation_status = self.relation_status(kanojo, user)
            elif kanojo.has_key('relation_status'):
                relation_status = kanojo.get('relation_status')
            if relation_status != 2:
                duration = kanojo_date.get('back_time', 0) - int(time.time())
                d_string = self.duration_to_str(duration)
                return { "body": "She on the trip, comming back %s."%d_string, "title": "" }
        return None
    

    def clear(self, kanojo, self_user=None, clear=CLEAR_SELF, check_clothes=False, owner_user=None):
        if kanojo is None:
            # TODO: maybe should return somthing else?
            return kanojo
        if clear == CLEAR_NONE:
            return kanojo
        allow_keys = ['mouth_type', 'skin_color', 'body_type', 'race_type', 'spot_type', 'sexual', 'recognition', 'clothes_type', 'brow_type', 'consumption', 'eye_position', 'accessory_type', 'possession', 'hair_type', 'clothes_color', 'ear_type', 'brow_position', 'eye_color', 'glasses_type', 'hair_color', 'face_type', 'eye_type', 'mouth_position', 'fringe_type', 'nose_type']
        if clear == CLEAR_BARCODE:
            rv = { key: kanojo[key] for key in allow_keys if kanojo.has_key(key) }
            rv['barcode'] = '************'
            return rv
        # select clothes must call before change kanojo db document
        clothes_type = kanojo.get('clothes_type')
        if check_clothes:
            clothes_type, changed = self.select_clothes(kanojo)
            if changed:
                self.save(kanojo)

        tmp_kanojo = copy.copy(kanojo)
        self.fill_fields(tmp_kanojo, self_user=self_user, owner_user=owner_user)
        if tmp_kanojo.get('relation_status') is not 2:
            tmp_kanojo['barcode'] = '************'

        curr_date = self.kanojo_date(tmp_kanojo)
        if curr_date:
            if tmp_kanojo.get('relation_status') == 2:
                if curr_date.has_key('background_image_url'):
                    tmp_kanojo['avatar_background_image_url'] = curr_date.get('background_image_url')
            else:
                tmp_kanojo['in_room'] = False

        allow_keys.extend(['id', 'profile_image_url', 'name', 'mascot_enabled', 'like_rate', 'love_gauge', 'location', 'nationality', 'avatar_background_image_url', 'advertising_product_url', 'birth_day', 'birth_month', 'birth_year', 'emotion_status', 'on_advertising', 'goods_button_visible', 'follower_count', 'advertising_banner_url', 'advertising_product_title', 'voted_like', 'relation_status', 'status', 'in_room'])
        if tmp_kanojo.get('relation_status') > 1:
            allow_keys.extend(['barcode', 'source', 'geo'])
        rv = { key: tmp_kanojo[key] for key in allow_keys if tmp_kanojo.has_key(key) }
        rv['clothes_type'] = clothes_type
        return OrderedDict(sorted(rv.items(), cmp=kanojo_order_dict_cmp))

    def kanojo(self, kanojo_id, self_user=None, clear=CLEAR_SELF, check_clothes=False):
        query = { 'id': kanojo_id }
        k = self.db.kanojos.find_one(query)
        if k:
            return self.clear(k, self_user=self_user, clear=clear, check_clothes=check_clothes)
        return k

    def kanojos(self, kanojo_ids, self_user=None, clear=CLEAR_SELF):
        query = {
            'id': {
                '$in': kanojo_ids
            }
        }
        arr = []
        for k in self.db.kanojos.find(query):
            arr.append(self.clear(k, self_user=self_user, clear=clear))

        # sort result
        rv = sorted(arr, key=lambda k: kanojo_ids.index(k['id']))
        return rv

    def fill_owners_info(self, kanojos, owner_users, self_user=None):
        rv = []
        for k in kanojos:
            owner_user = next((u for u in owner_users if u.get('id') == k.get('owner_user_id')), None)
            rv.append(self.clear(k, self_user=self_user, owner_user=owner_user, clear=CLEAR_SELF))
        return rv

    def kanojos_owner_users(self, kanojos):
        s = set(map(lambda k: k.get('owner_user_id'), kanojos))
        s.discard(0)
        s.discard(None)
        return list(s)

    def kanojo_by_barcode(self, barcode):
        query = None
        if 'kanojo' == barcode[:6]:
            kid = int(barcode[6:])
            query = { 'id': kid }
            k_info = self.db.saved_kanojos.find_one(query)
            if k_info is None:
                return None
            barcode = k_info.get('barcode')
        elif 'user' == barcode[:4]:
            uid = int(barcode[4:])
            query = { 'owner_user_id': uid }
            barcode = []
            for k_info in self.db.saved_kanojos.find(query):
                barcode.append(k_info.get('barcode'))
            if len(barcode) == 0:
                return None
        if isinstance(barcode, list):
            query = { 'barcode': { "$in": barcode } }
        else:
            query = { 'barcode': barcode }
        rv = []
        for k_info in self.db.kanojos.find(query):
            rv.append(k_info)
        return rv

    def select_clothes(self, kanojo, test_time=None):
        '''
            return - (clothes_type, changed)
        '''
        wardrobe = kanojo.get('wardrobe')
        if wardrobe and len(wardrobe):
            wardrobe_ids = map(lambda el: el.get('id'), wardrobe)
            tm = int(time.time()) if test_time is None else test_time

            # check if wardrobe used now
            if kanojo.has_key('clothes_selected') and tm < kanojo.get('clothes_selected').get('undress_time', 0):
                return (kanojo.get('clothes_selected').get('clothes_type', kanojo.get('clothes_type')), False)

            days_age = (tm - kanojo.get('birthday', 0)) / (24 * 60 * 60)
            tz_string = kanojo.get('timezone', 'Europe/Kiev')
            hour = datetime.fromtimestamp(tm, pytz.timezone(tz_string)).hour

            # search all clothes that can dress in this hour and calc 'weight_full'
            clothes_info = filter(lambda el: el.get('id') in wardrobe_ids and el.get('dress_up_from')<=hour<el.get('dress_up_to'), self.dress_up_time1)
            clothes_info.extend(filter(lambda el: el.get('id') in wardrobe_ids and (hour<el.get('dress_up_to') or hour>=el.get('dress_up_from')), self.dress_up_time2))
            clothes_info = copy.deepcopy(clothes_info)
            #weight_full = reduce(lambda x,y: x+y.get('like_weight'), clothes_info, 3)
            # TODO: do it simple
            weight_full = 3
            for ci in clothes_info:
                w = filter(lambda el: el.get('id')==ci.get('id'), wardrobe)
                like_weight = ci.get('like_weight', 10)
                if len(w):
                    like_weight = int(like_weight * w[0].get('like_weight_mult', 1))
                ci['like_weight_calc'] = like_weight
                weight_full += like_weight

            # select wardrobe and set putoff time
            weight_curr = (self.clothes_magic * days_age) % weight_full
            for ci in clothes_info:
                weight_curr -= ci.get('like_weight_calc')
                if weight_curr <= 0:
                    clothes_selected = {
                        'clothes_type': ci.get('id')
                    }
                    dress_up_hours = (ci.get('dress_up_to') + 24 - hour) % 24
                    #dress_up_hours = min(dress_up_hours, 6)
                    undress_time = int(tm / 3600) * 3600 + dress_up_hours * 3600
                    clothes_selected['undress_time'] = undress_time
                    kanojo['clothes_selected'] = clothes_selected
                    return (clothes_selected.get('clothes_type'), True)
        return (kanojo.get('clothes_type'), False)

    def add_clothes(self, kanojo, clothes_type, like_weight_mult=1, try_on_min=5):
        '''
            clothes_type == store_item['clothes_item_id']
        '''
        wardrobe = kanojo.get('wardrobe', [])
        w = filter(lambda el: el.get('id')==clothes_type, wardrobe)
        if len(w):
            w = w[0]
            w['like_weight_mult'] = w.get('like_weight_mult', 1) + like_weight_mult
        else:
            w = { 'id': clothes_type }
            if like_weight_mult != 1:
                w['like_weight_mult'] = like_weight_mult
            wardrobe.append(w)
        tm = int(time.time())
        w['tm'] = tm
        if try_on_min:
            kanojo['clothes_selected'] = {
                'clothes_type': clothes_type,
                'undress_time': tm + 60*try_on_min,
            }
        kanojo['wardrobe'] = wardrobe
        #self.save(kanojo)
        return w

    def apply_date(self, kanojo, store_item):
        if store_item.has_key('duration_of_date'):
            date_info = kanojo.get('date_info', [])
            curr_tm = int(time.time())
            back_tm = 0
            for d in date_info:
                back_tm = max(d.get('back_time', 0), back_tm)
            date = {
                'item_id': store_item.get('item_id')
            }
            if store_item.has_key('background_image_url'):
                date['background_image_url'] = store_item['background_image_url']
            if back_tm < curr_tm:
                date['back_time'] = curr_tm + store_item.get('duration_of_date')
            else:
                date['back_time'] = back_tm + store_item.get('duration_of_date')
            print back_tm, curr_tm, date['back_time']
            date_info.append(date)
            kanojo['date_info'] = date_info
            return date
        return None


    def action_string_to_freq(self, action_string):
        try:
            actions = map(lambda el: int(el), action_string.split('|'))
        except ValueError, e:
            return False
        freq = {}
        for act in actions:
            if not freq.has_key(act):
                freq[act] = len(filter(lambda el: el==act, actions))
        return freq

    def user_action_price(self, kanojo, action_string):
        freq = self.action_string_to_freq(action_string)
        if not freq:
            return False
        swipe = freq.pop(10, 0)
        shake = freq.pop(11, 0)
        touch_head = freq.pop(12, 0)
        kiss = freq.pop(20, 0)
        breasts = freq.pop(21, 0)
        if kiss == 0 and breasts == 0:
            return {}
        return { 'price_s': 10 }

    def _kanojo_love_increment(self, kanojo, user, love_change, relation_status=None):
        rv = { 
            'code': 200,
            'info': {},
            'love_increment': {
                'alertShow': 0,
                'decrement_love': 0,
                'increase_love': 0,
                #'reaction_word': ''
            }
        }
        if relation_status is None:
            relation_status = self.relation_status(kanojo, user)
        if relation_status == 2:
            kanojo['love_gauge'] += love_change
            rv['love_increment']['increase_love'] = love_change
            if love_change > 0:
                rv['alerts'] = [ { "body": "You increased her love level %d."%love_change, "title": "" } ]
            else:
                rv['alerts'] = [ { "body": "You could not increase her love...", "title": "" } ]
        elif relation_status == 3:
            tm = int(time.time())
            enjoying_time = kanojo.get('enjoying_time', 0)
            if enjoying_time > tm:
                m = (enjoying_time - tm) / 60
                rv['alerts'] = [ { "body": "She is enjoying with someone, coming back about %d mins later."%m, "title": "" } ]
                rv['love_increment']['alertShow'] = 1
                rv['info']['busy'] = True
            else:
                kanojo['love_gauge'] -= love_change
                rv['love_increment']['decrement_love'] = love_change
                if love_change:
                    rv['alerts'] = [ { "body": "Her love level towards her boyfriend reduced %d."%love_change, "title": "" } ]
                    kanojo['enjoying_time'] = tm + 60*60
        if kanojo['love_gauge'] > 100:
            kanojo['love_gauge'] = 100
            rv['alerts'] = [ { "body": "Her love level is already full.", "title": "" } ]
        if kanojo['love_gauge'] < 1 and relation_status==3:
            kanojo['love_gauge'] = 50
            rv['alerts'] = [ { "body": "She become your girlfriend.", "title": "" } ]
            rv['info']['change_owner'] = True
            rv['love_increment']['decrement_love'] = 0
            rv['love_increment']['alertShow'] = 1

        tz_string = kanojo.get('timezone', 'Europe/Kiev')
        hour = datetime.fromtimestamp(time.time(), pytz.timezone(tz_string)).hour
        part_of_day = ((hour + 2) % 24 ) / 6 # 0 - night, 1 - morning, 2 - day, 3 - evening
        rv['info']['pod'] = part_of_day

        return rv


    def user_action(self, kanojo, user, action_string):
        rv = { 'code': 400 }
        if action_string:
            freq = self.action_string_to_freq(action_string)
            if not freq:
                return rv
            swipe = freq.get(10, 0)
            shake = freq.get(11, 0)
            touch_head = freq.get(12, 0)
            kiss = freq.get(20, 0)
            breasts = freq.get(21, 0)

            action_weight = swipe*3 + shake + touch_head*9 + kiss*19 + breasts*15
            if kiss == 0 and breasts == 0:
                action_weight = 0
            if action_weight > 100:
                action_weight = 100

            relation_status = self.relation_status(kanojo, user)
            if relation_status == 2:
                action_weight /= 5
            elif relation_status == 3:
                action_weight /= 20
            else:
                action_weight = 0

            rv = self._kanojo_love_increment(kanojo, user, action_weight, relation_status=relation_status)

            rv['info']['actions'] = action_string
            if kiss == 0 and breasts == 0:
                rv['info']['a'] = max(freq, key=freq.get)
            else:
                pk = action_string.find('20') if kiss > 0 else len(action_string)
                pb = action_string.find('21') if breasts > 0 else len(action_string)
                rv['info']['a'] = 20 if pk < pb else 21
        return rv

    def user_do_gift_calc_kanojo_love_increment(self, kanojo, user, store_item, is_extended=False):
        relation_status = self.relation_status(kanojo, user)
        action_weight = randint(50, 100)
        if relation_status == 2:
            action_weight /= 5
        elif relation_status == 3:
            if is_extended:
                action_weight /= 10
            else:
                action_weight /= 20
        else:
            action_weight = 0
        rv = self._kanojo_love_increment(kanojo, user, action_weight, relation_status=relation_status)
        rv['info']['a'] = 2 if is_extended else 1
        return rv

    def duration_to_str(self, duration):
        if duration < 60:
            return '%d seconds'%duration if duration > 1 else '%d second'%duration
        duration /= 60
        if duration < 60:
            return '%d minutes'%duration if duration > 1 else '%d minute'%duration
        duration /= 60
        if duration < 24:
            return '%d hours'%duration if duration > 1 else '%d hour'%duration
        duration /= 24
        if duration < 7:
            return '%d days'%duration if duration > 1 else '%d day'%duration
        duration /= 7
        return '%d weeks'%duration if duration > 1 else '%d week'%duration

    def user_do_date_calc_kanojo_love_increment(self, kanojo, user, store_item, is_extended=False):
        relation_status = self.relation_status(kanojo, user)
        action_weight = randint(50, 100)
        if relation_status == 2 and store_item.get('duration_of_date'):
            d_string = self.duration_to_str(store_item.get('duration_of_date'))
            rv = {
                'alerts': [ { "body": "Enemies can't approach her for %s."%d_string, "title": "" } ],
                'love_increment': {
                    'decrement_love': 0,
                    'increase_love': 0,
                    'reaction_word': None
                }
            }
            if not is_extended:
                self.apply_date(kanojo, store_item)
            return rv
        elif relation_status == 2:
            action_weight /= 5
        elif relation_status == 3:
            action_weight /= 20
        else:
            action_weight = 0
        rv = self._kanojo_love_increment(kanojo, user, action_weight, relation_status=relation_status)
        rv['info']['a'] = 4 if is_extended else 3
        return rv

    def user_breakup_with_kanojo_alert(self, kanojo):
        rv = {
            'alerts': [ { "body": "You break up with %s."%kanojo.get('name'), "title": "" } ],
            'love_increment': {
                'decrement_love': 0,
                'increase_love': 0,
                'reaction_word': None
            }
        }
        return rv
    


if __name__ == "__main__":
    import config
    km = KanojoManager(generate_secret=config.KANOJO_SECRET)

    print km.generate('123')

    exit()

    mdb_connection_string = config.MDB_CONNECTION_STRING    
    db_name = mdb_connection_string.split('/')[-1]
    db = MongoClient(mdb_connection_string)[db_name]

    #barcode_info = db.kanojos.find_one({ 'id': 368 })
    #barcode_info.pop('_id', None)
    #print json.dumps(barcode_info)

    from user import UserManager
    um = UserManager(db)
    user = um.user(uid=1, clear=CLEAR_NONE)

    import config
    km = KanojoManager(db, generate_secret1=config.KANOJO_SECRET1, generate_secret2=config.KANOJO_SECRET2)
    #kanojo = km.kanojo(368, user, clear=CLEAR_NONE)
    kanojo = km.kanojo(31, user, clear=CLEAR_NONE)
    kanojo.pop('_id', None)
    print json.dumps(kanojo)

    #import pprint
    #pprint.pprint(km.user_action(kanojo, user, '10|11|12|20|21|20|12|11|10'))

    exit()

    for i in range(1417822084, 1417822084+60*60*24*15, 60*60):
        tm = datetime.fromtimestamp(i, pytz.timezone('Europe/Kiev'))
        (clothes_type, changed) = km.select_clothes(kanojo, test_time=i)
        print '%02d %d %d'%(tm.hour, clothes_type, changed)

    kanojo.pop('_id', None)
    print json.dumps(kanojo)
    #print km.create(barcode_info, barcode_info.get('name'), '/profile_images/kanojo/1.png?w=88&h=88&face=true', { 'id': 1 })

