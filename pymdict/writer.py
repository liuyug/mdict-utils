
import struct
import os.path
import locale

from tqdm import tqdm

from .base.writemdict import MDictWriter as MDictWriterBase, \
    _MdxRecordBlock as _MdxRecordBlockBase,  \
    _OffsetTableEntry as _OffsetTableEntryBase


class _OffsetTableEntry(_OffsetTableEntryBase):
    def __init__(self, key, key_null, key_len, offset, record_null, record_size):
        super(_OffsetTableEntry, self).__init__(key, key_null, key_len, offset, record_null)
        self.record_size = record_size


class _MdxRecordBlock(_MdxRecordBlockBase):
    def __init__(self, offset_table, compression_type, version):
        self._offset_table = offset_table
        self._compression_type = compression_type
        self._version = version

    def prepare(self, is_mdd):
        if is_mdd:
            for t in self._offset_table:
                t.record_null = open(t.record_null, 'rb').read()
        super(_MdxRecordBlock, self).__init__(self._offset_table, self._compression_type, self._version)

    @staticmethod
    def _len_block_entry(t):
        return t.record_size


class MDictWriter(MDictWriterBase):
    def _build_offset_table(self, d):
        items = sorted(d.items(), key=lambda x: locale.strxfrm(x[0]))

        self._offset_table = []
        offset = 0
        for key, record in items:
            key_enc = key.encode(self._python_encoding)
            key_null = (key + "\0").encode(self._python_encoding)
            key_len = len(key_enc) // self._encoding_length

            # set record_null to a the the value of the record. If it's
            # an MDX file, append an extra null character.
            if self._is_mdd:
                record_null = record['path']
            else:
                record_null = (record['path'] + "\0").encode(self._python_encoding)
                record['size'] += 1
            self._offset_table.append(_OffsetTableEntry(
                key=key_enc,
                key_null=key_null,
                key_len=key_len,
                record_null=record_null,
                record_size=record['size'],
                offset=offset,
            ))
            offset += record['size']
        self._total_record_len = offset

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
        index_pos = outfile.tell()
        outfile.write((struct.pack(index_format, 0, 0)) * len(self._record_blocks))

        recordblocks_total_size = 0
        recordb_index = []
        for b in self._record_blocks:
            b.prepare(self._is_mdd)
            recordblocks_total_size += len(b.get_block())
            recordb_index.append(b.get_index_entry())
            outfile.write(b.get_block())
            callback and callback(len(b._offset_table))
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
        outfile.seek(index_pos)
        outfile.write(self._recordb_index)
        outfile.seek(end_pos)

    def write(self, outfile, callback=None):
        self._write_header(outfile)
        self._write_key_sect(outfile)
        self._write_record_sect(outfile, callback=callback)


def pack(target, dictionary, title='', description='', is_mdd=False):
    def callback(value):
        bar.update(value)

    writer = MDictWriter(dictionary, title=title, description=description, is_mdd=is_mdd)
    bar = tqdm(total=len(writer._offset_table), unit='rec')
    outfile = open(target, "wb")
    writer.write(outfile, callback=callback)
    outfile.close()
    bar.close()


def pack_mdx_txt(source):
    dictionary = {}
    with open(source, 'rt') as f:
        key = None
        for line in f.readlines():
            line = line.strip()
            if line == '</>':
                key = None
                continue
            if not key:
                key = line
                continue
            dictionary[key] = {
                'path': line,
                'size': len(line),
            }
    return dictionary


def pack_mdd_file(source):
    dictionary = {}
    source = os.path.abspath(source)
    if os.path.isfile(source):
        size = os.path.getsize(source)
        key = '/' + os.path.basename(source)
        if os.sep == '\\':
            key.replace('\\', '/')
        dictionary[key] = {
            'path': source,
            'size': size,
        }
    else:
        relpath = source
        for root, dirs, files in os.walk(source):
            for f in files:
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                key = '/' + os.path.relpath(fpath, relpath)
                if os.sep == '\\':
                    key.replace('\\', '/')
                dictionary[key] = {
                    'path': fpath,
                    'size': size,
                }
    return dictionary
