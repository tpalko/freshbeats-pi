urls 

    from beater import views
    from beater.beatplayer import handlers as beatplayer_handlers
    from beater.freshbeats import freshbeats_client

views 

    from beater.beatplayer.health import BeatplayerRegistrar

health (views, player)

    from beater.beatplayer.client import BeatplayerClient

    #THREAD_C-2
    log_client_presence
        health.last_client_presence = get_localized_now()
        self.check_if_health_loop()
    
    #THREAD_C-3
    check_if_health_loop

        if there's an alive health loop thread, let it go 
        if there's a dead thread, clean it out 
        if not device.is_active, self.reassign_device() and return 
        replace the thread: new thread -> run_health_loop
    
    run_health_loop

        while True:
            - if device.health is not registered, we call the device in attempt to register it 
                if the device replies in the affirmative, we set the registered_at timestamp 
            - if device.health is registered, we look for reasons to invalidate that registration 
                - the last health report timestamp is old (timeout)
                - if the last health report is current, we make a health check call, and if that call fails 
                - there is no health report and it's been some time since registration 
            - break if 
                - we've iterated so many times 
                - device is not registered and in the last registration attempt response, the device explicitly said to not try again
                - device is not registered and we've attempted registration so many times 
        
        if the loop breaks, a finally block calls check_if_health_loop

    reassign_device: 
        called from 'check_if_health_loop' if not device.is_active
        called from device contextmanager after reconciling status not ready (not reachable AND mounted)
            - reachable is set after every device call 
                - device is called in run_health_loop and healthz 
            - mounted is set based on the healthz response, from a device context 
                - healthz is called for other devices within reassign_device                    
            - mounted is set while logging the health report from the device (but not in device context, does not trigger status reconcile)
        
        finds another device if necessary and tells the browser, which triggers device_select -> log_client_presence -> check_if_health_loop -> run_health_loop


client (health, player)
    import django
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../../webapp'))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
    django.setup()

-- end of urls views 

handlers 

    from .player import PlayerWrapper 
    from .health import BeatplayerRegistrar

    #THREAD_B-2
    player_status_and_state
        player.show_player_status()

    #THREAD_A-4
    register_client
        request.session['switchboard_connection_id'] = connection_id
        request.session['user_agent'] = user_agent 
    
    log_client_presence

player 

    from .playlist import Playlist, PlaylistHelper
    from .health import BeatplayerRegistrar (again)
    from from freshbeats import freshbeats, ingest.client import BeatplayerClient (again)

    #THREAD_B-3
    show_player_status 
        _publish_event(event='player_status', payload=json.dumps({
            'player': player_dump, 
            'current_song': current_song_html, 
            'playlist': playlist_html
        }), connection_id=connection_id)

base.html 

    include 'js/common/socketio_client.js'

    on ready 
        #THREAD_B-1
        $.ajax({
            url: '{% url "player_status_and_state" %}',
            type: 'GET',
            success: function(data, textStatus, jqXHR){}
        });

_player.js 

    on ready 
        device_select trigger 
        mobile_select trigger 
        log_client_presence interval 30s
    
    device_select 
        POST /device_select 
            log_client_presence

    mobile_select 
        POST mobile_select 
            log_client_presence

    #THREAD_C-1
    log_client_presence 
        POST log_client_presence 

socketio_client.js 

    #THREAD_A-1
    var socket = io.connect("http://{{socketio_host}}:{{socketio_port}}");

    connect_response
        
        #THREAD_A-3
        $.ajax({
            url: '{% url "register_client" %}',
            data: data,
            dataType: 'json',
            type: 'POST',
            success: function(data, textStatus, jqXHR) {      
                console.log('register client: ' + JSON.stringify(data));
            }, 
            error: function(jqXHR, textStatus, errorThrown) {
                console.error('register client error: ' + textStatus);
                console.error(errorThrown);
            }
        })

    player_status 

        - current song 
        - player controls
        - playlist 
        - volume
        - play time / percent 
    
switchboard 

    #THREAD_A-2
    sockets[socket.conn.id] = socket;
    socket.emit('connect_response', { 
        message: 'Socket.IO connection made', 
        connectionId: socket.conn.id, 
        userAgent: socket.handshake.headers['user-agent'], 
        remoteAddress: socket.client.conn.remoteAddress 
    });