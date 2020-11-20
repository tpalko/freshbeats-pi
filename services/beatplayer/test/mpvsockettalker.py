#!/usr/bin/env python 

import logging
import os
import sys
import time 
import traceback 

sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), ".."))
sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), "..", "beatplayer"))
from beatplayer.common.mpvsockettalker import MpvSocketTalker 
from beatplayer.wrappers import BaseWrapper, MPVWrapper

logging.basicConfig(
    format='[ %(levelname)7s ] %(asctime)s %(name)-17s %(filename)s:%(lineno)-4d %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def test(talker):
    '''
        - send to socket 
        - read from socket / populate response queue 
        - search response queue by request_id 
    '''
    
    logger.debug("TEST: Creating player wrapper")
    player = BaseWrapper.getInstance(MPVWrapper)
    logger.debug("TEST: Playing..")
    player.play(os.path.join("Green Day", "Dookie", "Green Day_Dookie_06_Pulling Teeth.mp3"))    
    time.sleep(3)
    
    logger.debug("TEST: Sending get_property command for volume..")
    send_command = { 'command': [ "get_property", "volume" ] }
    request_id = talker._send(send_command)
    logger.debug("TEST: Sent: %s" % send_command)
    logger.debug("TEST:   - request_id: %s" % request_id)
    
    try:
        logger.debug("TEST: Receiving data..")
        talker._recv_socket_output()
        logger.debug("TEST: Received data")
        logger.debug("TEST:   - data: %s" % talker.data)
        
        #talker.data = '{"data":false,"error":"success"}\n{"event":"audio-reconfig"}\n{"event":"tracks-changed"}\n{"event":"end-file"}\n'
        logger.debug("TEST: Parsing data into queue..")
        talker._output_into_queue()
        logger.debug("TEST: Queue contents: %s" % talker.response_queue)
        
        logger.debug("TEST: Reading response of request ID %s.." % request_id)
        response = talker._read(request_id)
        logger.debug("TEST: Response: %s" % response)
    except:
        logger.error("Failed to do something")
        logger.error(sys.exc_info()[0])
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])
    
    player.stop()

if __name__ == "__main__":
    
    t = MpvSocketTalker.getInstance(socket_file='/tmp/mpv.sock', log_level='DEBUG')
    test(t)
        
