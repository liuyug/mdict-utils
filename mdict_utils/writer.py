
import re
import string
import sqlite3
import struct
import os.path
import functools
import locale
import zlib
import datetime
from html import escape

from tqdm import tqdm

from .base.writemdict import MDictWriter as MDictWriterBase, \
    _MdxRecordBlock as _MdxRecordBlockBase,  \
    _OffsetTableEntry as _OffsetTableEntryBase


MDICT_OBJ = {}


def get_record_null(mdict_file, key, pos, size, encoding, is_mdd):
    global MDICT_OBJ
    if mdict_file not in MDICT_OBJ:
        if mdict_file.endswith('.db'):
            conn = sqlite3.connect(mdict_file)
            MDICT_OBJ[mdict_file] = conn
        elif is_mdd:
            pass
        else:
            f = open(mdict_file, 'rb')
            MDICT_OBJ[mdict_file] = f
    obj = MDICT_OBJ.get(mdict_file)
    if is_mdd:
        if mdict_file.endswith('.db'):
            sql = 'SELECT file FROM mdd WHERE entry=?'
            c = obj.execute(sql, (key,))
            row = c.fetchone()
            record_null = row[0]
            return record_null
        else:
            assert(obj is None), 'MDD file error: %s' % mdict_file
            with open(mdict_file, 'rb') as f:
                return f.read()
    else:
        if mdict_file.endswith('.db'):
            sql = 'SELECT paraphrase FROM mdx WHERE entry=?'
            c = obj.execute(sql, (key,))
            for row in c.fetchall():    # multi entry
                record_null = (row[0] + '\0').encode(encoding)
                if len(record_null) == size:
                    return record_null
        else:
            assert size > 1, key
            obj.seek(pos)
            record_null = obj.read(size - 1)
            return record_null + b'\0'
    return b''


class _OffsetTableEntry(_OffsetTableEntryBase):
    def __init__(self, key0, key, key_null, key_len, offset,
                 record_pos, record_null, record_size, encoding, is_mdd):
        super(_OffsetTableEntry, self).__init__(
            key, key_null, key_len, offset, record_null)
        self.key0 = key0
        self.record_pos = record_pos
        self.record_size = record_size
        self.encoding = encoding
        self.is_mdd = is_mdd

    def get_record_null(self):
        return get_record_null(
            self.record_null, self.key0,
            self.record_pos, self.record_size, self.encoding, self.is_mdd)


class _MdxRecordBlock(_MdxRecordBlockBase):
    def __init__(self, offset_table, compression_type, version):
        self._offset_table = offset_table
        self._compression_type = compression_type
        self._version = version

    def prepare(self):
        super(_MdxRecordBlock, self).__init__(
            self._offset_table, self._compression_type, self._version)

    def clean(self):
        if self._comp_data:
            self._comp_data = None

    @staticmethod
    def _block_entry(t, version):
        return t.get_record_null()

    @staticmethod
    def _len_block_entry(t):
        return t.record_size


class MDictWriter(MDictWriterBase):
    def __init__(self, d, title, description,
                 key_size=32768, record_size=65536,
                 encrypt_index=False,
                 encoding="utf8",
                 compression_type=2,
                 version="2.0",
                 encrypt_key=None,
                 register_by=None,
                 user_email=None,
                 user_device_id=None,
                 is_mdd=False):
        self._key_block_size = key_size
        self._record_block_size = record_size
        # disable encrypt
        super(MDictWriter, self).__init__(
            d, title, description,
            block_size=record_size, encrypt_index=False,
            encoding=encoding, compression_type=compression_type, version=version,
            encrypt_key=None, register_by=None,
            user_email=None, user_device_id=None, is_mdd=is_mdd
        )

    def _build_offset_table(self, items):
        """One key own multi entry, so d is list"""
        def mdict_cmp(item1, item2):
            # sort following mdict standard
            key1 = item1['key'].lower()
            key2 = item2['key'].lower()
            if not self._is_mdd:
                key1 = regex_strip.sub('', key1)
                key2 = regex_strip.sub('', key2)
            # locale key
            key1 = locale.strxfrm(key1)
            key2 = locale.strxfrm(key2)
            if key1 > key2:
                return 1
            elif key1 < key2:
                return -1
            # reverse
            if len(key1) > len(key2):
                return -1
            elif len(key1) < len(key2):
                return 1
            key1 = key1.rstrip(string.punctuation)
            key2 = key2.rstrip(string.punctuation)
            if key1 > key2:
                return -1
            elif key1 < key2:
                return 1
            return 0

        pattern = '[%s ]+' % string.punctuation
        regex_strip = re.compile(pattern)

        items.sort(key=functools.cmp_to_key(mdict_cmp))

        self._offset_table = []
        offset = 0
        for record in items:
            key = record['key']
            key_enc = key.encode(self._python_encoding)
            key_null = (key + "\0").encode(self._python_encoding)
            key_len = len(key_enc) // self._encoding_length

            self._offset_table.append(_OffsetTableEntry(
                key0=record['key'],
                key=key_enc,
                key_null=key_null,
                key_len=key_len,
                record_null=record['path'],
                record_size=record['size'],
                record_pos=record['pos'],
                offset=offset,
                encoding=self._python_encoding,
                is_mdd=self._is_mdd,
            ))
            offset += record['size']
        self._total_record_len = offset

    def _build_key_blocks(self):
        # Sets self._key_blocks to a list of _MdxKeyBlocks.
        self._block_size = self._key_block_size
        super(MDictWriter, self)._build_key_blocks()
        self._block_size = self._record_block_size

    def _build_record_blocks(self):
        self._record_blocks = self._split_blocks(_MdxRecordBlock)

    def _build_recordb_index(self):
        pass

    def _write_record_sect(self, outfile, callback=None):
        # outfile: a file-like object, opened in binary mode.
        if self._version == "2.0":
            record_format = b">QQQQ"
            index_format = b">QQ"
        else:
            record_format = b">LLLL"
            index_format = b">LL"
        # fill ZERO
        record_pos = outfile.tell()
        outfile.write(struct.pack(record_format, 0, 0, 0, 0))
        outfile.write((struct.pack(index_format, 0, 0)) * len(self._record_blocks))

        recordblocks_total_size = 0
        recordb_index = []
        for b in self._record_blocks:
            b.prepare()
            recordblocks_total_size += len(b.get_block())
            recordb_index.append(b.get_index_entry())
            outfile.write(b.get_block())
            callback and callback(len(b._offset_table))
            b.clean()
        end_pos = outfile.tell()
        self._recordb_index = b''.join(recordb_index)
        self._recordb_index_size = len(self._recordb_index)
        # fill REAL value
        outfile.seek(record_pos)
        outfile.write(struct.pack(record_format,
                                  len(self._record_blocks),
                                  self._num_entries,
                                  self._recordb_index_size,
                                  recordblocks_total_size))
        outfile.write(self._recordb_index)
        outfile.seek(end_pos)

    def write(self, outfile, callback=None):
        self._write_header(outfile)
        self._write_key_sect(outfile)
        self._write_record_sect(outfile, callback=callback)

    def _write_header(self, f):
        # disable encrypt
        encrypted = "No"
        register_by_str = ""
        # regcode = ""

        if not self._is_mdd:
            header_string = (
                """<Dictionary """
                """GeneratedByEngineVersion="{version}" """
                """RequiredEngineVersion="{version}" """
                """Encrypted="{encrypted}" """
                """Encoding="{encoding}" """
                """Format="Html" """
                """Stripkey="Yes" """
                """CreationDate="{date.year}-{date.month}-{date.day}" """
                """Compact="Yes" """
                """Compat="Yes" """
                """KeyCaseSensitive="No" """
                """Description="{description}" """
                """Title="{title}" """
                """DataSourceFormat="106" """
                """StyleSheet="" """
                """Left2Right="Yes" """
                """RegisterBy="{register_by_str}" """
                # """RegCode="{regcode}" """
                """/>\r\n\x00"""
            ).format(
                version=self._version,
                encrypted=encrypted,
                encoding=self._encoding,
                date=datetime.date.today(),
                description=escape(self._description, quote=True),
                title=escape(self._title, quote=True),
                register_by_str=register_by_str,
                # regcode=regcode,
            ).encode("utf_16_le")
        else:
            header_string = (
                """<Library_Data """
                """GeneratedByEngineVersion="{version}" """
                """RequiredEngineVersion="{version}" """
                """Encrypted="{encrypted}" """
                """Encoding="" """
                """Format="" """
                """CreationDate="{date.year}-{date.month}-{date.day}" """
                # """Compact="No" """
                # """Compat="No" """
                """KeyCaseSensitive="No" """
                """Stripkey="No" """
                """Description="{description}" """
                """Title="{title}" """
                # """DataSourceFormat="106" """
                # """StyleSheet="" """
                """RegisterBy="{register_by_str}" """
                # """RegCode="{regcode}" """
                """/>\r\n\x00"""
            ).format(
                version=self._version,
                encrypted=encrypted,
                date=datetime.date.today(),
                description=escape(self._description, quote=True),
                title=escape(self._title, quote=True),
                register_by_str=register_by_str,
                # regcode=regcode
            ).encode("utf_16_le")
        f.write(struct.pack(b">L", len(header_string)))
        f.write(header_string)
        f.write(struct.pack(b"<L", zlib.adler32(header_string) & 0xffffffff))


def pack(target, dictionary, title='', description='',
         key_size=32768, record_size=65536, encoding='UTF-8', is_mdd=False):
    def callback(value):
        bar.update(value)

    writer = MDictWriter(
        dictionary, title=title, description=description,
        key_size=key_size, record_size=record_size,
        encoding=encoding, is_mdd=is_mdd,
    )
    bar = tqdm(total=len(writer._offset_table), unit='rec')
    outfile = open(target, "wb")
    writer.write(outfile, callback=callback)
    outfile.close()
    bar.close()


def txt2db(source, encoding='UTF-8', zip=False, callback=None):
    db_name = source + '.db'
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS mdx')
    if zip:
        c.execute('CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase GLOB NOT NULL)')
    else:
        c.execute('CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase TEXT NOT NULL)')
    max_batch = 1024 * 10
    sources = []
    if os.path.isfile(source):
        sources.append(source)
    else:
        sources.extend([os.path.join(source, f) for f in os.listdir(source) if f.endswith('.txt')])
    for source in sources:
        with open(source, 'rt', encoding=encoding) as f:
            count = 0
            entries = []
            key = None
            content = []
            count = 0
            for line in f:
                count += 1
                line = line.strip()
                if not line:
                    continue
                if line == '</>':
                    if not key or not content:
                        raise ValueError('Error at line %s' % count)
                    content = ''.join(content)
                    if zip:
                        content = zlib.compress(content.decode(encoding))
                    entries.append((key, content))
                    if count > max_batch:
                        c.executemany('INSERT INTO mdx VALUES (?,?)', entries)
                        conn.commit()
                        count = 0
                        entries = []
                    key = None
                    content = []
                    callback and callback(1)
                elif not key:
                    key = line
                    count += 1
                else:
                    content.append(line)
            if entries:
                c.executemany('INSERT INTO mdx VALUES (?,?)', entries)
                conn.commit()
        c.execute('CREATE INDEX entry_index ON mdx (entry)')
        conn.close()


def db2txt(source, encoding='UTF-8', zip=False, callback=None):
    mdx_txt = source + '.txt'
    with open(mdx_txt, 'wt', encoding=encoding) as f:
        sql = 'SELECT entry, paraphrase FROM mdx'
        with sqlite3.connect(source) as conn:
            cur = conn.execute(sql)
            for c in cur:
                f.write(c[0] + '\r\n')
                if zip:
                    value = zlib.decompress(c[1]).decode(encoding)
                else:
                    value = c[1]
                f.write(value + '\r\n')
                f.write('</>\r\n')
                callback and callback(1)


def pack_mdx_db(source, encoding='UTF-8', callback=None):
    dictionary = []
    sql = 'SELECT entry, paraphrase FROM mdx'
    with sqlite3.connect(source) as conn:
        cur = conn.execute(sql)
        for c in cur:
            dictionary.append({
                'key': c[0],
                'pos': 0,
                'path': source,
                'size': len((c[1] + '\0').encode(encoding)),
            })
            callback and callback(1)
    return dictionary


def pack_mdd_db(source, callback=None):
    dictionary = []
    sql = 'SELECT entry, LENGTH(file) FROM mdd'
    with sqlite3.connect(source) as conn:
        cur = conn.execute(sql)
        for c in cur:
            dictionary.append({
                'key': c[0],
                'pos': 0,
                'path': source,
                'size': c[1],
            })
            callback and callback(1)
    return dictionary


def pack_mdx_txt(source, encoding='UTF-8', callback=None):
    """return LIST data."""
    dictionary = []
    sources = []
    null_length = len('\0'.encode(encoding))
    if os.path.isfile(source):
        sources.append(source)
    else:
        sources.extend([os.path.join(source, f) for f in os.listdir(source) if f.endswith('.txt')])
    for source in sources:
        with open(source, 'rb') as f:
            key = None
            pos = 0
            offset = 0
            count = 0
            line = f.readline()
            while line:
                count += 1
                line = line.strip()
                if not line:
                    if not key:
                        raise ValueError('Error at line %s: %s' % (count, source))
                    line = f.readline()
                    continue
                if line == b'</>':
                    if not key or offset == pos:
                        raise ValueError('Error at line %s: %s' % (count, source))
                    # calculate content length including \r\n.
                    # readline will filter \r\n
                    size = offset - pos + null_length
                    dictionary.append({
                        'key': key.decode(encoding),
                        'pos': pos,
                        'path': source,
                        'size': size,
                    })
                    key = None
                    callback and callback(1)
                elif not key:
                    key = line
                    pos = f.tell()
                else:
                    offset = f.tell()

                line = f.readline()
    return dictionary


def pack_mdx_txt2(source, encoding='UTF-8'):
    """return DICT data. entry is key"""
    dictionary = {}
    sources = []
    if os.path.isfile(source):
        sources.append(source)
    else:
        sources.extend([os.path.join(source, f) for f in os.listdir(source) if f.endswith('.txt')])
    for source in sources:
        with open(source, 'rt', encoding=encoding) as f:
            key = None
            count = 0
            content = ''
            line = f.readline()
            while line:
                count += 1
                line = line.strip()
                if not line:
                    line = f.readline()
                    continue
                if line == '</>':
                    if not key:
                        raise ValueError('Error at line %s: %s' % (count, key))
                    dictionary[key] = content
                    key = None
                    content = ''
                elif not key:
                    key = line
                else:
                    content += line
                line = f.readline()
    return dictionary


def pack_mdd_file(source, callback=None):
    dictionary = []
    source = os.path.abspath(source)
    if os.path.isfile(source):
        size = os.path.getsize(source)
        key = '\\' + os.path.basename(source)
        if os.sep != '\\':
            key = key.replace(os.sep, '\\')
        dictionary.append({
            'key': key,
            'pos': 0,
            'path': source,
            'size': size,
        })
    else:
        relpath = source
        for root, dirs, files in os.walk(source):
            for f in files:
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                key = '\\' + os.path.relpath(fpath, relpath)
                if os.sep != '\\':
                    key = key.replace(os.sep, '\\')
                dictionary.append({
                    'key': key,
                    'pos': 0,
                    'path': fpath,
                    'size': size,
                })
                callback and callback(1)
    return dictionary
