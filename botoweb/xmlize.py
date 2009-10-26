# Copyright (c) 2009 Chris Moyer http://coredumped.org
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

BAD_CHARS = ['<', '>', '&'] # Illegal characters in XML that must be wrapped in a CDATA
REGISTERED_CLASSES = {} # A mapping of name=> class for what to decode objects into

from botoweb.fixed_datetime import datetime
from datetime import datetime as datetime_type
from boto.utils import Password
from boto.sdb.db.key import Key

TYPE_NAMES = {
	str: "string",
	unicode: "string",
	int: "integer",
	list: "list",
	dict: "map",
	datetime: "dateTime",
	datetime_type: "dateTime",
	object: "object",
	Password: "password",
	Key: "object",
}

class DefaultObject(object):
	"""Default object for when re get something that we don't know about yet"""
	id = None
	__name__ = None

class ProxyObject(object):
	"""Proxy object so we're not setting up an actual object,
	we simply have the __name__ set to the name of this object type,
	and we set the __model_class__ to the model_class for this object.
	all other properties set are actual properties explicitly set in
	the XML.

	We also set __id__ if it's set in the "id=" attribute
	"""
	__name__ = None
	__model_class__ = None
	__id__ = None

from lxml import etree
class XMLSerializer(object):
	"""XML Serializer object"""

	def __init__(self, file=None):
		"""Create a new serialization file"""
		if not file:
			from tempfile import TemporaryFile
			file = TemporaryFile()
		self.file = file
		self.num_objs = 0

	def encode(self, prop_name, prop_value):
		"""Encode this value to XML"""
		if prop_value == None:
			return None
		prop_type = type(prop_value)
		if prop_type in self.type_map:
			return self.type_map[prop_type](self, prop_name, prop_value)
		if isinstance(prop_value, object):
			return self.encode_object(prop_name, prop_value)
		return self.encode_default(prop_name, prop_value, prop_type.__name__)

	def encode_default(self, prop_name, prop_value, prop_type):
		"""Encode Default encoding property"""
		if prop_type == "str":
			prop_type = "string"
		args = {"prop_name": prop_name, "prop_value": self.encode_cdata(prop_value), "prop_type": str(prop_type)}
		self.file.write("""<%(prop_name)s type="%(prop_type)s">%(prop_value)s</%(prop_name)s>""" % args)

	def encode_str(self, prop_name, prop_value):
		return self.encode_default(prop_name, str(prop_value), "string")

	def encode_int(self, prop_name, prop_value):
		return self.encode_default(prop_name, str(prop_value), "integer")

	def encode_list(self, prop_name, prop_value):
		"""Encode a list by encoding each property individually"""
		for val in prop_value:
			self.encode(prop_name, val)

	def encode_dict(self, prop_name, prop_value):
		"""Encode a dict by encoding each element individually with a name="" param"""
		self.file.write("""<%s type="complexType">""" % prop_name)
		for k in prop_value.keys():
			v = prop_value[k]
			self.encode(str(k), v)
		self.file.write("""</%s>""" % prop_name)

	def encode_datetime(self, prop_name, prop_value):
		"""Encode a DATETIME into standard ISO 8601 Internet Format"""
		self.encode_default(prop_name, prop_value.isoformat(), "dateTime")

	def encode_object(self, prop_name, prop_value):
		"""Encode a generic object (must have an "id" attribute)"""
		from boto.sdb.db.query import Query
		prop_type = prop_value.__class__.__name__
		if isinstance(prop_value, Query):
			return self.encode_query(prop_name, prop_value)
		elif hasattr(prop_value, "id"):
			prop_value = str(prop_value.id)
		else:
			prop_value = str(prop_value)
		self.file.write("""<%s type="reference" object_type="%s" id="%s" href="%s"/>""" % (prop_name, prop_type, prop_value, prop_name))

	def encode_query(self, prop_name, prop_value):
		"""Encode a query, this is sent as a reference"""
		#TODO: Fix this by somehow getting the ID into the href
		self.file.write("""<%s type="reference" href="%s"/>""" % (prop_name, prop_name))

	def encode_cdata(self, string):
		"""Return what might be a CDATA encoded string"""
		string = str(string)
		for ch in BAD_CHARS:
			if ch in string:
				return "<![CDATA[ %s ]]>" % string
		return string

	def encode_bool(self, prop_name, prop_value):
		self.encode_default(prop_name, str(prop_value), "boolean")


	type_map = {
		str: encode_str,
		int: encode_int,
		unicode: encode_str,
		list: encode_list,
		dict: encode_dict,
		datetime: encode_datetime,
		datetime_type: encode_datetime,
		object: encode_object,
		bool: encode_bool,
	}


	def dump(self, obj, objname = None):
		"""Dump this object to our serialization"""
		from boto.sdb.db.model import Model
		if not isinstance(obj, object):
			if not objname:
				objname = obj.__name__
			self.encode(objname, obj)
		elif isinstance(obj, list) or isinstance(obj, dict):
			if not objname:
				objname = obj.__class__.__name__
			self.encode(objname, obj)
		else:
			if not objname:
				objname = obj.__class__.__name__
			if hasattr(obj, "id") and obj.id:
				self.file.write("""<%s id="%s" href="%s">""" % (objname, obj.id, obj.id))
			else:
				self.file.write("<%s>" % objname)
			if isinstance(obj, Model):
				for prop in obj.properties():
					self.encode(prop.name, getattr(obj, prop.name))
			else:
				for prop_name in obj.__dict__:
					if not prop_name.startswith("_") and not prop_name == "id":
						prop_value = getattr(obj, prop_name)
						if not type(prop_value) == type(self.dump):
							self.encode(prop_name, prop_value)
			self.file.write("</%s>" % objname)

	def load(self):
		"""Load from this file to an object or object list"""
		self.file.seek(0)
		tree = etree.parse(self.file)
		root = tree.getroot()
		return self.decode(root)

	def decode(self, node):
		"""Decode this node into an object or list of objects"""
		if node.tag.endswith("List"):
			return [self.decode(x) for x in node]
		else:
			obj = ProxyObject()
			obj.__name__ = node.tag
			obj.__id__ = node.get("id")

			if node.tag in REGISTERED_CLASSES.keys():
				model_class = REGISTERED_CLASSES[node.tag]
				obj.__model_class__ = model_class

			props = {}
			for prop in node:
				value = None
				prop_type = (prop.get("type") or "string").lower()
				if prop_type == "string":
					value = self.decode_string(prop)
				elif prop_type in ('complex', 'complextype'):
					# Dictionary
					pass
				elif prop_type in ('date', 'datetime', 'time'):
					# Date Time
					value = self.decode_datetime(prop)
				elif prop_type == "bool":
					# Boolean
					value = (self.decode_string(prop).upper() == "TRUE")
				elif prop_type == "reference":
					# Object (new style)
					value = ProxyObject()
					value.__name__ = prop.get("object_type")
					value.__id__ = prop.get("id")
				elif prop.get("type") in REGISTERED_CLASSES.keys():
					# Object (old style)
					value = REGISTERED_CLASSES[prop.get("type")]()
					value.id = prop.text
				else:
					# By default we assume it's a string
					value = self.decode_string(prop)
				if not props.has_key(prop.tag):
					props[prop.tag] = []
				props[prop.tag].append(value)
			for prop_name in props:
				val = props[prop_name]
				if len(val) == 1:
					val = val[0]
				setattr(obj, prop_name, val)
			return obj


	def decode_string(self, node):
		"""Decode a simple string property"""
		ret = node.text
		# Prevent "None" from being sent back as a None, instead of an empty string
		if not ret:
			ret = ""
		return ret


	def decode_datetime(self, node):
		"""Decode a simple string property"""
		date_str = self.decode_string(node)
		if not date_str or len(date_str) == 0:
			return None
		return datetime.parseisoformat(date_str)



	
def dump(obj, file=None, objname=None):
	"""Write an XML representation of *obj* to the open file object *file*
	"""
	enc = XMLSerializer(file)
	enc.dump(obj, objname)
	enc.file.seek(0)
	return enc.file

def dumps(obj, objname=None):
	"""Dump the XML to a string, this is equivalent to dump(obj).read()"""
	return dump(obj, objname=objname).read()

def load(file):
	"""Read a from the open file object *file* and interpret it as an XML serialization

	@param file: File object to read from
	@type file: file
	"""
	return XMLSerializer(file).load()

def loads(string):
	"""Load from a string
	@param string: String of the XML to parse
	@type string: str
	"""
	from StringIO import StringIO
	return load(StringIO(string))

def register(cls, name=None):
	"""Register a class to be deserializable

	@param cls: Class to register
	@type cls: class

	@param name: An optional conanical name to use for this class, the default is to use 
		just the name of the class
	@type name: str
	"""
	if name == None:
		name = cls.__name__
	REGISTERED_CLASSES[name] = cls

def get_class(class_name):
	"""Get the class for this name"""
	return REGISTERED_CLASSES.get(class_name)
