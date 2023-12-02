class Fifo(object):
    
    fifo = None 

    def __init__(self, *args, **kwargs):
        self.fifo = []
    
    def apush(self, item):
        self.push(item)
        return self.pop()

    def push(self, item):
        self.fifo.append(item)
    
    def pop(self):
        retObj = None 
        if len(self.fifo) > 0:
            retObj = self.fifo[0]
            del self.fifo[0]
        return retObj