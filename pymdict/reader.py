
import struct
import os.path
import zlib

from tqdm import tqdm

from .base.readmdict import MDX, MDD


def meta(source, substyle=False, passcode=None):
    meta = {}
    if source.endswith('.mdx'):
        encoding = ''
        md = MDX(source, encoding, substyle, passcode)
    if source.endswith('.mdd'):
        md = MDD(source, passcode)
    meta['version'] = md._version
    meta['record'] = len(md)
    for key, value in md.header.items():
        key = key.decode('utf-8').lower()
        value = value.decode('utf-8')
        meta[key] = value
    return meta


def get_keys(source, substyle=False, passcode=None):
    if source.endswith('.mdx'):
        encoding = ''
        md = MDX(source, encoding, substyle, passcode)
    if source.endswith('.mdd'):
        md = MDD(source, passcode)
    return md.keys()


def get_record(md, key, offset):
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
        header = b'\xf0' + struct.pack('>I', decompressed_size)
        record_block = lzo.decompress(header + block_compressed[8:])
    # zlib compression
    elif block_type == b'\x02\x00\x00\x00':
        # decompress
        record_block = zlib.decompress(block_compressed[8:])
    # notice that adler32 return signed value
    assert(adler32 == zlib.adler32(record_block) & 0xffffffff)
    assert(len(record_block) == decompressed_size)

    record_start = offset - decompressed_offset
    record_end = record_start + decompressed_size
    record_null = record_block[record_start:record_end]
    record = record_null.strip().decode('utf-8')

    f.close()
    return record


def query(source, words, substyle=False, passcode=None):
    if source.endswith('.mdx'):
        encoding = ''
        md = MDX(source, encoding, substyle, passcode)
    if source.endswith('.mdd'):
        md = MDD(source, passcode)
    words = [word.encode('utf-8') for word in words]
    for word in words:
        record = []
        for offset, key in md._key_list:
            if word == key:
                record.append(get_record(md, key, offset))
        yield '\n---\n'.join(record)


def unpack(target, source, substyle=False, passcode=None):
    target = target or './'
    if not os.path.exists(target):
        os.makedirs(target)
    if source.endswith('.mdx'):
        encoding = ''
        mdx = MDX(source, encoding, substyle, passcode)
        bar = tqdm(total=len(mdx), unit='rec')
        basename = os.path.basename(source)
        output_fname = os.path.join(target, basename + '.txt')
        tf = open(output_fname, 'wb')
        for key, value in mdx.items():
            tf.write(key)
            tf.write(b'\r\n')
            tf.write(value)
            if not value.endswith(b'\n'):
                tf.write(b'\r\n')
            tf.write(b'</>\r\n')
            bar.update(1)
        tf.close()
        bar.close()
        # write header
        if mdx.header.get(b'StyleSheet'):
            style_fname = os.path.join(target, basename + '.css')
            sf = open(style_fname, 'wb')
            sf.write(b'\r\n'.join(mdx.header[b'StyleSheet'].splitlines()))
            sf.close()
        # write description
        if mdx.header.get(b'Description'):
            fname = os.path.join(target, basename + '.description.html')
            f = open(fname, 'wb')
            f.write(b'\r\n'.join(mdx.header[b'Description'].splitlines()))
            f.close()
        if mdx.header.get(b'Title'):
            fname = os.path.join(target, basename + '.title.txt')
            f = open(fname, 'wb')
            f.write(mdx.header[b'Title'])
            f.close()
    elif source.endswith('.mdd'):
        datafolder = os.path.abspath(target)
        if not os.path.exists(datafolder):
            os.makedirs(datafolder)
        mdd = MDD(source, passcode)
        bar = tqdm(total=len(mdd), unit='rec')
        for key, value in mdd.items():
            fname = key.decode('utf-8').replace('\\', os.path.sep)
            dfname = datafolder + fname
            if not os.path.exists(os.path.dirname(dfname)):
                os.makedirs(os.path.dirname(dfname))
            df = open(dfname, 'wb')
            df.write(value)
            df.close()
            bar.update(1)
        bar.close()
