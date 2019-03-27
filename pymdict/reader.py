
import os.path

from tqdm import tqdm

from .base.readmdict import MDX, MDD


def meta(source, encoding='utf-8', substyle=False, passcode=None):
    meta = {}
    if source.endswith('.mdx'):
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


def get_keys(source, encoding='utf-8', substyle=False, passcode=None):
    if source.endswith('.mdx'):
        md = MDX(source, encoding, substyle, passcode)
    if source.endswith('.mdd'):
        md = MDD(source, passcode)
    return md.keys()


def unpack(target, source, encoding='utf-8', substyle=False, passcode=None):
    if not os.path.exists(target):
        os.makedirs(target)
    if source.endswith('.mdx'):
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
        mdd = MDD(source, passcode)
        bar = tqdm(total=len(mdd), unit='rec')
        datafolder = os.path.join(target, 'mdd')
        if not os.path.exists(datafolder):
            os.makedirs(datafolder)
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
