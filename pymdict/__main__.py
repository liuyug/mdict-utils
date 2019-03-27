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
    parser.add_argument('-k', dest='key', metavar='<mdx/mdd>', help='show mdx/mdd keys')
    parser.add_argument('-m', dest='meta', metavar='<mdx/mdd>', help='show mdx/mdd meta information')
    parser.add_argument('-q', dest='query', metavar='<mdx/mdd>', help='query KEY from mdx/mdd')

    group = parser.add_argument_group('Reader')
    group.add_argument('-x', dest='extract', metavar='<mdx/mdd>', help='extract mdx/mdd file.')
    group.add_argument('-d', dest='exdir', help='extracted directory')

    group = parser.add_argument_group('Writer')
    group.add_argument('-c', dest='create', metavar='<mdx/mdd>', help='create mdx/mdd file')
    group.add_argument('resource', nargs='*', help='Dictionary resource directory/file')

    args = parser.parse_args()

    if args.meta:
        meta = reader.meta(args.meta)
        print('Title: %(title)s' % meta)
        print('Engine Version: %(generatedbyengineversion)s' % meta)
        print('Record: %(record)s' % meta)
        print('Format: %(format)s' % meta)
        'encoding' in meta and print('Encoding: %(encoding)s' % meta)
        print('Creation Date: %(creationdate)s' % meta)
        print('Description: %(description)s' % meta)
    elif args.key:
        keys = reader.get_keys(args.key)
        count = 0
        for key in keys:
            count += 1
            key = key.decode('utf-8')
            print(key)
    elif args.query:
        qq = reader.query(args.resource, args.query)
        for q in qq:
            print(q)
    elif args.extract:
        reader.unpack(args.exdir, args.extract)
    elif args.create:
        is_mdd = args.create.endswith('.mdd')
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
        pack(args.create, dictionary, title, description, is_mdd=is_mdd)
    else:
        parser.print_help()


if __name__ == '__main__':
    run()
