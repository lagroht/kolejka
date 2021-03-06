# vim:ts=4:sts=4:sw=4:expandtab

__import__('pkg_resources').declare_namespace('kolejka')

def main():
    import argparse
    import logging
    import setproctitle
    from kolejka.worker.stage0 import config_parser as stage0_parser
    from kolejka.worker.stage2 import config_parser as stage2_parser

    setproctitle.setproctitle('kolejka-worker')
    parser = argparse.ArgumentParser(description='KOLEJKA worker')
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help='show more info')
    parser.add_argument("-d", "--debug", action="store_true", default=False, help='show debug info')
    parser.add_argument('--config-file', help='config file')
    parser.add_argument('--config', help='config')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True
    subparser = subparsers.add_parser('execute')
    stage0_parser(subparser)
    subparser = subparsers.add_parser('stage2') #TODO: find proper name
    stage2_parser(subparser)
    args = parser.parse_args()
    level=logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(level = level)
    args.execute(args)

if __name__ == '__main__':
    main()
