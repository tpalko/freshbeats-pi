from ..basewrapper import BaseWrapper 
import os 

class main(BaseWrapper):
    
    player_path = "mplayer"
    
    def executable_filename():
        return main.player_path
    
    def _init(self):
        pass 
    
    def _command_generator(self, url, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        return command 
    
    def get_time(self):
        return (0, 0)    
    # exposed controls 
    
    def play(self, body, query):
        url = body['url']
        filepath = body['filepath']
        callback_url = body['callback_url']
        agent_base_url = body['agent_base_url']
        return self._issue_command(url, filepath, callback_url, agent_base_url)
    
    def stop(self):
        return self._send_to_process("stop")
        
    def pause(self):
        self.paused = not self.paused 
        return self._send_to_process("pause")

    def mute(self):
        self.muted = not self.muted
        return self._send_to_process("mute %s" % ("1" if self.muted else "0"))
    
    def set_volume(self):
        return self._send_to_process("volume %s 1" % self.volume)
