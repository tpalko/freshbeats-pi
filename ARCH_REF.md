## model 

    Device : an agent 
        - agent URL 
        - player 
        - health 
        - is active

    DeviceHealth : health component of a device
        - registration time 
        - last device health report (notably not respective of any particular client, but the latest presence of any client concerned with this device)
        - status
        - reachable / mounted
        - last client presence 

    Player : state of the UI player 
        * as this is updated and saved in the course of app usage, a new record will be created with the old as its parent reflecting state changes 
        - play status
        - volume
        - playlist song
        - play position
        - shuffle/repeat/mute state
        - beatplayer agent status snapshot

    Session 

    Player records are continually appended, tracking state changes. Between Device and Player, Device is the entity that has actual real-world state, and so selecting 
    a Device will drive the UI display, reflecting the Device's Player information to any browser window. In this way, the Player records are a threaded timeline
    per Device. It only makes sense to look at Player records as children of Devices, and each Device should always point to the latest Player record in its history.
    DeviceHealth, in contrast, is a single state record representing health attributes of a Device. 


session 
    device_id 

## Loops and threads 

Loop init steps:
    browser -> server
    browser -> switchboard (init health loop from switchboard)
    (init presence loop from browser) browser -> server (init registration loop to beatplayer) -> beatplayer (init health loop from beatplayer)

Resulting call loops (caller -> callee):
    browser 
        -> server (javascript interval to refresh client presence timestamp)
    server 
        -> beatplayer (ensuring that the server has a current registration with every device that any browser is concerned with)
    beatplayer 
        -> server (health reports back to the server to be broadcast to any concerned browser)
    switchboard 
        -> browser (health reports directly to any concerned browser)

Reasonable logging threads:
    webapp
        django runserver
        registration loop
        beatplayer health report
    beatplayer
        beatplayer output
        health report client ping
        media player process and output monitoring


Resulting threads:
    webapp
        threading
            - any call via freshbeats client (check plan, apply plan, etc.)
            - health loop registration check
    beatplayer
        threading
            - client health report ping
            - play call (synchronous, why threading here?)
            - socket reader/watcher
            - media play process reporter
                - media play process output stream reader
        popen
            - "can play" check
            - "is music folder mounted" check
            - mpv init call to create socket file
            - media player call 

## page load

Page load connects with switchboard which sets up a health ping from switchboard to the server, sets device and mobile selections on the session, and 
triggers a registration with beatplayer which sets up a health ping from beatplayer to the server. The beatplayer registration is itself a loop which ensures the beatplayer registration is renewed as long as the client (browser) has recent presence, and the health ping from beatplayer will die on its own if the call fails too many times. Browser presence is another ping loop that runs as long as the window is open. Both health pings to the server are forwarded through switchboard to the browser for status icon updates.

### action: browser loads

    - beatplayer.handlers
        device_select: sets device_id on session 
        mobile_select: sets mobile_id on session 

    - monitoring.monitor_handlers
        register_client: stores the user agent and switchboard connection id of the client in session 
        log_client_presence
            - fetches Device based on session data
            - instantiates a BeatplayerHealth for the Device
            - calls log_client_presence() on BeatplayerHealth 

on interval from page (30 seconds)
    - log_client_presence 

BeatplayerHealth.log_client_presence()
    in DeviceHealth context
        - set DeviceHealth.last_client_presence 
    check_if_health_loop()

BeatplayerHealth.check_if_health_loop()
    in read-only Device context
        if Device is active and DeviceHealth.last_client_presence is recent
            start a thread on BeatplayerHealth._run_health_loop()

BeatplayerHealth._run_health_loop()
    in Device context 
        if DeviceHealth has a registration timestamp
            nullify registration if no recent last contact (last_device_health_report), Device is not healthy or the registration (registered_at) is too old
        otherwise
            call the Device to register it

## health call sub-nest

Once the browser triggers a beatplayer registration from the server, this loop runs continually until a browser presence is no longer detected.

entrypoints to health loop
    - log_client_presence -> check_if_health_loop
    - any read/write device context when status != ready -> _reassign_device -> _healthz (other devices)

monitor_handlers.py
    log_client_presence
        check_if_health_loop

health.py
    device()
        if not read only and not ready
            _reassign_device
    _healthz
        with device:
            _call_agent: health_check_only    
    _reassign_device
        with device: (read only, only to know session device ID)
            _healthz (other devices)
    _call_agent
        health_check_only: client healthz
        full: register_client
    check_if_health_loop
        with device: (read only)
            _reassign_device
    _run_health_loop
        with device:
            _call_agent: health_check_only
            _call_agent: full
        check_if_health_loop

## About Device Registration

    A beatplayer agent (Device) has a registration endpoint that, when called with a callback URL, will register and ping that URL on an interval with health reports.
    From the point of view of the web app, a Device registration is signing the web app up to receive health reports so it can update browser clients.
    The web app will attempt to re-register if the registration is voided for any reason but only if the Device is "active" (a user flag) and there is recent activity 
    from a browser session looking at that Device.
    From the point of view of the Device itself, if the health report posts back to the web app fail too many times, the registration is cancelled from its end and the URL is forgotten.
    


## play call 

    beatplayer.handlers.player()
        get Device based on session 
        get playlist ID based on session 
        get PlayerWrapper instance for device 
        PlayerWrapper.call('play')

PlayerWrapper.call()
    in Player(playlist_id) context 
        PlayerWrapper.play(Player)

PlayerWrapper.play(player)
    parse kwargs
    PlayerWrapper._beatplayer_play(player)    

PlayerWrapper._beatplayer_play(player)
    get player.playlistsong.song 
    beatplayer_client.play(song.url, callback URL, device URL)
    player.state = Playing

BeatplayerClient.play() -> POST /play

routes.play()
    get BaseWrapper instance (player)
    start a thread on player.issue_command
    join thread 

BaseWrapper.issue_command()
    acquire lock
    exchange passed-in command args for earliest entry on FIFO command queue 
    validate filepath
    if valid
        generate command string 
        issue BeatPlayer.stop() repeatedly until not is_playing()
        open command process
        get ProcessMonitor instance
        pass command process to ProcessMonitor.process()
        set BaseWrapper.current_command
    release lock 

BeatPlayer.stop()
    ...

ProcessMonitor.process()
    ...


## beatplayer health report thread 

device_health_report
    BeatplayerHealth.log_device_health_report()
    PlayerWrapper.parse_state()

BeatplayerHealth.log_device_health_report():
    in devicehealth context:
        set mounted, last_device_health_report 

PlayerWrapper.parse_state()
    in player context:
        parse health data
        set player properties
        publish 'clear_player_output' to switchboard


    