import beatplayer.routes 
    import cowpy                            -> `cowpy/.cowpyrc` 
    from jroutes.routing import responsify, authorize, route, context
        import cowpy
        logger = cowpy.getLogger()          -> `jroutes/.cowpyrc`
    from beatplayer.health import PlayerHealth
        import cowpy
        from .common.processmonitor import ProcessMonitor
            import cowpy
            logger = cowpy.getLogger()      -> `beatplayer/.cowpyrc`
        from .common.mpvsockettalker import PlayerNotRunningError
            import cowpy
            logger = cowpy.getLogger()      -> `beatplayer/.cowpyrc`
        logger_health = cowpy.getLogger()   -> `beatplayer/.cowpyrc`
        health_ping_loop_logger = cowpy.getLogger(f'{__name__}.health_ping_loop')           -> `beatplayer/.cowpyrc`
    from beatplayer.basewrapper import BaseWrapper 
        import cowpy
        from .common.processmonitor import ProcessMonitor
            import cowpy
            logger = cowpy.getLogger()      -> `beatplayer/.cowpyrc`
        from .common.lists import Fifo 
    logger = cowpy.getLogger()              -> `beatplayer/.cowpyrc`