
import sqlite3
import struct
import os.path
import zlib

from tqdm import tqdm

from .base.readmdict import MDX, MDD
from .chtml import CompactHTML


def meta(source, substyle=False, passcode=None):
    meta = {}
    if source.endswith('.db'):
        with sqlite3.connect(source) as conn:
            c = conn.execute('SELECT * FROM meta')
            for row in c.fetchall():
                meta[row[0]] = row[1]
    else:
        if source.endswith('.mdx'):
            encoding = ''
            md = MDX(source, encoding, substyle, passcode)
        if source.endswith('.mdd'):
            md = MDD(source, passcode)
        meta['version'] = md._version
        meta['record'] = len(md)
        for key, value in md.header.items():
            # key has been decode from UTF-16 and encode again with UTF-8
            key = key.decode('UTF-8').lower()
            value = value.decode('UTF-8')
            meta[key] = value
    return meta


def get_keys(source, substyle=False, passcode=None):
    if source.endswith('.db'):
        with sqlite3.connect(source) as conn:
            c = conn.execute('SELECT entry FROM mdx')
            for row in c.fetchall():
                yield row[0]
            c = conn.execute('SELECT entry FROM mdd')
            for row in c.fetchall():
                yield row[0]
    else:
        if source.endswith('.mdx'):
            encoding = ''
            md = MDX(source, encoding, substyle, passcode)
        if source.endswith('.mdd'):
            md = MDD(source, passcode)
        for k in md.keys():
            yield k.decode('UTF-8')


def get_record(md, key, offset, length):
    f = open(md._fname, 'rb')
    f.seek(md._record_block_offset)

    num_record_blocks = md._read_number(f)
    num_entries = md._read_number(f)
    assert(num_entries == md._num_entries)
    record_block_info_size = md._read_number(f)
    # record_block_size =
    md._read_number(f)

    # record block info section
    compressed_offset = f.tell() + record_block_info_size
    decompressed_offset = 0
    for i in range(num_record_blocks):
        compressed_size = md._read_number(f)
        decompressed_size = md._read_number(f)
        if (decompressed_offset + decompressed_size) > offset:
            break
        decompressed_offset += decompressed_size
        compressed_offset += compressed_size

    f.seek(compressed_offset)
    block_compressed = f.read(compressed_size)
    block_type = block_compressed[:4]
    adler32 = struct.unpack('>I', block_compressed[4:8])[0]
    # no compression
    if block_type == b'\x00\x00\x00\x00':
        record_block = block_compressed[8:]
    # lzo compression
    elif block_type == b'\x01\x00\x00\x00':
        # LZO compression is used for engine version < 2.0
        try:
            from .base import lzo
        except ImportError:
            lzo = None
            print("LZO compression support is not available")
            return
        # decompress
        # standard lzo (python-lzo) of c version
        # header = b'\xf0' + struct.pack('>I', decompressed_size)
        # record_block = lzo.decompress(header + block_compressed[8:])
        # lzo of python version, no header!!!
        record_block = lzo.decompress(block_compressed[8:], initSize=decompressed_size, blockSize=1308672)
    # zlib compression
    elif block_type == b'\x02\x00\x00\x00':
        # decompress
        record_block = zlib.decompress(block_compressed[8:])
    # notice that adler32 return signed value
    assert(adler32 == zlib.adler32(record_block) & 0xffffffff)
    assert(len(record_block) == decompressed_size)

    record_start = offset - decompressed_offset
    if length > 0:
        record_null = record_block[record_start:record_start + length]
    else:
        record_null = record_block[record_start:]
    f.close()
    if md._fname.endswith('.mdd'):
        return record_null
    else:
        return record_null.strip().decode(md._encoding)


def query(source, word, substyle=False, passcode=None):
    record = []
    if source.endswith('.db'):
        with sqlite3.connect(source) as conn:
            c = conn.execute('SELECT * FROM mdx WHERE entry=?', (word, ))
            for row in c.fetchall():
                record.append(row[1])
            if not record:
                c = conn.execute('SELECT * FROM mdd WHERE entry=?', (word, ))
                for row in c.fetchall():
                    return row[1]
    else:
        if source.endswith('.mdx'):
            encoding = ''
            md = MDX(source, encoding, substyle, passcode)
        if source.endswith('.mdd'):
            md = MDD(source, passcode)
        word = word.encode('UTF-8')
        for x in range(len(md._key_list)):
            offset, key = md._key_list[x]
            if word == key:
                if (x + 1) < len(md._key_list):
                    length = md._key_list[x + 1][0] - offset
                else:
                    length = -1
                record.append(get_record(md, key, offset, length))
        if md._fname.endswith('.mdd'):
            if record:
                return record[0]
    return '\n---\n'.join(record)


def unpack(target, source, split=None, convert_chtml=False, substyle=False, passcode=None):
    target = target or './'
    if not os.path.exists(target):
        os.makedirs(target)
    if source.endswith('.mdx'):
        encoding = ''
        mdx = MDX(source, encoding, substyle, passcode)
        bar = tqdm(total=len(mdx), unit='rec')
        basename = os.path.basename(source)
        # write header
        chtml_converter = None
        if convert_chtml and mdx.header.get(b'StyleSheet'):
            style_fname = os.path.join(target, basename + '.stylesheet')
            sf = open(style_fname, 'wb')
            b_content = b'\r\n'.join(mdx.header[b'StyleSheet'].splitlines())
            sf.write(b_content)
            sf.close()
            chtml_converter = CompactHTML(b_content)
        # write description
        if mdx.header.get(b'Description'):
            fname = os.path.join(target, basename + '.description.html')
            f = open(fname, 'wb')
            f.write(b'\r\n'.join(mdx.header[b'Description'].splitlines()))
            f.close()
        if mdx.header.get(b'Title'):
            # MDX will be unpacked as TXT, rename to HTML
            fname = os.path.join(target, basename + '.title.html')
            f = open(fname, 'wb')
            f.write(mdx.header[b'Title'])
            f.close()

        # content
        out_objs = {}
        if not split:       # no split
            part = len(mdx)
            out_fname = os.path.join(target, basename + '.txt')
            tf = open(out_fname, 'wb')
            out_objs['all'] = tf
        elif split == 'az':
            import string
            for c in string.ascii_lowercase:
                out_fname = os.path.join(target, '%s.%s.txt' % (basename, c))
                tf = open(out_fname, 'wb')
                out_objs[c] = tf
            out_fname = os.path.join(target, '%s.other.txt' % (basename))
            tf = open(out_fname, 'wb')
            out_objs['other'] = tf
        elif split.isdigit():
            part = len(mdx) // int(split) + 1
            for x in range(int(split)):
                out_fname = os.path.join(target, '%s.part%02d.txt' % (basename, x + 1))
                tf = open(out_fname, 'wb')
                out_objs[x + 1] = tf
        else:
            raise ValueError('split value: %s' % split)
        item_count = 0
        part_count = 1
        for key, value in mdx.items():
            if not value.strip():
                bar.write('Skip entry: %s' % key)
                continue
            item_count += 1
            if not split:
                tf = out_objs.get('all')
            elif split == 'az':
                k = key.decode().lower()
                tf = out_objs.get(k[0], out_objs['other'])
            elif split.isdigit():
                if item_count % part == 0:
                    part_count += 1
                tf = out_objs.get(part_count)
            tf.write(key)
            tf.write(b'\r\n')
            if convert_chtml and chtml_converter:
                value = chtml_converter.to_html(value)
            tf.write(value)
            if not value.endswith(b'\n'):
                tf.write(b'\r\n')
            tf.write(b'</>\r\n')
            bar.update(1)
        bar.close()
        for obj in out_objs.values():
            obj.close()
    elif source.endswith('.mdd'):
        datafolder = os.path.abspath(target)
        if not os.path.exists(datafolder):
            os.makedirs(datafolder)
        mdd = MDD(source, passcode)
        bar = tqdm(total=len(mdd), unit='rec')
        for key, value in mdd.items():
            fname = key.decode('UTF-8').replace('\\', os.path.sep)
            dfname = datafolder + fname
            if not os.path.exists(os.path.dirname(dfname)):
                os.makedirs(os.path.dirname(dfname))
            df = open(dfname, 'wb')
            df.write(value)
            df.close()
            bar.update(1)
        bar.close()


def unpack_to_db(target, source, encoding='', substyle=False, passcode=None, zip=True):
    target = target or './'
    if not os.path.exists(target):
        os.makedirs(target)
    name, _ = os.path.splitext(os.path.basename(source))
    db_name = os.path.join(target, name + '.db')
    with sqlite3.connect(db_name) as conn:
        if source.endswith('.mdx'):
            mdx = MDX(source, encoding, substyle, passcode)

            conn.execute('DROP TABLE IF EXISTS meta')
            conn.execute('CREATE TABLE meta (key TEXT NOT NULL, value TEXT NOT NULL)')
            meta = {}
            for key, value in mdx.header.items():
                key = key.decode(mdx._encoding).lower()
                value = '\r\n'.join(value.decode(mdx._encoding).splitlines())
                meta[key] = value
            meta['zip'] = zip
            conn.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
            conn.commit()

            conn.execute('DROP TABLE IF EXISTS mdx')
            if zip:
                conn.execute('CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase BLOB NOT NULL)')
            else:
                conn.execute('CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase TEXT NOT NULL)')

            bar = tqdm(total=len(mdx), unit='rec')
            max_batch = 1024
            count = 0
            entries = []
            for key, value in mdx.items():
                if not value.strip():
                    continue
                count += 1
                key = key.decode(mdx._encoding)
                if zip:
                    value = zlib.compress(value)
                else:
                    value = value.decode(mdx._encoding)
                entries.append((key, value))
                if count > max_batch:
                    conn.executemany('INSERT INTO mdx VALUES (?,?)', entries)
                    conn.commit()
                    count = 0
                    entries = []
                bar.update(1)
            if entries:
                conn.executemany('INSERT INTO mdx VALUES (?,?)', entries)
                conn.commit()
            bar.close()
            conn.execute('CREATE INDEX mdx_entry_index ON mdx (entry)')

        elif source.endswith('.mdd'):
            conn.execute('DROP TABLE IF EXISTS mdd')
            conn.execute('CREATE TABLE mdd (entry TEXT NOT NULL, file BLOB NOT NULL)')
            mdd = MDD(source, passcode)
            bar = tqdm(total=len(mdd), unit='rec')
            max_batch = 1024 * 1024 * 10
            count = 0
            for key, value in mdd.items():
                count += len(value)
                key = key.decode('UTF-8').lower()
                conn.execute('INSERT INTO mdd VALUES (?,?)', (key, value))
                if count > max_batch:
                    conn.commit()
                    count = 0
                bar.update(1)
            conn.commit()
            conn.execute('CREATE INDEX mdd_entry_index ON mdd (entry)')
            bar.close()
