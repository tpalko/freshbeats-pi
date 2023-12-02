import logging 
import logging 
from beater.models import Log 
from pytz import timezone
from datetime import datetime 

UTC = timezone("UTC")

# logger = logging.getLogger()

class DatabaseHandler(logging.Handler):

    def handle(self, record):


        log = Log(
            levelname = record.levelname,
            levelno = record.levelno,
            lineno = record.lineno,
            message = record.message,
            asctime = UTC.localize(datetime.strptime(record.asctime, "%Y-%m-%d %H:%M:%S,%f")),
            processName = record.processName,
            funcName = record.funcName,
            name = record.name,            
            pathname = record.pathname
        )
        log.save()
        # print(record.__class__)
        # Log.objects.create(**record)
        
        '''
         <LogRecord: beater.models, 10, /media/storage/development/github.com/freshbeats-pi/webapp/beater/models.py, 37, "beater.Device.objects">
         
         ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', 
         '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', 
         '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', 
         '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', 
         '__str__', '__subclasshook__', '__weakref__', 
         
         'args', 'asctime', 'created', 
         'exc_info', 'exc_text', 'filename', 'funcName', 'getMessage', 'levelname', 
         'levelno', 'lineno', 'message', 'module', 'msecs', 'msg', 'name', 'pathname', 
         'process', 'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName']
         
         '''
        # 
        # from logging import LogRecord

        # print(record)
        # print(type(record))
        # for p in [ r for r in dir(record) if r[0] != '_' ]:
        #     val = getattr(record, p)
        #     print(f'{p} = {val} ({type(val)})')
        # 
        #     args = () (<class 'tuple'>)
        #     stack_info = None (<class 'NoneType'>)
        #     exc_info = None (<class 'NoneType'>)
        #     exc_text = None (<class 'NoneType'>)
        # 
        # 
        #     levelname = DEBUG (<class 'str'>)
        #     levelno = 10 (<class 'int'>)
        #     message = beater.Playlist.objects (<class 'str'>)
        #     asctime = 2022-02-26 01:04:15,301 (<class 'str'>)
        #     processName = MainProcess (<class 'str'>)
        #     funcName = get_queryset (<class 'str'>)
        #     name = beater.models (<class 'str'>)
        #     lineno = 37 (<class 'int'>)
        #     pathname = /media/storage/development/github.com/freshbeats-pi/webapp/beater/models.py (<class 'str'>)
        # 
        # 
        #     filename = models.py (<class 'str'>)
        #     module = models (<class 'str'>)
        # 
        #     relativeCreated = 4011.615514755249 (<class 'float'>)
        #     threadName = Thread-1 (<class 'str'>)
        #     created = 1645837455.301167 (<class 'float'>)
        #     msecs = 301.1670112609863 (<class 'float'>)
        #     process = 844777 (<class 'int'>)
        #     thread = 139729124534016 (<class 'int'>)
        # 
        #     getMessage = <bound method LogRecord.getMessage of <LogRecord: beater.models, 10, /media/storage/development/github.com/freshbeats-pi/webapp/beater/models.py, 37, "beater.Playlist.objects">> (<class 'method'>)
        #     msg = beater.Playlist.objects (<class 'beater.models.CacheManager'>)
        # 


        
