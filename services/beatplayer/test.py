#!/home/debian/tpalko/.virtualenv/freshbeats-beatplayer/bin/python

if __name__ == "__main__":

    import cowpy

    logger_player = cowpy.getLogger()

    from optparse import OptionParser
    from beatplayer.mpplayer import MPPlayer
    import traceback 

    parser = OptionParser(usage='usage: %prog [options]')

    parser.add_option("-a", "--address", dest="address", default='0.0.0.0', help="IP address on which to listen")
    parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")
    parser.add_option("-t", "--smoke-test", action="store_true", dest="smoke_test", help="Smoke test")
    parser.add_option("-f", "--filepath", dest="filepath", help="Play file")
    parser.add_option("-e", "--player-executable", dest="executable", default='mpv', help="The executable program to play file")

    (options, args) = parser.parse_args()

    logger_player.debug("Options: %s" % options)

    if options.smoke_test:
        try:
            play_test_filepath = options.filepath if options.filepath else os.path.basename(sys.argv[0])
            logger_player.info("Running smoke test with %s playing %s" % (options.executable, play_test_filepath))
            m = MPPlayer(player=options.executable)
            m.play(filepath=play_test_filepath)
        except:
            logger_player.error(str(sys.exc_info()[0]))
            logger_player.error(str(sys.exc_info()[1]))
            traceback.print_tb(sys.exc_info()[2])
    elif options.filepath:
        try:
            m = MPPlayer(player=options.executable)
            result = m.play(filepath=options.filepath)
        except:
            logger_player.error(str(sys.exc_info()[0]))
            logger_player.error(str(sys.exc_info()[1]))
            traceback.print_tb(sys.exc_info()[2])
    else:

        p = MPPlayer(player='mpv')
        p.serve()

