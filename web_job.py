#!/usr/bin/env python
# -*- coding: utf-8 -*-


__version__ = '0.1'
__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2014-2015'


import os
import os.path
from functools import wraps
from flask import Flask, Response, json, request, stream_with_context, redirect, render_template, abort, send_file, send_from_directory
from flask import session
import json
import time, datetime
import re
import urllib
from pymongo import MongoClient
from datetime import timedelta
from user import *
from kanojo import *
from images import ImageManager
import config
from flask_api.decorators import set_parsers
from bkmultipartparser import BKMultipartParser
from thread_post import Post
from hashlib import sha224
from cgi import escape
from geo_ip import GeoIP, GEOIP_CACHE_ONLY, GEOIP_WEB_SERVICE
from store import StoreManager, KANOJO_OWNER, KANOJO_FRIEND, KANOJO_OTHER
from reactionword import ReactionwordManager
from random import randint

from OpenSSL import SSL
context = SSL.Context(SSL.SSLv23_METHOD)
context.use_privatekey_file(config.SSL_PRIVATEKEY_FILE)
context.use_certificate_file(config.SSL_CERTIFICATE_FILE)

app = Flask(__name__)
app.debug = False
app.secret_key = config.SESSION_SECRET_KEY
#app.config['SESSION_COOKIE_DOMAIN'] = '192.168.1.19'
#session.permanent = True
#app.permanent_session_lifetime = timedelta(minutes=5)
#app.config['DEFAULT_PARSERS'] = []

mdb_connection_string = config.MDB_CONNECTION_STRING_REAL
db_name = mdb_connection_string.split('/')[-1]
db2 = MongoClient(mdb_connection_string)[db_name]

mdb_connection_string = config.MDB_CONNECTION_STRING
db_name = mdb_connection_string.split('/')[-1]
db = MongoClient(mdb_connection_string)[db_name]

kanojo_manager = KanojoManager(db,
					server=app.config['SERVER_NAME'],
					clothes_magic=config.CLOTHES_MAGIC,
					generate_secret=config.KANOJO_SECRET
				)
store = StoreManager()
user_manager = UserManager(db, server=app.config['SERVER_NAME'], kanojo_manager=kanojo_manager, store=store)
image_manager = ImageManager()
geoIP = GeoIP(db, secret1=config.GEOIP_SECRET1, secret2=config.GEOIP_SECRET2, secret3=config.GEOIP_SECRET3)
reactionword = ReactionwordManager()


def json_response(data):
	rtext = json.dumps(data)
	if request.method == 'POST':
		if request.form.get('callback', False):
			rtext = '%s(%s);'%(request.form.get('callback', ''), rtext)
	else:
		if request.args.get('callback', False):
			rtext = '%s(%s);'%(request.args.get('callback', ''), rtext)
	return Response(rtext, status=200, mimetype='application/json')

def server_url():
	url = request.url_root
	return url.replace('http:/', 'https:/')

@app.route('/')
def index():
	if not request.headers.getlist("X-Forwarded-For"):
		remote_ip = request.remote_addr
	else:
		remote_ip = request.headers.getlist("X-Forwarded-For")[0]
	tz_string = geoIP.ip2timezone(remote_ip, service_type=GEOIP_WEB_SERVICE)
	#print remote_ip, tz_string
	val = {}
	posts = []
	for p in db.posts.find().sort('time', 1):
		posts.append(Post(post=p, timezone_string=tz_string))
	val['posts'] = posts
	return render_template('thread.html', **val)

@app.route('/robots.txt')
@app.route('/favicon.ico')
def robots_txt():
	return send_from_directory(app.static_folder, request.path[1:])

@app.route('/post', methods=['POST'])
def post():
	prms = request.form

	name = u'Сырно' if len(prms.get('nya1').strip()) == 0 else prms.get('nya1').strip()
	msg = escape(prms.get('nya2').strip())
	pwd = prms.get('password', '').strip()
	if len(msg):
		msg = message_marking(msg)
		msg = clickableURLs(msg)
		msg = checkRefLinks(msg, 1)
		msg = checkQuotes(msg)
		pid = db.seqs.find_and_modify(
				query = {'colection': 'posts'},
				update = {'$inc': {'id': 1}},
				fields = {'id': 1, '_id': 0},
				new = True 
			)
		post = {
			'pid': pid.get('id'),
			'post': msg.replace("\n", '<br>'),
			'poster': name,
			'time': int(time.time())
		}
		if pwd:
			post['password'] = sha224(pwd).hexdigest()
		db.posts.insert(post)
	
	return redirect("/", code=302)

marking_rules = (
  (re.compile('\*\*(?P<bold>.*?)\*\*', re.VERBOSE), r'<b>\g<bold></b>'),
  (re.compile('__(?P<underline>.*?)__', re.VERBOSE), r'<span class="underline">\g<underline></span>'),
  (re.compile('--(?P<strike>.*?)--', re.VERBOSE), r'<strike>\g<strike></strike>'),
  (re.compile('%%(?P<spoiler>.*?)%%', re.VERBOSE), r'<span class="spoiler">\g<spoiler></span>'),
  (re.compile('\*(?P<italic>.*?)\*', re.VERBOSE), r'<i>\g<italic></i>'),
  (re.compile('_(?P<italic>.*?)_', re.VERBOSE), r'<i>\g<italic></i>'),
  (re.compile('`(?P<code>.*?)`', re.VERBOSE), r'<code>\g<code></code>'),
)

def message_marking(message):
	l = []
	for line in message.split('\n'):
		line = line.strip()
		for (p, mark_sub) in marking_rules:
			line = p.sub(mark_sub, line)
		l.append(line)
	return '\n'.join(l)

def refLinksReplace(match):
	match = match.group()
	postid = match[len('&gt;&gt;'):]
	parentid = 1
	if parentid != 0:
		if postid == parentid:
			return r'<a href="/.html" onclick="javascript:highlight(' + '\'' + postid + '\'' + r', true);">&gt;&gt;' + postid + '</a>'
		else:
			return '<a href="#' + postid + r'" onclick="javascript:highlight(' + '\'' + postid + '\'' + r', true);">&gt;&gt;' + postid + '</a>'
	return match

def checkQuotes(message):
	message = re.compile(r'^&gt;(.*)$', re.MULTILINE).sub(r'<span class="unkfunc">&gt;\1</span>', message)
	return message

def checkRefLinks(message, parentid):
  message = re.compile(r'&gt;&gt;([0-9]+)').sub(refLinksReplace, message)
  return message

def clickableURLs(message):
	translate_prog = prog = re.compile(r'\b(http|ftp|https)://\S+(\b|/)|\b[-.\w]+@[-.\w]+')
	i = 0
	list = []
	while 1:
		m = prog.search(message, i)
		if not m:
			break
		j = m.start()
		list.append(message[i:j])
		i = j
		url = m.group(0)
		while url[-1] in '();:,.?\'"<>':
			url = url[:-1]
		i = i + len(url)
		url = url
		if ':' in url:
			repl = '<a href="%s">%s</a>' % (url, url)
		else:
			repl = '<a href="mailto:%s">&lt;%s&gt;</a>' % (url, url)
		list.append(repl)
	j = len(message)
	list.append(message[i:j])
	return ''.join(list)

@app.route('/last_kanojos.html')
def last_kanojos_html():
	val = {}
	return render_template('last_kanojos.html', **val)

@app.route('/last_kanojos.json')
def last_kanojos():
	data = {
		'code': 200,
		'kanojos': []
	}
	for i in db.info.find().sort('timestamp', -1).limit(100):
		i.pop('_id', None)
		i.pop('timestamp', None)
		kid = i.get('kid')
		if kid is None:
			kid = i.get('img_url', '').split('/')[-1].split('.')[0]
			if kid.isdigit():
				kid = int(kid)
		if isinstance(kid, int):
			i['url'] = 'http://www.barcodekanojo.com/kanojo/%d/%s'%(kid, i.get('name', '_'))
		data['kanojos'].append(i)
	return json_response(data)

@app.route('/add_job', methods=['POST'])
def add_job():
	data = request.form.get('nya')
	#data = 'https://www.barcodekanojo.com/user/407529/Everyone http://www.barcodekanojo.com/kanojo/2606490/아...바타  fsdf'
	re_u = re.compile('^https?://www\.barcodekanojo\.com/user/(\d+)/.+$')
	re_k = re.compile('^https?://www\.barcodekanojo\.com/kanojo/(\d+)/.+$')
	users = []
	kanojos = []
	errors = []
	for line in data.split():
		s = re_u.search(line.strip())
		if s:
			users.append(int(s.groups()[0]))
		else:
			k = re_k.search(line.strip())
			if k:
				kanojos.append(int(k.groups()[0]))
			else:
				errors.append(line.strip())
	val = {
		'users': users,
		'kanojos': kanojos,
		'errors': errors,
	}
	if len(users) or len(kanojos):
		dt = {}
		if len(users):
			dt['users'] = users
		if len(kanojos):
			dt['kanojos'] = kanojos
		db2.save_jobs.insert(dt)
	return render_template('add_job.html', **val)

@app.route('/images/<fn>', methods=['GET'])
def images_root(fn):
	return send_from_directory('%s/images'%app.static_folder, fn)

@app.route('/images/api/item/basic/<fn>')
@app.route('/images/store/<fn>')
def images_store(fn):
	return send_from_directory('%s/images/store'%app.static_folder, fn)

@app.route('/images/profile_bkgr/<fn>')
def images_profile_bkgr(fn):
	return send_from_directory('%s/images/profile_bkgr'%app.static_folder, fn)


### --------------- storage.barcodekanojo.com ---------------

@app.route('/avatar/<path:path>')
def avatar(path):
	#if request.headers['Host'] == 'storage.barcodekanojo.com':
	filename = '%s/avatar_data/%s'%(app.static_folder, path.lower())
	if os.path.isfile(filename):
		return send_file(filename)
	abort(404)


### --------------- DRESS UP ---------------

@app.route('/dress_up')
def dress_up():
	return redirect('/dress_up/index.html', code=302)

@app.route('/dress_up/<fn>')
def dress_up_file(fn):
	filename = '%s/dress_up/%s'%(app.static_folder, fn)
	if os.path.isfile(filename):
		return send_file(filename)
	abort(404)

def dresup_json_to_barcode(dressup_json):
	keys = ["c_skin", "c_hair", "c_eye", "c_clothes", "body", "hair", "face", "fringe", "mouth", "eye", "nose", "brow", "ear", "spot", "glasses", "accessory", "clothes"]
	r_keys = dressup_json.keys()
	for k in keys:
		if k not in r_keys:
			rv = { 'code': 400 }
			return json_response(rv)
	bc = {
		'skin_color': dressup_json.get('c_skin'),
		'hair_color': dressup_json.get('c_hair'),
		'eye_color': dressup_json.get('c_eye'),
		'clothes_color': dressup_json.get('c_clothes'),
		'body_type': dressup_json.get('body'),
		'hair_type': dressup_json.get('hair'),
		'face_type': dressup_json.get('face'),
		'fringe_type': dressup_json.get('fringe'),
		'mouth_type': dressup_json.get('mouth'),
		'eye_type': dressup_json.get('eye'),
		'nose_type': dressup_json.get('nose'),
		'brow_type': dressup_json.get('brow'),
		'ear_type': dressup_json.get('ear'),
		'spot_type': dressup_json.get('spot'),
		'glasses_type': dressup_json.get('glasses'),
		'accessory_type': dressup_json.get('accessory'),
		'clothes_type': dressup_json.get('clothes')
	}
	return bc

@app.route('/search_barcode.json', methods=['POST'])
def search_barcode():
	data = request.get_json()
	query = {
		'$or': [ 
			{ 'owner_user_id': { '$exists': False } },
			{ 'owner_user_id': 0 }
		]
	}
	query.update(dresup_json_to_barcode(data))
	query.pop('clothes_color', None)
	kanojo = db2.kanojo.find_one(query)
	if kanojo:
		rv = { 'code': 200 }
		rv['barcode'] = kanojo.get('barcode')
	else:
		rv = { 'code': 404 }
	return json_response(rv)

def _genarete_barcode(bid):
	#55.{10}[1]
	n = bid * config.BARCODE_SECRET % 9999999999
	str12 = '55' + str(n).zfill(10)
	sum1 = 0
	sum2 = 0
	i = 1
	for digit in str12:
		if i%2:
			sum1 += int(digit)
		else:
			sum2 += int(digit)
		i = i+1
	rv = (10 - (sum2*3 + sum1) % 10) % 10
	return '%s%d'%(str12, rv)

@app.route('/generate_barcode.json', methods=['POST'])
def generate_barcode():
	data = request.get_json()
	barcode = dresup_json_to_barcode(data)
	barcode['race_type'] = 10
	barcode['eye_position'] = 0
	barcode['brow_position'] = 0
	barcode['mouth_position'] = 0

	barcode['sexual'] = randint(0, 99)
	barcode['recognition'] = randint(0, 99)
	barcode['consumption'] = randint(0, 99)
	barcode['possession'] = randint(0, 99)
	barcode['flirtable'] = randint(0, 99)

	bc = None
	while True:
		bid = db.seqs.find_and_modify(
					query = {'colection': 'barcode_counter'},
					update = {'$inc': {'id': 1}},
					fields = {'id': 1, '_id': 0},
					new = True 
				)
		if not bid:
			return json_response({ 'code': 500 })
		bid = bid.get('id')
		if bid > 9999999999:
			return json_response({ 'code': 500 })
		bc = _genarete_barcode(bid)
		q = { 'barcode': bc }
		if db.kanojos.find_one(q) or db.barcode_tmp.find_one(q):
			continue
		break
	barcode['barcode'] = bc
	barcode['timestamp'] = int(time.time())
	db.barcode_tmp.save(barcode)

	rv = { 'code': 200 }
	rv['barcode'] = bc
	return json_response(rv)


### --------------- BARCODE STATISTIC ---------------

@app.route('/barcode_stat')
def barcode_stat():
	return redirect('/barcode_stat/index.html', code=302)

@app.route('/barcode_stat/<fn>')
def barcode_stat_file(fn):
	filename = '%s/barcode_stat/%s'%(app.static_folder, fn)
	if os.path.isfile(filename):
		return send_file(filename)
	abort(404)



### --------------- KANOJO SERVER ---------------

@app.route('/2/api/account/verify.json', methods=['GET','POST'])
def acc_verify():
	prms = request.form if request.method == 'POST' else request.args
	uuid = prms.get('uuid')
	if uuid:
		user = user_manager.user(uuid=uuid)
		if not user:
			#return json_response({ "code": 404 })
			user = user_manager.create(uuid=uuid)
			if user:
				user = user_manager.clear(user, CLEAR_SELF)
			else:
				return json_response({ "code": 507 })
		session['id'] = user.get('id')
		rv = json_response({ "code": 200, "user": user })
		return rv
	else:
		return json_response({ "code": 400 })

@app.route('/2/api/account/show.json', methods=['GET','POST'])
@app.route('/2/account/show.json', methods=['GET','POST'])
def account_show():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	user = user_manager.user(uid=session['id'], clear=CLEAR_SELF)
	if user:
		return json_response({ "code": 200, "user": user })
	else:
		return json_response({ "code": 404 })

@app.route('/2/user/current_kanojos.json', methods=['GET','POST'])
def user_currentkanojos():
	#kanojo_manager.server = request.url_root[:-1]
	kanojo_manager.server = server_url()[:-1]
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('user_id') is None or prms.get('index') is None or prms.get('limit') is None:
		return json_response({ "code": 400 })
	user_id = int(prms.get('user_id'))
	index = int(prms.get('index'))
	limit = int(prms.get('limit'))
	# TODO: search doesn't work
	search = prms.get('search')
	user = user_manager.user(uid=user_id, clear=CLEAR_NONE)
	if user is None:
		return json_response({ "code": 200, "user": user })
	rspns = { "code": 200 }
	kanojos_ids = user.get('kanojos')
	current_kanojos = []
	if index < len(kanojos_ids):
		if (index+limit) > len(kanojos_ids):
			kanojos_ids = kanojos_ids[index:]
		else:
			kanojos_ids = kanojos_ids[index:index+limit]
		self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
		current_kanojos = kanojo_manager.kanojos(kanojo_ids=kanojos_ids, self_user=self_user)
	rspns['current_kanojos'] = current_kanojos
	rspns['user'] = user_manager.clear(user, CLEAR_OTHER, self_uid=session['id'])
	return json_response(rspns)

@app.route('/2/user/friend_kanojos.json', methods=['GET','POST'])
def user_friendkanojos():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('user_id') is None or prms.get('index') is None or prms.get('limit') is None:
		return json_response({ "code": 400 })
	user_id = int(prms.get('user_id'))
	index = int(prms.get('index'))
	limit = int(prms.get('limit'))
	# TODO: search doesn't work
	search = prms.get('search')
	user = user_manager.user(uid=user_id, clear=CLEAR_NONE)
	if user is None:
		return json_response({ "code": 200, "user": user })
	rspns = { "code": 200 }
	kanojos_ids = user.get('friends')
	friend_kanojos = []
	if index < len(kanojos_ids):
		if (index+limit) > len(kanojos_ids):
			kanojos_ids = kanojos_ids[index:]
		else:
			kanojos_ids = kanojos_ids[index:index+limit]
		self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
		friend_kanojos = kanojo_manager.kanojos(kanojo_ids=kanojos_ids, self_user=self_user)
	rspns['friend_kanojos'] = friend_kanojos
	rspns['user'] = user_manager.clear(user, CLEAR_OTHER, self_uid=session['id'])
	return json_response(rspns)

@app.route('/2/kanojo/like_rankings.json', methods=['GET','POST'])
def kanojo_likerankings():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('index') is None or prms.get('limit') is None:
		return json_response({ "code": 400 })
	index = int(prms.get('index'))
	limit = int(prms.get('limit'))
	query = {}
	kanojos = db.kanojos.find(query).sort('id', -1).skip(index).limit(limit)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	rspns = { "code": 200 }
	like_ranking_kanojos = []
	for k in kanojos:
		like_ranking_kanojos.append(kanojo_manager.clear(k, self_user))
	rspns['like_ranking_kanojos'] = like_ranking_kanojos
	return json_response(rspns)

@app.route('/2/kanojo/show.json', methods=['GET','POST'])
def kanojo_show():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('kanojo_id') is None or prms.get('screen') is None:
		return json_response({ "code": 400 })
	kanojo_id = int(prms.get('kanojo_id'))
	rspns = { "code": 200 }
	barcode = '************'
	rspns['product'] = {"category": "others", "comment": "", "name": "product_name", "product_image_url": None, "barcode": barcode, "country": "Japan", "location": "Somewhere", "scan_count": 1366, "category_id": 21, "geo": None, "company_name": "company_name"}
	rspns['scanned'] = {"category": "others", "comment": "", "user_id": 0, "name": "RT454K", "product_image_url": None, "barcode": barcode, "location": "Somewhere", "nationality": "Japan", "geo": None, "id": 0}
	rspns['messages'] = {"notify_amendment_information": "This information is already used by other users.\nIf your amendment would be incorrect, you will be restricted user."}
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	kanojo = kanojo_manager.kanojo(kanojo_id, self_user=self_user, clear=CLEAR_NONE)
	if kanojo:
		owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)
		rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
		rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER, check_clothes=True)

		kanojo_date_alert = kanojo_manager.kanojo_date_alert(kanojo)
		if kanojo_date_alert:
			rspns['alerts'] = [ kanojo_date_alert, ]
	else:
		rspns = { "code": 404 }
		rspns['alerts'] = [{"body": "The Requested KANOJO was not found.", "title": ""}]
	return json_response(rspns)

@app.route('/2/user/enemy_users.json', methods=['GET','POST'])
def user_enemy_users():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('user_id') is None or prms.get('index') is None or prms.get('limit') is None:
		return json_response({ "code": 400 })
	user_id = int(prms.get('user_id'))
	index = int(prms.get('index'))
	limit = int(prms.get('limit'))
	user = user_manager.user(uid=user_id, clear=CLEAR_NONE)
	rspns = { "code": 200 }
	rspns['user'] = user_manager.clear(user, CLEAR_OTHER, self_uid=session['id'])
	enemy_users = []
	# TODO: get enemy users
	rspns['enemy_users'] = enemy_users
	return json_response(rspns)

@app.route('/2/communication/play_on_live2d.json', methods=['GET', 'POST'])
def communication_play_on_live2d():
	'''
		actions codes (reverse direction):
			10 - swipe
			11 - shake
			12 - touch head
			20 - kiss
			21 - touch breasts
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('kanojo_id') is None or prms.get('actions') is None:
		return json_response({ "code": 400 })
	try:
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError:
		return json_response({ "code": 400 })
	actions = prms.get('actions')
	rspns = { "code": 200 }
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	kanojo = kanojo_manager.kanojo(kanojo_id, self_user=self_user, clear=CLEAR_NONE)
	if kanojo:
		owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)
		rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
		#url = request.url_root+'apibanner/kanojoroom/reactionword.html'
		url = server_url() + 'web/reactionword.html'
		if actions and len(actions):
			print actions
			dt = user_manager.user_action(self_user, kanojo, action_string=actions, current_owner=owner_user)
			if dt.has_key('love_increment') and dt.has_key('info'):
				tmp = dt.get('info', {})
				prms = { key: tmp[key] for key in ['pod', 'a'] if tmp.has_key(key) }
				dt['love_increment']['reaction_word'] = '%s?%s'%(url, urllib.urlencode(prms))
				#print dt['love_increment']['reaction_word']
				dt.pop('info', None)
			rspns.update(dt)
		rspns['self_user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
		rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER)
	else:
		rspns = { "code": 404 }
		rspns['alerts'] = [{"body": "The Requested KANOJO was not found.", "title": ""}]
	return json_response(rspns)

# this url builds in 'communication_play_on_live2d'
@app.route('/apibanner/kanojoroom/reactionword.html')
@app.route('/web/reactionword.html')
def apibanner_kanojoroom_reactionword():
	'''
		a - action param
			1 - gift to kanojo
			2 - extended gift
			3 - date
			4 - extended date (not use)
			10,11,12 - main touch action
			20,21 - main touch by stamina action 
		pod - part of day param
			0 - night
			1 - morning
			2 - day
			3 - evening
	'''
	# TODO: add more text strings
	prms = request.args
	if prms.get('a') is None or prms.get('pod') is None:
		return json_response({ "code": 400 })
	try:
		a = int(prms.get('a'))
		pod = int(prms.get('pod'))
	except ValueError, e:
		return json_response({ "code": 400 })
	val = { 
		'text': reactionword.reactionword_json(a, pod),
	}
	return render_template('apibanner_kanojoroom_reactionword.html', **val)

@app.route('/2/kanojo/vote_like.json', methods=['GET', 'POST'])
def kanojo_vote_like():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('kanojo_id') is None or prms.get('like') is None:
		return json_response({ "code": 400 })
	try:
		kanojo_id = int(prms.get('kanojo_id'))
		like = int(prms.get('like'))
	except ValueError:
		return json_response({ "code": 400 })
	rspns = { "code": 200 }
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	kanojo = kanojo_manager.kanojo(kanojo_id, self_user=self_user, clear=CLEAR_NONE)
	# TODO: save new vote
	rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER)
	return json_response(rspns)

@app.route('/2/resource/product_category_list.json', methods=['GET','POST'])
def resource_product_category_list():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	rspns = { "code": 200 }
	rspns['categories'] = [{"id": "1", "name": "Drink"}, {"id": "2", "name": "Food"}, {"id": "3", "name": "Snack"}, {"id": "4", "name": "Alcohol"}, {"id": "5", "name": "Beer"}, {"id": "6", "name": "Tabacco"}, {"id": "7", "name": "Magazines"}, {"id": "8", "name": "Stationary"}, {"id": "9", "name": "Industrial tool"}, {"id": "10", "name": "Electronics"}, {"id": "11", "name": "Kitchenware"}, {"id": "12", "name": "Clothes"}, {"id": "13", "name": "Accessory"}, {"id": "14", "name": "Music"}, {"id": "15", "name": "DVD"}, {"id": "16", "name": "TVgame"}, {"id": "17", "name": "Sports gear"}, {"id": "18", "name": "Health & beauty"}, {"id": "19", "name": "Medicine"}, {"id": "20", "name": "Medical supplies"}, {"id": "22", "name": "Book"}, {"id": "21", "name": "others"}]
	return json_response(rspns)


@app.route('/2/activity/user_timeline.json', methods=['GET','POST'])
def activity_usertimeline():
	#return json_response({"code": 200, "activities": []})
	data = json.dumps({"activities": [{"kanojo": {"mascot_enabled": "0", "avatar_background_image_url": None, "in_room": True, "mouth_type": 1, "skin_color": 2, "body_type": 1, "race_type": 10, "spot_type": 1, "birth_day": 12, "sexual": 61, "id": 1, "relation_status": 2, "on_advertising": None, "clothes_type": 3, "brow_type": 10, "consumption": 17, "like_rate": 0, "eye_position": 0, "source": "", "location": "Somewhere", "birth_month": 10, "follower_count": 1, "goods_button_visible": True, "accessory_type": 1, "birth_year": 2014, "status": "Born in  12 Oct 2014 @ Somewhere. Area: Italy. 1 users are following.\nShe has relationship with id:1", "hair_type": 3, "clothes_color": 3, "ear_type": 1, "brow_position": 0, "barcode": "8028670007619", "love_gauge": 50, "profile_image_url": "https://192.168.1.19/profile_images/kanojo/1.png?w=88&h=88&face=true", "possession": 11, "eye_color": 5, "glasses_type": 1, "hair_color": 23, "face_type": 3, "nationality": "Italy", "advertising_product_url": None, "geo": "0.0000,0.0000", "emotion_status": 50, "voted_like": False, "eye_type": 101, "mouth_position": 0, "name": "\u30f4\u30a7\u30eb\u30c7", "fringe_type": 22, "nose_type": 1, "advertising_banner_url": None, "advertising_product_title": None, "recognition": 11}, "scanned": None, "user": {"friend_count": 0, "tickets": 20, "name": "id:1", "language": "en", "level": 1, "kanojo_count": 1, "money": 0, "stamina_max": 100, "facebook_connect": False, "profile_image_url": None, "sex": "not sure", "stamina": 100, "twitter_connect": False, "birth_month": 10, "id": 1, "birth_day": 11, "enemy_count": 0, "scan_count": 0, "email": None, "relation_status": 2, "birth_year": 2014, 'description': '', 'generate_count': 0, 'password': ''}, "other_user": {"friend_count": 0, "tickets": 20, "name": "id:1", "language": "en", "level": 1, "kanojo_count": 1, "money": 0, "stamina_max": 100, "facebook_connect": False, "profile_image_url": None, "sex": "not sure", "stamina": 100, "twitter_connect": False, "birth_month": 10, "id": 1, "birth_day": 11, "enemy_count": 0, "scan_count": 0, "email": None, "relation_status": 2, "birth_year": 2014, 'description': '', 'generate_count': 0, 'password': ''}, "activity": "AKI approached dsad.", "created_timestamp": 1413382843, "id": 16786677, "activity_type": 7}], "code": 200})
	data = '''{"activities": [{"kanojo": {"mascot_enabled": "0", "avatar_background_image_url": null, "in_room": true, "mouth_type": 1, "skin_color": 2, "body_type": 1, "race_type": 10, "spot_type": 1, "birth_day": 12, "sexual": 61, "id": 1, "relation_status": 2, "on_advertising": null, "clothes_type": 3, "brow_type": 10, "consumption": 17, "like_rate": 0, "eye_position": 0, "source": "", "location": "Somewhere", "birth_month": 10, "follower_count": 1, "goods_button_visible": true, "accessory_type": 1, "birth_year": 2014, "status": "Born in  12 Oct 2014 @ Somewhere. Area: Italy. 1 users are following.\nShe has relationship with id:1", "hair_type": 3, "clothes_color": 3, "ear_type": 1, "brow_position": 0, "barcode": "8028670007619", "love_gauge": 50, "profile_image_url": "https://192.168.1.19/profile_images/kanojo/1.png?w=88&h=88&face=true", "possession": 11, "eye_color": 5, "glasses_type": 1, "hair_color": 23, "face_type": 3, "nationality": "Italy", "advertising_product_url": null, "geo": "0.0000,0.0000", "emotion_status": 50, "voted_like": false, "eye_type": 101, "mouth_position": 0, "name": "\u30f4\u30a7\u30eb\u30c7", "fringe_type": 22, "nose_type": 1, "advertising_banner_url": null, "advertising_product_title": null, "recognition": 11}, "scanned": null, "user": {"friend_count": 0, "tickets": 5, "name": "id:1", "language": "en", "level": 1, "kanojo_count": 1, "money": 0, "stamina_max": 100, "facebook_connect": false, "profile_image_url": null, "sex": "not sure", "stamina": 100, "twitter_connect": false, "birth_month": 10, "id": 1, "birth_day": 11, "enemy_count": 0, "scan_count": 0, "email": null, "relation_status": 2, "birth_year": 2014, 'description': '', 'generate_count': 0, 'password': ''}, "other_user": {"friend_count": 0, "tickets": 20, "name": "id:1", "language": "en", "level": 1, "kanojo_count": 1, "money": 0, "stamina_max": 100, "facebook_connect": false, "profile_image_url": null, "sex": "not sure", "stamina": 100, "twitter_connect": false, "birth_month": 10, "id": 1, "birth_day": 11, "enemy_count": 0, "scan_count": 0, "email": null, "relation_status": 2, "birth_year": 2014, 'description': '', 'generate_count': 0, 'password': ''}, "activity": "AKI approached dsad.", "created_timestamp": 1413382843, "id": 16786677, "activity_type": 7}], "code": 200}'''
	from gzip import GzipFile
	from io import BytesIO as IO
	gzip_buffer = IO()
	with GzipFile(mode='wb',
					compresslevel=6,
					fileobj=gzip_buffer) as gzip_file:
		gzip_file.write(data)
	response = Response()
	response.data = gzip_buffer.getvalue()
	response.headers['Content-Encoding'] = 'gzip'
	response.headers['Content-Length'] = response.content_length
	response.headers['Vary'] = 'Accept-Encoding'
	response.headers['Server'] = 'Apache'
	response.headers['Cache-Control'] = 'max-age=0, no-cache'
	response.headers['Keep-Alive'] = 'timeout=2, max=100'
	response.headers['X-Mod-Pagespeed'] = '1.6.29.7-3566'
	response.headers['Connection'] = 'Keep-Alive'
	return response

#http://www.barcodekanojo.com/profile_images/kanojo/625028/1289899377/non.png?w=50&h=50&face=true
@app.route('/profile_images/kanojo/<kid>.png')
def profile_images_kanojo(kid):
	# TODO: web
	filename = '%s.png'%kid
	if os.path.isfile(filename):
		return send_file(filename, mimetype='image/png')
	#request.args.get('w,h,face')
	abort(404)

@app.route('/2/notification/register_token.json', methods=['POST'])
def notification_register_token():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	time.sleep(1)
	return json_response({ "code": 200 })

@app.route('/2/api/message/dialog.json', methods=['GET'])
def api_message_dialog():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	return json_response({ "code": 200 })

@app.route('/2/api/webview/chart.json', methods=['GET'])
def api_webview_chart():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if prms.get('user_id') is None or prms.get('kanojo_id') is None:
		return json_response({ "code": 400 })
	user_id = int(prms.get('user_id'))
	kanojo_id = int(prms.get('kanojo_id'))
	rspns = { 'code': 200 }
	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	if kanojo:
		rspns['url'] = server_url()+ 'web/wv_chart.html?c=%d&j=%d&d=%d&s=%d&f=%d'%(kanojo.get('consumption')+100, kanojo.get('possession')+100, kanojo.get('recognition')+100, kanojo.get('sexual')+100, kanojo.get('flirtable',50)+100)
	else:
		rspns = { 'code': 404 }
	return json_response(rspns)

# this url build in 'api_webview_chart'
@app.route('/web/wv_chart.html', methods=['GET'])
def wv_chart():
	prms = request.args
	if prms.get('c') is None or prms.get('j') is None and prms.get('d') is None or prms.get('s') is None and prms.get('f') is None:
		return abort(400)
	val = {
		'celebrity': prms.get('c'),
		'jealousy': prms.get('j'),
		'dedication': prms.get('d'),
		'sexual': prms.get('s'),
		'flirtable': prms.get('f'),
	}
	return render_template('wv_chart.html', **val)

@app.route('/2/api/webview/show.json', methods=['GET'])
def api_webview_show():
	#print request.cookies
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if prms.get('uuid') is None:
		return json_response({ "code": 400 })
	rspns = { 'code': 200 }
	#rspns['url'] = request.url_root[7:] + 'web/i.html?user_id=%d'%session['id']
	rspns['url'] = server_url()[8:] + 'web/i.html?user_id=%d'%session['id']
	#rspns['url'] = 'www.ya.ru'
	#rspns = {"url": "www.barcodekanojo.com/wv_main?language=en&user_id=407529&uuid=UFMjIlUgVSdMUSBYWUxVVFUjTCNZIFZMJVYnVFdVJFEnIFQkAkI", "code": 200}
	response = json_response(rspns)
	#for key in request.cookies.keys():
	#	if key[:3] == '044':
	#		response.set_cookie(key, request.cookies.get(key))
	#response.mimetype = 'text/html'
	return response

# this url build in 'api_webview_show'
@app.route('/web/i.html', methods=['GET'])
def web_i():
	val = {}
	return render_template('index_m.html', **val)

@app.route('/2/barcode/query.json', methods=['GET', 'POST'])
def barcode_query():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if prms.get('barcode') is None:
		return json_response({ "code": 400 })
	barcode = prms.get('barcode')
	session['barcode'] = barcode
	kanojo = kanojo_manager.kanojo_by_barcode(barcode)

	# TODO: for tests
	if barcode == test_barcode.get('barcode'):
		self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
		rspns = { 'code': 200 }
		#barcode = '************'
		rspns['product'] = {"category": "others", "comment": "", "name": "product_name", "product_image_url": None, "barcode": barcode, "country": "Japan", "location": "Somewhere", "scan_count": 1, "category_id": 21, "geo": None, "company_name": "company_name"}
		rspns['scanned'] = None
		rspns['scan_history'] = {"kanojo_count": 0, "friend_count": 0, "barcode": barcode, "total_count": 0}
		rspns['messages'] = {"notify_amendment_information": "This information is already used by other users.\nIf your amendment would be incorrect, you will be restricted user.", "inform_girlfriend": "She is your KANOJO, and you have scanned this barcode 0times.", "inform_friend": "She belongs to miwakoizm, and you have scanned this barcode 0times.", "do_generate_kanojo": "Would you like to generate this KANOJO?\nIt requires 20 stamina.", "do_add_friend": "She belongs to Nobody.\nDo you want to add her on your friend list ? It requires 0 stamina."}
		rspns['barcode'] = test_barcode
		return json_response(rspns)

	if kanojo is None or len(kanojo) == 0:
		bc = db.barcode_tmp.find_one( { 'barcode': barcode } )
		rspns = {
			"code": 200,
			"product": None,
			"scan_history": {"kanojo_count": 0, "friend_count": 0, "barcode": barcode, "total_count": 0},
			"messages": {
				"notify_amendment_information": "This information is already used by other users.\nIf your amendment would be incorrect, you will be restricted user.",
				"inform_girlfriend": "She is your KANOJO, and you have scanned this barcode 0times.",
				"inform_friend": "She belongs to , and you have scanned this barcode 0times.",
				"do_generate_kanojo": "Would you like to generate this KANOJO?\nIt requires 20 stamina.",
				"do_add_friend": "She belongs to .\nDo you want to add her on your friend list ? It requires 5 stamina."
			},
			"scanned": None
		}
		if bc:
			bc.pop('_id', None)
			rspns["barcode"] = bc
		else:
			bc_info = kanojo_manager.generate(barcode)
			if bc_info:
				rspns["barcode"] = bc_info
				bc = copy.deepcopy(bc_info)
				bc['timestamp'] = int(time.time())
				db.barcode_tmp.insert(bc)
			else:
				rspns = {
					"code": 400,
					"exception": "",
					"alerts": [
						{"body": "Barcode error", "title": ""}
					]
				}
	else:
		kanojo = kanojo[0]
		owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)
		if owner_user is None:
			owner_user = user_manager.default_user()
		self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
		rspns = { 'code': 200 }
		#barcode = '************'
		rspns['product'] = {"category": "others", "comment": "", "name": "product_name", "product_image_url": None, "barcode": barcode, "country": "Japan", "location": "Somewhere", "scan_count": 1, "category_id": 21, "geo": None, "company_name": "company_name"}
		rspns['scanned'] = None
		rspns['scan_history'] = {"kanojo_count": 0, "friend_count": 0, "barcode": barcode, "total_count": 0}
		rspns['messages'] = {"notify_amendment_information": "This information is already used by other users.\nIf your amendment would be incorrect, you will be restricted user.", "inform_girlfriend": "She is your KANOJO, and you have scanned this barcode 0times.", "inform_friend": "She belongs to miwakoizm, and you have scanned this barcode 0times.", "do_generate_kanojo": "Would you like to generate this KANOJO?\nIt requires 20 stamina.", "do_add_friend": "She belongs to Nobody.\nDo you want to add her on your friend list ? It requires 0 stamina."}
		rspns['barcode'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_BARCODE)
		rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_SELF)
		rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
	return json_response(rspns)

# curl -v -k --trace-ascii curl.trace -x http://192.168.1.41:8888 -include --form barcode=8028670007619 --form asd=zxc http://192.168.1.19:5000/2/barcode/scan.json
@app.route('/2/barcode/scan.json', methods=['POST'])
@set_parsers(BKMultipartParser)
def barcode_scan():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	parser = BKMultipartParser()
	options = {
		'content_length': request.headers.get('content_length')
	}
	(prms, files) = parser.parse(request.stream.read(), request.headers.get('Content-Type'), **options)
	if prms.get('barcode') is None or prms.get('barcode') != session.get('barcode'):
		return json_response({ "code": 400 })
	session.pop('barcode', None)
	barcode = prms.get('barcode')
	kanojos = kanojo_manager.kanojo_by_barcode(barcode)
	if kanojos is None or len(kanojos) == 0:
		rspns = {
			"code": 400,
			"exception": "",
			"alerts": [
				{"body": "Kanojo don't found.", "title": ""}
			]
		}
	else:
		uid = session['id']
		self_user = user_manager.user(uid=uid, clear=CLEAR_NONE)
		for k in kanojos:
			user_manager.add_kanojo_as_friend(self_user, k)
		rspns = { 'code': 200 }
		rspns['user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	return json_response(rspns)

@app.route('/2/barcode/decrease_generating.json', methods=['GET'])
def barcode_decrease_generating():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	barcode = prms.get('barcode')
	uid = session['id']
	self_user = user_manager.user(uid=uid, clear=CLEAR_NONE)
	rspns = { 'code': 200 }
	rspns['user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	#rspns['product'] = { 'category': 'Industrial tool', 'company_name': 'wakaba', 'name': 'test', 'price': '$9.95', 'product': 'iichan', 'product_image_url': 'http://www.deviantsart.com/g3629d.png' }
	rspns['product'] = { 'category': 'Industrial tool', 'company_name': 'wakaba', 'name': None, 'price': '$9.95', 'product': 'iichan', 'product_image_url': None }
	return json_response(rspns)



test_barcode = { "mouth_type": 3,  "nose_type": 6,  "body_type": 1, "spot_type": 1,  "sexual": 44,  "recognition": 14,  "clothes_type": 3,  "brow_type": 7,  "consumption": 28, "accessory_type": 1,  "possession": 14,   "hair_type": 24,  "clothes_color": 1, "ear_type": 2, "barcode": "4909411043339", "eye_color": 7, "glasses_type": 1,  "hair_color": 17, "face_type": 3, "eye_type": 106, "fringe_type": 16,  "skin_color": 1,
	"brow_position":  0,
	"eye_position":   0,
	"mouth_position": 0,
	}


@app.route('/2/barcode/scan_and_generate.json', methods=['POST'])
@set_parsers(BKMultipartParser)
def barcode_scan_and_generate():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	parser = BKMultipartParser()
	options = {
		'content_length': request.headers.get('content_length')
	}
	(prms, files) = parser.parse(request.stream.read(), request.headers.get('Content-Type'), **options)
	if not prms.has_key('barcode') or not files.has_key('kanojo_profile_image_data') and not prms.has_key('kanojo_name'):
		return json_response({ "code": 400 })

	rspns = { 'code': 200 }
	barcode = prms.get('barcode')
	uid = session['id']
	self_user = user_manager.user(uid=uid, clear=CLEAR_NONE)
	bc_info = db.barcode_tmp.find_one({ 'barcode': barcode })

	if bc_info:
		f = files['kanojo_profile_image_data']
		(crop_url, full_url) = image_manager.crop_and_upload_profile_image(f.stream, filename=prms.get('kanojo_name'))

		kanojo = user_manager.create_kanojo_from_barcode(self_user, bc_info, prms.get('kanojo_name'), crop_url, full_url)
		if kanojo:
			rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER, check_clothes=True)
			rspns['user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
			db.barcode_tmp.remove(bc_info)
		else:
			rspns = { "code": 403, "love_increment": { "alertShow": 1 }, "alerts": [ { "body": "You don't have enough stamina.", "title": "" } ] }
	else:
		rspns = { 'code': 400 }

	return json_response(rspns)

@app.route('/2/account/update.json', methods=['POST'])
@set_parsers(BKMultipartParser)
def account_update():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	parser = BKMultipartParser()
	options = {
		'content_length': request.headers.get('content_length')
	}
	(prms, files) = parser.parse(request.stream.read(), request.headers.get('Content-Type'), **options)

	uid = session['id']
	self_user = user_manager.user(uid=uid, clear=CLEAR_NONE)

	updated = False
	if prms.has_key('name'):
		self_user['name'] = prms['name']
		updated = True
	if prms.has_key('sex'):
		self_user['sex'] = prms['sex']
		updated = True
	if prms.has_key('email'):
		#self_user['email'] = prms['email']
		updated = True
	if prms.has_key('birth_year') and prms.has_key('birth_month') and prms.has_key('birth_day'):
		self_user['birthday'] = int(time.mktime(time.strptime('%s-%s-%s 12:00:00'%(prms['birth_year'], prms['birth_month'], prms['birth_day'] ), '%Y-%m-%d %H:%M:%S'))) - time.timezone
		updated = True
	if files.has_key('profile_image_data'):
		f = files['profile_image_data']
		img_url = image_manager.upload(f.stream.read(), f.content_type, filename=f.filename)
		print 'url: ', img_url
		#f.save(open(f.filename, 'wb'))
		if img_url:
			self_user['profile_image_url'] = img_url
			updated = True

	if updated:
		user_manager.save(self_user)

	rspns = { 
		'code': 200,
		"alerts": [{"body": "Your account have been saved.", "title": ""}]
	}
	rspns['user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	return json_response(rspns)

@app.route('/2/activity/scanned_timeline.json', methods=['GET'])
def activity_scanned_timeline():
	'''
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if not prms.has_key('barcode') or not prms.has_key('index') and not prms.has_key('limit'):# or not prms.has_key('since_id'):
		return json_response({ "code": 400 })
	barcode = prms.get('barcode')
	try:
		index = int(prms.get('index'))
		limit = int(prms.get('limit'))
	except ValueError, e:
		return json_response({ "code": 400 })
	# TODO: logic
	rspns = { 'code': 200 }
	rspns['activities'] = []
	return json_response(rspns)

@app.route('/2/barcode/update.json', methods=['POST'])
@set_parsers(BKMultipartParser)
def barcode_update():
	'''
		update product info
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	parser = BKMultipartParser()
	options = {
		'content_length': request.headers.get('content_length')
	}
	(prms, files) = parser.parse(request.stream.read(), request.headers.get('Content-Type'), **options)
	# TODO: logic
	rspns = { 'code': 200 }
	return json_response(rspns)


@app.route('/2/communication/store_items.json', methods=['GET'])
def communication_store_items():
	'''
		item_class: 1 - items, 2 - date, 3 - tickets
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if not prms.has_key('item_class') or not prms.has_key('item_category_id'):
		return json_response({ "code": 400 })
	try:
		item_class = int(prms.get('item_class'))
		item_category_id = int(prms.get('item_category_id'))
	except ValueError, e:
		return json_response({ "code": 400 })
	rspns = { 'code': 200 }

	# TODO: show ticket items
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	if item_class == 3:
		rspns['item_categories'] = []
	elif item_class==1:
		rspns['item_categories'] = store.category_goods(item_category_id, has_items=user_manager.user_items(self_user))
	elif item_class==2:
		rspns['item_categories'] = store.category_dates(item_category_id, has_items=user_manager.user_items(self_user))
	return json_response(rspns)

@app.route('/2/communication/date_list.json', methods=['GET'])
def communication_date_list():
	'''
		type_id - 1 (store, can buy), 2 - belongings list
		kanojo_id - kanojo_id
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if not prms.has_key('type_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		type_id = int(prms.get('type_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })

	rspns = { 'code': 200 }

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	allow_kanojo = KANOJO_OTHER
	if kanojo.get('owner_user_id') == session['id']:
		allow_kanojo = KANOJO_OWNER
	elif session['id'] in kanojo.get('followers', []):
		allow_kanojo = KANOJO_FRIEND
	if type_id == 1:
		rspns['item_categories'] = store.dates_list(allow_kanojo, user_level=self_user.get('level'))
	elif type_id == 2:
		has_items = user_manager.user_items(self_user)
		if has_items:
			rspns['item_categories'] = store.dates_list(allow_kanojo, user_level=self_user.get('level'), filter_has_items=True, has_items=has_items)
		else:
			rspns['item_categories'] = []

	return json_response(rspns)

@app.route('/2/shopping/compare_price.json', methods=['GET', 'POST'])
def shopping_compare_price():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('store_item_id') or not prms.has_key('price'):
		return json_response({ "code": 400 })
	try:
		store_item_id = int(prms.get('store_item_id'))
		price = int(prms.get('price'))
	except ValueError, e:
		return json_response({ "code": 400 })

	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	rspns = { 'code': 200 }
	#  Client work with commented lines
	#rspns['store_item_id'] = store_item_id
	#rspns['use_ticket'] = price
	#rspns['numbers_ticket'] = self_user.get('tickets', 0)
	return json_response(rspns)

@app.route('/2/communication/item_list.json', methods=['GET'])
def communication_item_list():
	'''
		type_id - 1 (can buy), 2 - belongings list
		kanojo_id - kanojo_id
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if not prms.has_key('type_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		type_id = int(prms.get('type_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })
	rspns = { 'code': 200 }

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	allow_kanojo = KANOJO_OTHER
	if kanojo.get('owner_user_id') == session['id']:
		allow_kanojo = KANOJO_OWNER
	elif session['id'] in kanojo.get('followers', []):
		allow_kanojo = KANOJO_FRIEND
	if type_id == 1:
		rspns['item_categories'] = store.goods_list(allow_kanojo, user_level=self_user.get('level'))
	elif type_id == 2:
		has_items = user_manager.user_items(self_user)
		if has_items:
			rspns['item_categories'] = store.goods_list(allow_kanojo, user_level=self_user.get('level'), filter_has_items=True, has_items=has_items)
		else:
			rspns['item_categories'] = []
	return json_response(rspns)

@app.route('/2/communication/has_items.json', methods=['GET'])
def communication_has_items():
	'''
		item_class: 1 - items, 2 - date
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.args
	if not prms.has_key('item_class') or not prms.has_key('item_category_id'):
		return json_response({ "code": 400 })
	try:
		item_class = int(prms.get('item_class'))
		item_category_id = int(prms.get('item_category_id'))
	except ValueError, e:
		return json_response({ "code": 400 })
	rspns = { 'code': 200 }

	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	has_items = user_manager.user_items(self_user)
	if item_class == 3:
		rspns['item_categories'] = []
	elif item_class==1:
		if has_items:
			rspns['item_categories'] = store.category_goods(item_category_id, filter_has_items=True, has_items=has_items)
		else:
			rspns['item_categories'] = []
	elif item_class==2:
		if has_items:
			rspns['item_categories'] = store.category_dates(item_category_id, filter_has_items=True, has_items=has_items)
		else:
			rspns['item_categories'] = []
	return json_response(rspns)

@app.route('/2/communication/do_gift.json', methods=['GET', 'POST'])
def communication_do_gift():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('basic_item_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		basic_item_id = int(prms.get('basic_item_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)

	rspns = { 'code': 200 }
	rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
	url = server_url() + 'web/reactionword.html'
	do_gift = user_manager.user_action(user=self_user, kanojo=kanojo, do_gift=basic_item_id, is_extended_action=False)
	if do_gift.has_key('love_increment') and do_gift.has_key('info'):
		tmp = do_gift.get('info', {})
		prms = { key: tmp[key] for key in ['pod', 'a'] if tmp.has_key(key) }
		do_gift['love_increment']['reaction_word'] = '%s?%s'%(url, urllib.urlencode(prms))
		do_gift.pop('info', None)
	rspns.update(do_gift)
	rspns['self_user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	if kanojo.get('owner_user_id') != session['id']:
		rspns['owner_user'] = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_OTHER)
	else:
		rspns['owner_user'] = user_manager.clear(self_user, CLEAR_OTHER, self_user=self_user)
	return json_response(rspns)

@app.route('/2/shopping/verify_tickets.json', methods=['GET', 'POST'])
def shopping_verify_tickets():
	'''
		buy extend gift/date
	'''
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('store_item_id') or not prms.has_key('use_tickets'):
		return json_response({ "code": 400 })
	try:
		store_item_id = int(prms.get('store_item_id'))
		use_tickets = int(prms.get('use_tickets'))
	except ValueError, e:
		return json_response({ "code": 400 })

	rspns = { 'code': 200 }
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	item_type = store.item_type(store_item_id)
	if item_type==1:
		buy_present = user_manager.user_action(self_user, None, do_gift=store_item_id, is_extended_action=True)
	elif item_type==2:
		buy_present = user_manager.user_action(self_user, None, do_date=store_item_id, is_extended_action=True)
	else:
		rspns = { 'code': 400 }
	rspns.update(buy_present)
	return json_response(rspns)



@app.route('/2/communication/do_extend_gift.json', methods=['GET', 'POST'])
def communication_do_extend_gift():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('extend_item_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		extend_item_id = int(prms.get('extend_item_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)

	rspns = { 'code': 200 }
	rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
	url = server_url() + 'web/reactionword.html'
	give_present = user_manager.give_present(self_user, kanojo, extend_item_id)
	if give_present.has_key('love_increment') and give_present.has_key('info'):
		tmp = give_present.get('info', {})
		prms = { key: tmp[key] for key in ['pod', 'a'] if tmp.has_key(key) }
		give_present['love_increment']['reaction_word'] = '%s?%s'%(url, urllib.urlencode(prms))
		give_present.pop('info', None)
	rspns.update(give_present)
	rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER, check_clothes=True)
	rspns['self_user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	if kanojo.get('owner_user_id') != session['id']:
		rspns['owner_user'] = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_OTHER)
	else:
		rspns['owner_user'] = user_manager.clear(self_user, CLEAR_OTHER, self_user=self_user)	
	return json_response(rspns)


@app.route('/2/communication/do_date.json', methods=['GET', 'POST'])
def communication_do_date():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('basic_item_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		basic_item_id = int(prms.get('basic_item_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)

	rspns = { 'code': 200 }
	rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
	url = server_url() + 'web/reactionword.html'
	do_date = user_manager.user_action(user=self_user, kanojo=kanojo, do_date=basic_item_id, is_extended_action=False)
	if do_date.has_key('love_increment') and do_date.has_key('info'):
		tmp = do_date.get('info', {})
		prms = { key: tmp[key] for key in ['pod', 'a'] if tmp.has_key(key) }
		do_date['love_increment']['reaction_word'] = '%s?%s'%(url, urllib.urlencode(prms))
		do_date.pop('info', None)
	rspns.update(do_date)
	rspns['self_user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	if kanojo.get('owner_user_id') != session['id']:
		rspns['owner_user'] = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_OTHER)
	else:
		rspns['owner_user'] = user_manager.clear(self_user, CLEAR_OTHER, self_user=self_user)
	return json_response(rspns)

@app.route('/2/communication/do_extend_date.json', methods=['GET', 'POST'])
def communication_do_extend_date():
	if not session.has_key('id'):
		return json_response({ "code": 401 })
	prms = request.form if request.method == 'POST' else request.args
	if not prms.has_key('extend_item_id') or not prms.has_key('kanojo_id'):
		return json_response({ "code": 400 })
	try:
		extend_item_id = int(prms.get('extend_item_id'))
		kanojo_id = int(prms.get('kanojo_id'))
	except ValueError, e:
		return json_response({ "code": 400 })

	kanojo = kanojo_manager.kanojo(kanojo_id, None, clear=CLEAR_NONE)
	self_user = user_manager.user(uid=session['id'], clear=CLEAR_NONE)
	owner_user = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_NONE)

	rspns = { 'code': 200 }
	rspns['owner_user'] = user_manager.clear(owner_user, CLEAR_OTHER, self_user=self_user)
	url = server_url() + 'web/reactionword.html'
	do_date = user_manager.do_date(self_user, kanojo, extend_item_id)
	if do_date.has_key('love_increment') and do_date.has_key('info'):
		tmp = do_date.get('info', {})
		prms = { key: tmp[key] for key in ['pod', 'a'] if tmp.has_key(key) }
		do_date['love_increment']['reaction_word'] = '%s?%s'%(url, urllib.urlencode(prms))
		do_date.pop('info', None)
	rspns.update(do_date)
	rspns['kanojo'] = kanojo_manager.clear(kanojo, self_user, clear=CLEAR_OTHER, check_clothes=True)
	rspns['self_user'] = user_manager.clear(self_user, CLEAR_SELF, self_user=self_user)
	if kanojo.get('owner_user_id') != session['id']:
		rspns['owner_user'] = user_manager.user(uid=kanojo.get('owner_user_id'), clear=CLEAR_OTHER)
	else:
		rspns['owner_user'] = user_manager.clear(self_user, CLEAR_OTHER, self_user=self_user)	
	return json_response(rspns)




# --------  CRON  --------


#@sched.scheduled_job('interval', minutes=10)
def update_stamina_job():
	t = (int(time.time())/60)%(60*24)
	run_period = 10
	idxs = []
	tmp = t % 240
	for i in range(6):
		for j in range(run_period):
			idxs.append((tmp+j)%(60*24))
		tmp += 240
	query = { 
		'stamina_idx': { "$in": idxs}
	}
	#print int(time.time()), idxs
	for user in db.users.find(query):
		user_manager.user_change(user, up_stamina=True, update_db_record=True)
		print 'Recover stamina \"%s\"(%d)'%(user.get('name'), user.get('id'))

def test_job():
	print int(time.time())


update_stamina_job()

from apscheduler.schedulers.background import BackgroundScheduler

#if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
#if True:
sched = BackgroundScheduler()
sched.add_job(update_stamina_job, 'interval', minutes=10, id='update_stamina_job', replace_existing=True)
#sched.add_job(test_job, 'interval', seconds=30)
sched.start()


if __name__ == "__main__":
	app.debug = True
	#app.run(host='0.0.0.0', port=443, ssl_context=context)
	#app.run(host='192.168.1.19', port=443, ssl_context=context)
	app.run(host='0.0.0.0', port=5000)
	#app.run(host='localhost')
