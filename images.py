#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.1'
__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2014'

from PIL import Image
import json
import requests
try:
	from gdrive_cdn import UploadToCDN
except ImportError, e:
	pass
import StringIO


class UploadToDeviantsart(object):
	def __init__(self):
		super(UploadToDeviantsart, self).__init__()

	def upload(self, content, content_type='image/jpeg', filename='image.jpg'):
		r = requests.post('http://deviantsart.com', files={'file': (filename, content, content_type)})
		try:
			rv = json.loads(r.text)
		except ValueError:
			return False
		return rv.get('url', False)



class ImageManager(object):
	def __init__(self):
		super(ImageManager, self).__init__()

	def upload(self, image_data, content_type='image/jpeg', filename='image.jpg'):
		return UploadToDeviantsart().upload(image_data, content_type, filename)

	def crop_and_upload_profile_image(self, img_data, filename='kanojo', upload_full_image=True):
		try:
			cdn = UploadToCDN()
		except NameError, e:
			cdn = UploadToDeviantsart()
		im = Image.open(img_data)
		cr = im.crop((94, 40, 170+94, 170+40))
		cr.thumbnail((88, 88), Image.ANTIALIAS)
		dt = StringIO.StringIO()
		cr.save(dt, format="png")
		crop_url = cdn.upload(dt.getvalue(), content_type='image/png', filename=u'%ss.png'%filename)
		dt.close()

		full_url = None
		if cdn and upload_full_image:
			dt = StringIO.StringIO()
			im.save(dt, format="png")
			full_url = cdn.upload(dt.getvalue(), content_type='image/png', filename=u'%s.png'%filename)
			dt.close()
		return (crop_url, full_url)


if __name__=='__main__':
	im = Image.open('1.png')
	#im = Image.open(StringIO.StringIO(buffer))
	cr = im.crop((94, 40, 170+94, 170+40))
	cr.thumbnail((88, 88), Image.ANTIALIAS)
	dt = StringIO.StringIO()
	cr.save(dt, format="png")
	crop_url = UploadToCDN().upload(dt.getvalue(), content_type='image/png', filename=u'best_girl.png')
	#crop_url = UploadToDeviantsart().upload(dt.getvalue(), content_type='image/png')
	dt.close()

	full_url = None
	try:
		cdn = UploadToCDN()
	except NameError, e:
		cdn = None
	if cdn:
		dt = StringIO.StringIO()
		im.save(dt, format="png")
		full_url = UploadToCDN().upload(dt.getvalue(), content_type='image/png', filename=u'fk.png')
		dt.close()
	print crop_url, full_url