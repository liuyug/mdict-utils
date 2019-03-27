import os.path
import argparse

from . import reader
from .writer import pack, pack_mdd_file, pack_mdx_txt


def run():
    parser = argparse.ArgumentParser(prog='pymdict', description='MDict Tools')
    parser.add_argument('FILE', metavar='<MDX/MDD>', help='mdx/mdd file')
    parser.add_argument('-k', dest='key', action='store_true', help='list mdx/mdd keys.')
    parser.add_argument('-m', dest='meta', action='store_true', help='print mdx/mdd meta information.')

    group = parser.add_argument_group('Reader')
    group.add_argument('-x', dest='extract', action='store_true', help='extract mdx/mdd file.')
    group.add_argument('-d', dest='exdir', help='extract directory')

    group = parser.add_argument_group('Writer')
    group.add_argument('-a', dest='add', action='append', help='add directory/files into mdx/mdd file.')
    group.add_argument('--title', help='title file')
    group.add_argument('--description', help='descritpion file')

    args = parser.parse_args()

    if args.meta:
        meta = reader.meta(args.FILE)
        print('Title: %(title)s' % meta)
        print('Engine Version: %(generatedbyengineversion)s' % meta)
        print('Record: %(record)s' % meta)
        print('Format: %(format)s' % meta)
        'encoding' in meta and print('Encoding: %(encoding)s' % meta)
        print('Creation Date: %(creationdate)s' % meta)
        print('Description: %(description)s' % meta)
    elif args.key:
        keys = reader.get_keys(args.FILE)
        count = 0
        for key in keys:
            count += 1
            key = key.decode('utf-8')
            print(key)
    elif args.extract:
        reader.unpack(args.exdir, args.FILE)
    elif args.add:
        is_mdd = args.FILE.endswith('.mdd')
        dictionary = []
        for a in args.add:
            print('Search "%s"...' % a)
            if is_mdd:
                d = pack_mdd_file(a)
            else:
                d = pack_mdx_txt(a)
            print('\tentry:', len(d))
            dictionary.extend(d)
        title = ''
        description = ''
        if args.title:
            title = open(args.title, 'rt').read()
        if args.description:
            description = open(args.description, 'rt').read()
        print('Pack to "%s"' % args.FILE)
        pack(args.FILE, dictionary, title, description, is_mdd=is_mdd)
    else:
        parser.print_help()


if __name__ == '__main__':
    run()
