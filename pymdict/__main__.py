import os.path
import argparse

from . import about
from . import reader
from .writer import pack, pack_mdd_file, pack_mdx_txt


def run():
    parser = argparse.ArgumentParser(prog='mdict', description=about.description)
    parser.add_argument('--version', action='version',
                        version='%%(prog)s version %s - written by %s <%s>' % (
                            about.version, about.author, about.email),
                        help='show version')
    parser.add_argument('--title', help='Dictionary title file')
    parser.add_argument('--description', help='Dictionary descritpion file')
    parser.add_argument('-k', dest='key', action='store_true', help='show mdx/mdd keys')
    parser.add_argument('-m', dest='meta', action='store_true', help='show mdx/mdd meta information')
    parser.add_argument('-q', dest='query', action='store_true', help='query KEY from mdx/mdd')
    parser.add_argument('mdict', metavar='<mdx/mdd>', help='Dictionary MDX/MDD file')

    group = parser.add_argument_group('Reader')
    group.add_argument('-x', dest='extract', action='store_true', help='extract mdx/mdd file.')
    group.add_argument('-d', dest='exdir', help='extracted directory')

    group = parser.add_argument_group('Writer')
    group.add_argument('-c', dest='create', action='store_true', help='create mdx/mdd file')
    group.add_argument('resource', nargs='*', help='Dictionary resource directory/file')

    args = parser.parse_args()

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
    elif args.query:
        qq = reader.query(args.mdict, args.query)
        for q in qq:
            print(q)
    elif args.extract:
        reader.unpack(args.exdir, args.mdict)
    elif args.create:
        is_mdd = args.mdict.endswith('.mdd')
        dictionary = []
        for resource in args.resource:
            print('Scan "%s"...' % resource)
            if is_mdd:
                d = pack_mdd_file(resource)
            else:
                d = pack_mdx_txt(resource)
            print('\tentry:', len(d))
            dictionary.extend(d)
        title = ''
        description = ''
        if args.title:
            title = open(args.title, 'rt').read()
        if args.description:
            description = open(args.description, 'rt').read()
        print('Pack to "%s"' % args.create)
        pack(args.mdict, dictionary, title, description, is_mdd=is_mdd)
    else:
        parser.print_help()


if __name__ == '__main__':
    run()
