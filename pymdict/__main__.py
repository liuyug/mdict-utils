import os.path
import argparse

from . import about
from . import reader
from .writer import pack, pack_mdd_file, pack_mdx_txt, pack_mdx_sqlite3,  \
    txt2sqlite, sqlite2txt


total = 0


def make_callback(fmt):
    def callback(value):
        global total
        total += value
        print(fmt % total, end='')
    return callback


def run():
    epilog = 'NOTE: MDict encoding is UTF-8 and format is version 2.0'
    parser = argparse.ArgumentParser(prog='mdict', description=about.description, epilog=epilog)
    parser.add_argument('--version', action='version',
                        version='%%(prog)s version %s - written by %s <%s>' % (
                            about.version, about.author, about.email),
                        help='show version')
    parser.add_argument('--title', help='Dictionary title file')
    parser.add_argument('--description', help='Dictionary descritpion file')
    parser.add_argument('-k', dest='key', action='store_true', help='show mdx/mdd keys')
    parser.add_argument('-m', dest='meta', action='store_true', help='show mdx/mdd meta information')
    parser.add_argument('-q', dest='query', action='store_true', help='query KEY from mdx/mdd')
    parser.add_argument('--txt-db', action='store_true', help='convert mdx txt to sqlite3 db')
    parser.add_argument('--db-txt', action='store_true', help='convert sqlite3 db to mdx txt')
    parser.add_argument('mdict', metavar='<mdx/mdd>', help='Dictionary MDX/MDD file')

    group = parser.add_argument_group('Reader')
    group.add_argument('-x', dest='extract', action='store_true', help='extract mdx/mdd file.')
    group.add_argument('-d', dest='exdir', help='extracted directory')

    group = parser.add_argument_group('Writer')
    group.add_argument('-c', dest='create', action='store_true', help='create mdx/mdd file')
    group.add_argument('--encoding', metavar='<encoding>', default='utf-8', help='mdx txt file encoding')
    group.add_argument('resource', nargs='*', help='Dictionary resource directory/file')

    args = parser.parse_args()

    global total

    if args.meta:
        meta = reader.meta(args.mdict)
        print('Title: %(title)s' % meta)
        print('Engine Version: %(generatedbyengineversion)s' % meta)
        print('Record: %(record)s' % meta)
        print('Format: %(format)s' % meta)
        'encoding' in meta and print('Encoding: %(encoding)s' % meta)
        print('Creation Date: %(creationdate)s' % meta)
        print('Description: %(description)s' % meta)
    elif args.key:
        keys = reader.get_keys(args.mdict)
        count = 0
        for key in keys:
            count += 1
            key = key.decode('utf-8')
            print(key)
    elif args.txt_db:
        total = 0
        fmt = '\rConvert "%s": %%s' % args.mdict
        txt2sqlite(args.mdict, callback=make_callback(fmt))
        print()
    elif args.db_txt:
        total = 0
        fmt = '\rConvert "%s": %%s' % args.mdict
        sqlite2txt(args.mdict, callback=make_callback(fmt))
        print()
    elif args.query:
        qq = reader.query(args.mdict, args.resource)
        for q in qq:
            print(q)
    elif args.extract:
        reader.unpack(args.exdir, args.mdict)
    elif args.create:
        is_mdd = args.mdict.endswith('.mdd')
        dictionary = []
        for resource in args.resource:
            fmt = '\rScan "%s": %%s' % resource
            total = 0
            if is_mdd:
                d = pack_mdd_file(resource, callback=make_callback(fmt))
            elif resource.endswith('.db'):
                d = pack_mdx_sqlite3(resource, encoding=args.encoding, callback=make_callback(fmt))
            else:
                d = pack_mdx_txt(resource, encoding=args.encoding, callback=make_callback(fmt))
            dictionary.extend(d)
        print()
        title = ''
        description = ''
        if args.title:
            title = open(args.title, 'rt').read()
        if args.description:
            description = open(args.description, 'rt').read()
        print('Pack to "%s"' % args.mdict)
        pack(args.mdict, dictionary, title, description, encoding=args.encoding, is_mdd=is_mdd)
    else:
        parser.print_help()


if __name__ == '__main__':
    run()
