"""
writemdict.py - a library for creating dictionary files in the MDict file format.

Optional dependencies:
  python-lzo: Required to write dictionaries using LZO compression. (Other compression schemes are available.)

Simple usage example: 

    from __future__ import unicode_literals
    from writemdict import MDictWriter

    dictionary = {"doe": "a deer, a female deer.",
                  "ray": "a drop of golden sun.",
                  "me": "a name I call myself.",
                  "far": "a long, long way to run."}

    writer = MDictWriter(dictionary, title="Example Dictionary", description="This is an example dictionary.")
    outfile = open("dictionary.mdx", "wb")
    writer.write(outfile)
    outfile.close()

  This will create an MDX file called "dictionary.mdx", with four entries: "doe", "ray", "me", "far", and the 
  corresponding definitions.

  For further options, see the documentation for MdxWriter.__init__().
"""

from __future__ import unicode_literals

import struct, zlib, operator, sys, datetime

from .ripemd128 import ripemd128
# from cgi import escape
from html import escape
from .pureSalsa20 import Salsa20

try:
	from . import lzo
	HAVE_LZO = True
except ImportError:
	HAVE_LZO = False

class ParameterError(Exception):
	### Raised when some parameter to MdxWriter is invalid or uninterpretable.
	pass

def _mdx_compress(data, compression_type=2):
	header = (struct.pack(b"<L", compression_type) + 
	         struct.pack(b">L", zlib.adler32(data) & 0xffffffff)) #depending on python version, zlib.adler32 may return a signed number. 
	if compression_type == 0: #no compression
		return header + data
	elif compression_type == 2:
		return header + zlib.compress(data)
	elif compression_type == 1:
		if HAVE_LZO:
			return header + lzo.compress(data)[5:] #python-lzo adds a 5-byte header.
		else:
			raise NotImplementedError()
	else:
		raise ParameterError("Unknown compression type")
		
def _fast_encrypt(data, key):
	b = bytearray(data)
	key = bytearray(key)
	previous = 0x36
	for i in range(len(b)):
		t = b[i] ^ previous ^ (i&0xff) ^ key[i%len(key)]
		previous = b[i] = ((t>>4)|(t<<4)) & 0xff
	return bytes(b)
	
def _mdx_encrypt(comp_block):
	key = ripemd128(comp_block[4:8] + struct.pack(b"<L", 0x3695))
	return comp_block[0:8] + _fast_encrypt(comp_block[8:], key)
	
def _salsa_encrypt(plaintext, dict_key):
	assert(type(dict_key) == bytes)
	assert(type(plaintext) == bytes)
	encrypt_key = ripemd128(dict_key)
	s20 = Salsa20(key=encrypt_key,IV=b"\x00"*8,rounds=8)
	return s20.encryptBytes(plaintext)

def _hexdump(bytes_blob):
	# Returns a hexadecimal representation of bytes_blob, as a (unicode) string.
	#
	# bytes_blob should have type bytes.
	
	# In Python 2.6+, bytes is an alias for str, and indexing into a bytes
	# object gives a string of length 1.
	# In Python 3, indexing into a bytes object gives a number.
	# The following should work on both versions.
	if bytes == str:
		return "".join("{:02X}".format(ord(c)) for c in bytes_blob)
	else:
		return "".join("{:02X}".format(c) for c in bytes_blob)
	
def encrypt_key(dict_key, **kwargs):
	"""
	Generates a hexadecimal key for use with the official MDict program.

	Parameters:
	  dict_key: a bytes object, representing the dictionary password.

	Keyword parameters:
	  Exactly one of email and device_id should be specified. They should be unicode strings,
	  representing either the user's email address, or the device ID of the machine on which
	  the dictionary is to be opened.
	
	Return value:
	  a string of 32 hexadecimal digits. This should be placed in a file of its own,
	  with the same name and location as the mdx file but the extension changed to '.key'.

	Example usage:
		key = encrypt_key(b"password", email="username@example.com")

		key = encrypt_key(b"password", device_id="12345678-9012-3456-7890-1234")
	"""

	if(("email" not in kwargs and "device_id" not in kwargs) or ("email" in kwargs and "device_id" in kwargs)):
		raise ParameterError("Expected exactly one of email and device_id as keyword argument")


	if "email" in kwargs:
		owner_info_digest = ripemd128(kwargs["email"].encode("ascii"))
	else:
		owner_info_digest = ripemd128(kwargs["device_id"].encode("ascii"))

	dict_key_digest = ripemd128(dict_key)
	
	s20 = Salsa20(key=owner_info_digest,IV=b"\x00"*8,rounds=8)
	output_key = s20.encryptBytes(dict_key_digest)
	return _hexdump(output_key)
	

class _OffsetTableEntry(object):
	# Each OffsetTableEntry represents one key/record pair of the dictionary.
	# In addition to the values themselves, it contains information about
	# the offset at which this entry will be placed (i.e. the total length
	# of records before it) which is required by the MDX format.
	def __init__(self, key, key_null, key_len, offset, record_null):
		self.key = key
		self.key_null = key_null
		self.key_len = key_len
		self.offset = offset
		self.record_null = record_null

class MDictWriter(object):
	
	def __init__(self, d, title, description, 
	             block_size=65536, 
	             encrypt_index=False,
	             encoding="utf8",
	             compression_type=2,
	             version="2.0",
	             encrypt_key = None,
	             register_by = None,
	             user_email = None,
	             user_device_id = None,
	             is_mdd=False):
		"""
		Prepares the records. A subsequent call to write() writes 
		the mdx or mdd file.
		   
		d is a dictionary. The keys should be (unicode) strings. If used for an mdx
		  file (the parameter is_mdd is False), then the values should also be 
		  (unicode) strings, containing HTML snippets. If used to write an mdd
		  file (the parameter is_mdd is True), then the values should be binary 
		  strings (bytes objects), containing the raw data for the corresponding 
		  file object.
		
		title is a (unicode) string, with the title of the dictionary
		  description is a (unicode) string, with a short description of the
		  dictionary.
		   
		block_size is the approximate number of bytes (uncompressed)
		  before starting a new block.
		
		
		encrypt_index is true if the keyword index should be encrypted.
		
		encoding is the character encoding to use in the files. Valid options are
		  "utf8", "utf16", "gbk", and "big5". If used to write an mdd file (the
		  parameter is_mdd is True), then this is ignored.
		
		compression_type is an integer specifying the compression type to use.
		  Valid options are 0 (no compression), 1 (LZO compression), or 2 (gzip
		  compression).
		
		version specifies the version of the file format to use. Recognized options are
		  "2.0" and "1.2".
		
		encrypt_key should be a string, containing the dictionary key. If
		  encrypt_key is None, no encryption will be applied. If encrypt_key is
		  not None, you need to specify register_by.

		register_by should be either "email" or "device_id". Ignored unless
		  encrypt_key is not None. Specifies whether the user's email or user's
		  device ID should be used to encrypt the encryption key.

		user_email is ignored unless encrypt_key is not None and register_by is 
		  "email". If it is specified, an encrypted form of encrypt_key will be
		  written into the dictionary header. The file can then be opened by
		  anyone who has set their email (in the MDict client) this this value.
		  If it is not specified, the MDict client will look for this encrypted
		  key in a separate .key file.
			
		user_device_id is ignored unless encrypt_key is not None and register_by
		  is "device_id". If it is specified, an encrypted form of encrypt_key
		  will be written into the dictionary header. The file can then be opened 
		  by anyone whose device ID (as determined by the MDict client) equals this
		  value. If it is not specified, the MDict client will look for this
		  encrypted key in a separate .key file.
		
		is_mdd is a boolean specifying whether the file written will be an mdx file
		  or an mdd file. By default this is False, meaning that an mdd file will
		  be written.
		"""

		self._num_entries = len(d)
		self._title=title
		self._description=description
		self._block_size = block_size
		self._encrypt_index = encrypt_index
		self._encrypt = (encrypt_key is not None)
		self._encrypt_key = encrypt_key
		if register_by not in ["email", "device_id", None]:
			raise ParameterError("Unkonwn register_by type")
		self._register_by = register_by
		self._user_email = user_email
		self._user_device_id = user_device_id
		self._compression_type = compression_type
		self._is_mdd = is_mdd
		
		# encoding is set to the string used in the mdx header.
		# python_encoding is passed on to the python .encode()
		# function to encode the data.
		# encoding_length is the size of one unit of the encoding,
		# used to calculate the length for keys in the key index.
		if not is_mdd:
			encoding = encoding.lower()
			if encoding in ["utf8", "utf-8"]:
				self._python_encoding = "utf_8"
				self._encoding = "UTF-8"
				self._encoding_length = 1
			elif encoding in ["utf16", "utf-16"]:
				self._python_encoding = "utf_16_le"
				self._encoding = "UTF-16"
				self._encoding_length = 2
			elif encoding == "gbk":
				self._python_encoding = "gbk"
				self._encoding = "GBK"
				self._encoding_length = 1
			elif encoding == "big5":
				self._python_encoding = "big5"
				self._encoding = "BIG5"
				self._encoding_length = 1
			else:
				raise ParameterError("Unknown encoding")
		else:
			self._python_encoding="utf_16_le"
			self._encoding_length=2
		if version not in ["2.0", "1.2"]:
			raise ParameterError("Unknown version")
		self._version = version
		self._build_offset_table(d)
		self._build_key_blocks()
		self._build_keyb_index()
		self._build_record_blocks()
		self._build_recordb_index()
		
	def _build_offset_table(self,d):
		# Sets self._offset_table to a table of entries _OffsetTableEntry objects e.
		#
		# where:
		#  e.key: encoded version of the key, not null-terminated
		#  e.key_null: encoded version of the key, null-terminated
		#  e.key_len: the length of the key, in either bytes or 2-byte units, not counting the null character
		#        (as required by the MDX format in the keyword index)
		#  e.offset: the cumulative sum of len(record_null) for preceding records
		#  e.record_null: encoded version of the record, null-terminated
		#
		# Also sets self._total_record_len to the total length of all record fields.
		items = list(d.items())
		items.sort(key=operator.itemgetter(0))
		
		self._offset_table = []
		offset = 0
		for key, record in items:
			key_enc = key.encode(self._python_encoding)
			key_null = (key+"\0").encode(self._python_encoding)
			key_len = len(key_enc) // self._encoding_length
			
			# set record_null to a the the value of the record. If it's
			# an MDX file, append an extra null character.
			if self._is_mdd:
				record_null = record
			else:
				record_null = (record+"\0").encode(self._python_encoding) 
			self._offset_table.append(_OffsetTableEntry(
			    key=key_enc,
			    key_null=key_null,
			    key_len=key_len,
			    record_null=record_null,
			    offset=offset))
			offset += len(record_null)
		self._total_record_len = offset
	
	def _split_blocks(self, block_type):
		# Split either the records or the keys into blocks for compression.
		# 
		# Returns a list of _MdxBlock, where the decompressed size of each block is (as
		# far as practicable) less than self._block_size.
		#
		# block_type should be a subclass of _MdxBlock, i.e. either _MdxRecordBlock or 
		# _MdxKeyBlock.
		
		this_block_start = 0
		cur_size = 0
		blocks = []
		for ind in range(len(self._offset_table)+1):
			if ind != len(self._offset_table):
				t = self._offset_table[ind]
			else:
				t = None
			
			if ind == 0:
				flush = False 
				# nothing to flush yet
				# this part is needed in case the first entry is longer than
				# self._block_size.
			elif ind == len(self._offset_table):
				flush = True #always flush the last block
			elif cur_size + block_type._len_block_entry(t) > self._block_size:
				flush = True #Adding this entry to make us larger than
				             #self._block_size, so flush now.
			else:
				flush = False
			if flush:
				blocks.append(block_type(
				    self._offset_table[this_block_start:ind], self._compression_type, self._version))
				cur_size = 0
				this_block_start = ind
			if t is not None: #mentally add this entry to list of things 
				cur_size += block_type._len_block_entry(t)
		return blocks
		
	def _build_key_blocks(self):
		# Sets self._key_blocks to a list of _MdxKeyBlocks.
		self._key_blocks = self._split_blocks(_MdxKeyBlock)
	
	def _build_record_blocks(self):
		self._record_blocks = self._split_blocks(_MdxRecordBlock)
		
	def _build_keyb_index(self):
		# Sets self._keyb_index to a bytes object, containing the index of key blocks, in
		# a format suitable for direct writing to the file.
		#
		# Also sets self._keyb_index_comp_size and self._keyb_index_decomp_size.
		
		decomp_data = b"".join(b.get_index_entry() for b in self._key_blocks)
		self._keyb_index_decomp_size = len(decomp_data)
		if self._version == "2.0":
			self._keyb_index = _mdx_compress(decomp_data, self._compression_type)
			if self._encrypt_index:
				self._keyb_index = _mdx_encrypt(self._keyb_index)
			self._keyb_index_comp_size = len(self._keyb_index)
		elif self._encrypt_index:
			raise ParameterError("Key index encryption not supported in version 1.2")
		else:
			self._keyb_index = decomp_data
	
	def _build_recordb_index(self):
		# Sets self._recordb_index to a bytes object, containing the index of key blocks,
		# in a format suitable for direct writing to the file.
		
		# Also sets self._recordb_index_size.
		
		self._recordb_index = b"".join(
		    (b.get_index_entry() for b in self._record_blocks))
		self._recordb_index_size = len(self._recordb_index)
	
	def _write_key_sect(self, outfile):
		# Writes the key section header, key block index, and all the key blocks to
		# outfile.
		
		# outfile: a file-like object, opened in binary mode.
		
		keyblocks_total_size = sum(len(b.get_block()) for b in self._key_blocks)
		if self._version == "2.0":
			preamble = struct.pack(b">QQQQQ",
			    len(self._key_blocks),
			    self._num_entries,
			    self._keyb_index_decomp_size,
			    self._keyb_index_comp_size,
			    keyblocks_total_size)
			preamble_checksum = struct.pack(b">L", zlib.adler32(preamble))
			if(self._encrypt):
				preamble = _salsa_encrypt(preamble, self._encrypt_key)
			outfile.write(preamble)
			outfile.write(preamble_checksum)
		else:
			preamble = struct.pack(b">LLLL",
			    len(self._key_blocks),
			    self._num_entries,
			    self._keyb_index_decomp_size,
			    keyblocks_total_size)
			if(self._encrypt):
				preamble = _salsa_encrypt(preamble, self._encrypt_key)
			outfile.write(preamble)
		
		outfile.write(self._keyb_index)
		for b in self._key_blocks:
			outfile.write(b.get_block())
			
	def _write_record_sect(self, outfile):
		# Writes the record section header, record block index, and all the record blocks
		# to outfile.
		#
		# outfile: a file-like object, opened in binary mode.
		
		recordblocks_total_size = sum(
		    (len(b.get_block()) for b in self._record_blocks))
		if self._version == "2.0":
			format = b">QQQQ"
		else:
			format = b">LLLL"
		outfile.write(struct.pack(format,
		    len(self._record_blocks),
		    self._num_entries,
		    self._recordb_index_size,
		    recordblocks_total_size))
		outfile.write(self._recordb_index)
		for b in self._record_blocks:
			outfile.write(b.get_block())
		    
	def write(self, outfile):
		""" 
		Write the mdx file to outfile.
		
		outfile: a file-like object, opened in binary mode.
		"""
		
		self._write_header(outfile)
		self._write_key_sect(outfile)
		self._write_record_sect(outfile)


	def _write_header(self, f):
		encrypted = 0
		if self._encrypt_index:
			encrypted = encrypted | 2
		if self._encrypt:
			encrypted = encrypted | 1
		
		if self._encrypt and self._register_by == "email":
			register_by_str = "EMail"
			if self._user_email is not None:
				regcode = encrypt_key(self._encrypt_key, email=self._user_email)
			else:
				regcode = ""
		elif self._encrypt and self._register_by == "device_id":
			register_by_str = "DeviceID"
			if self._user_device_id is not None:
				regcode = encrypt_key(self._encrypt_key, device_id=self._user_device_id)
			else:
				regcode = ""
		else:
			register_by_str = ""
			regcode = ""
		
		if not self._is_mdd:
			header_string = (
			"""<Dictionary """
			"""GeneratedByEngineVersion="{version}" """ 
			"""RequiredEngineVersion="{version}" """
			"""Encrypted="{encrypted}" """
			"""Encoding="{encoding}" """
			"""Format="Html" """
			"""CreationDate="{date.year}-{date.month}-{date.day}" """
			"""Compact="No" """
			"""Compat="No" """
			"""KeyCaseSensitive="No" """
			"""Description="{description}" """
			"""Title="{title}" """
			"""DataSourceFormat="106" """
			"""StyleSheet="" """
			"""RegisterBy="{register_by_str}" """
			"""RegCode="{regcode}"/>\r\n\x00""").format(
			    version = self._version,
			    encrypted = encrypted,
			    encoding = self._encoding, 
			    date = datetime.date.today(), 
			    description=escape(self._description, quote=True),
			    title=escape(self._title, quote=True),
			    register_by_str=register_by_str,
			    regcode=regcode
			).encode("utf_16_le")
		else:
			header_string = (
			"""<Library_Data """
			"""GeneratedByEngineVersion="{version}" """ 
			"""RequiredEngineVersion="{version}" """
			"""Encrypted="{encrypted}" """
			"""Format="" """
			"""CreationDate="{date.year}-{date.month}-{date.day}" """
			"""Compact="No" """
			"""Compat="No" """
			"""KeyCaseSensitive="No" """
			"""Description="{description}" """
			"""Title="{title}" """
			"""DataSourceFormat="106" """
			"""StyleSheet="" """
			"""RegisterBy="{register_by_str}" """
			"""RegCode="{regcode}"/>\r\n\x00""").format(
			    version = self._version,
			    encrypted = encrypted, 
			    date = datetime.date.today(), 
			    description=escape(self._description, quote=True),
			    title=escape(self._title, quote=True),
			    register_by_str=register_by_str,
			    regcode=regcode
			).encode("utf_16_le")
		f.write(struct.pack(b">L", len(header_string)))
		f.write(header_string)
		f.write(struct.pack(b"<L",zlib.adler32(header_string) & 0xffffffff))

class _MdxBlock(object):
	# Abstract base class for _MdxRecordBlock and _MdxKeyBlock.
	#
	# In the MDX file format, the keyword section and the record section have a
	# similar structure: 
	#
	#   section header
	#   index entry for block 0
	#   ...
	#   index entry for block k
	#   block 0
	#   ...
	#   block k
	# 
	# This class represents one such block. It defines a common interface for
	# record blocks and keyword blocks, to allow the two sections to
	# be built in a uniform manner.
	#
	
	def __init__(self, offset_table, compression_type, version):
		# Builds the data from offset_table.
		#
		# offset_table is a iterable containing _OffsetTableEntry objects.
		
		decomp_data = b"".join(
		    type(self)._block_entry(t, version)
		    for t in offset_table)
		self._decomp_size = len(decomp_data)
		self._comp_data = _mdx_compress(decomp_data, compression_type)
		self._comp_size = len(self._comp_data)
		self._version = version
	
	def get_block(self):
		# Returns a bytes object, containing the data for this block.
		return self._comp_data
		
	def get_index_entry(self):
		# Returns a bytes object, containing the entry for this block in the
		# corresponding key block index or record block index.
		
		raise NotImplementedError()
		
	@staticmethod
	def _block_entry(t, version):
		# Returns the data corresponding to a single entry in offset.
		#
		# t is an _OffsetTableEntry object
		
		raise NotImplementedError()
	
	@staticmethod
	def _len_block_entry(t):
		# Should be approximately equal to len(_block_entry(t)).
		#
		# Used by MdxWriter._split_blocks() to determine where to split into blocks."""
		raise NotImplementedError()
		
class _MdxRecordBlock(_MdxBlock):
	# A class representing a record block.
	#
	# Has the ability to return (in the format suitable for insertion in an mdx file) 
	# both the block itself, as well as the entry in the record block index for that
	# block.

	def __init__(self, offset_table, compression_type, version):
		# Builds the data for offset_table.
		#
		# offset_table is a iterable containing _OffsetTableEntry objects.
		#
		# Actually only uses the record parts.
		
		_MdxBlock.__init__(self, offset_table, compression_type, version)
		
	def get_index_entry(self):
		# Returns a bytes object, containing the entry for this block in the record
		# block index.
		
		if self._version == "2.0":
			format = b">QQ"
		else:
			format = b">LL"
		return struct.pack(format, self._comp_size, self._decomp_size)
	
	@staticmethod
	def _block_entry(t, version):
		return t.record_null
	
	@staticmethod
	def _len_block_entry(t):
		return len(t.record_null)
	
class _MdxKeyBlock(_MdxBlock):
	# A class representing a key block.
	#
	# Has the ability to return (in the format suitable for insertion in an mdx file) 
	# both the block itself, as well as the entry in the record block index for that
	# block.
	def __init__(self, offset_table, compression_type, version):
		# Builds the data for offset_table.
		#
		# offset_table is a iterable containing _OffsetTableEntry objects.
		#
		# Only uses the key, key_len, key_null and offset fields, and effectively ignores record_null.

		_MdxBlock.__init__(self, offset_table, compression_type, version)
		self._num_entries = len(offset_table)
		if version=="2.0":
			self._first_key = offset_table[0].key_null
			self._last_key = offset_table[len(offset_table)-1].key_null
		else:
			self._first_key = offset_table[0].key
			self._last_key = offset_table[len(offset_table)-1].key
		self._first_key_len = offset_table[0].key_len
		self._last_key_len = offset_table[len(offset_table)-1].key_len
	
	@staticmethod
	def _block_entry(t, version):
		if version == "2.0":
			format = b">Q"
		else:
			format = b">L"
		return struct.pack(format, t.offset)+t.key_null
	
	@staticmethod
	def _len_block_entry(t):
		return 8 + len(t.key_null) #This is only accurate for version 2.0, but we only need approximate size anyway
	
	def get_index_entry(self):
		# Returns a bytes object, containing the header data for this block
		if self._version == "2.0":
			long_format = b">Q"
			short_format = b">H"
		else:
			long_format = b">L"
			short_format = b">B"
		return (
		    struct.pack(long_format, self._num_entries)
		  + struct.pack(short_format, self._first_key_len)
		  + self._first_key
		  + struct.pack(short_format, self._last_key_len)
		  + self._last_key
		  + struct.pack(long_format, self._comp_size)
		  + struct.pack(long_format, self._decomp_size)
		  )
		
	
	
		
