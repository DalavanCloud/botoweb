# Author: Chris Moyer
import os, os.path
import yaml
from botoweb.config import Config
from pkg_resources import get_provider, ResourceManager

import boto 
import logging
log = logging.getLogger("botoweb")

class Environment(object):
	"""botoweb Environment"""

	def __init__(self, module, env=None):
		"""Initialize the Environment object
		:param module: The Module that serves as the basis for this botoweb application
		:param env: Optional environment file that overrides any settings in our config
		"""
		self.module = module
		self._client_connection = None
		if not env:
			env = os.environ.get("BOTO_WEB_ENV")
		self.env = env

		# Config setup
		self.config = Config()
		self.config.env = self

		self.dist = get_provider(self.module)
		self.mgr = ResourceManager()

		if self.dist.has_resource("conf"):
			self.config.update(self.get_config("conf"))

		if env and os.path.exists(self.env):
			log.info("Loading environment: %s" % self.env)
			self.config.update(yaml.load(open(self.env, "r")))

		# Set up the DB shortcuts
		if not self.config.has_key("DB"):
			self.config['DB'] = {
									"db_type": self.config.get("DB", "db_type", "SimpleDB"),
									"db_user": self.config.get("Credentials", "aws_access_key_id"),
									"db_passwd": self.config.get("Credentials", "aws_secret_access_key")
								}
		if self.config.has_key("auth_db"):
			self.config['DB']['User'] = {"db_name": self.config['auth_db']}
		if self.config.has_key("default_db"):
			self.config['DB']['db_name'] = self.config["default_db"]
		if self.config.has_key("session_db"):
			self.config['DB']['Session'] = {'db_name': self.config["session_db"]}

	def get_config(self, path):
		"""Get configuration file at path
		:param path: Location for the file to load
		:type path: str
		"""
		config = {}
		for cf in self.dist.resource_listdir(path):
			if cf.endswith(".yaml"):
				section_name = cf[:-5]
				section = yaml.load(self.dist.get_resource_stream(self.mgr, os.path.join(path, cf)))
				if isinstance(section, dict):
					config[section_name] = section
				else:
					if not config.has_key("botoweb"):
						config['botoweb'] = {}
					config['botoweb'][section_name] = section
			elif not cf.startswith("."):
				config[cf] = self.get_config(os.path.join(path, cf))
		return config

	def connect_client(self, host=None, port=None, enable_ssl=None):
		"""Client Connection caching"""
		if not self._client_connection and self.config.has_section("client"):
			if not enable_ssl:
				enable_ssl = bool(self.config.get("client", "enable_ssl", True))
			if not host:
				host = self.config.get("client", "host", "localhost")
			if not port:
				port = int(self.config.get("client", "port", 8080))
			log.debug("Creating connection: %s:%s" % (host, port))
			from botoweb.client.connection import ClientConnection
			self._client_connection = ClientConnection(host, port, enable_ssl)
			self._client_connection.request("GET", "/")
		return self._client_connection

	# Add in the shortcuts that are normally in boto
	def connect_sqs(self, aws_access_key_id=None, aws_secret_access_key=None, **kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("Credentials", "aws_access_key_id")
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("Credentials", "aws_secret_access_key")
		return boto.connect_sqs(aws_access_key_id, aws_secret_access_key, **kwargs)

	def connect_s3(self, aws_access_key_id=None, aws_secret_access_key=None, **kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("Credentials", "aws_access_key_id")
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("Credentials", "aws_secret_access_key")
		return boto.connect_s3(aws_access_key_id, aws_secret_access_key, **kwargs)

	def connect_ec2(self, aws_access_key_id=None, aws_secret_access_key=None, **kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("Credentials", "aws_access_key_id")
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("Credentials", "aws_secret_access_key")
		return boto.connect_ec2(aws_access_key_id, aws_secret_access_key, **kwargs)

	def connect_sdb(self, aws_access_key_id=None, aws_secret_access_key=None, **kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("DB", "db_user", self.config.get("Credentials", "aws_access_key_id"))
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("DB", "db_passwd", self.config.get("Credentials", "aws_secret_access_key"))
		return boto.connect_sdb(aws_access_key_id, aws_secret_access_key, **kwargs)

	def connect_fps(self, aws_access_key_id=None, aws_secret_access_key=None,**kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("Credentials", "aws_access_key_id")
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("Credentials", "aws_secret_access_key")
		return boto.connect_fps(aws_access_key_id, aws_secret_access_key, **kwargs)

	def connect_cloudfront(self, aws_access_key_id=None, aws_secret_access_key=None, **kwargs):
		if aws_access_key_id == None:
			aws_access_key_id = self.config.get("Credentials", "aws_access_key_id")
		if aws_secret_access_key == None:
			aws_secret_access_key = self.config.get("Credentials", "aws_secret_access_key")
		return boto.connect_cloudfront(aws_access_key_id, aws_secret_access_key, **kwargs)
