from threading import Thread
from time import sleep
from threading import Lock

data_lock = Lock()

#https://realpython.com/pointers-in-python/#simulating-pointers-in-python mutable types (like pointers) TO READ
# Note that you have to add a minimum "delay" between the release and the get of a lock, a dealy may be a simple for.
# Otherwise processes keep getting the access to the lock, and don't let the others do anything

def modify_variable(var):
    print("Thread 1 started")

    c = 0
    while c<100:
        c +=1
        #sleep(0.01)
        for i in range(1,100):
            x = i*12.54        
        with data_lock:
            var[0] += 1
            print("Thread 1: " + str(var))
            #print("Thread 1 entered lock")
            
                
def dec_var(var):
    print("Thread 2 started")
    c = 0
    while c<100:
        c+=1
        #sleep(0.01)
        for i in range(1,100):
            x = i*12.54        
        with data_lock:
            var[0] -= 1
            print("Thread 2: " + str(var))
            #print("Thread 2 entered lock")
            

def dec_var2(var):
    print("Thread 3 started")
    c = 0
    while c<100:
        c+=1
        for i in range(1,100):
            x = i*12.54
        #sleep(0.01)
        with data_lock:
            print("Thread 3: " + str(var))
            #print("Thread 3 entered lock")

my_var = [0]


t = Thread(target=modify_variable, args=(my_var, ))
t2 = Thread(target=dec_var, args=(my_var, ))
t3 = Thread(target=dec_var2, args=(my_var, ))

t.start()
t2.start()
t3.start()

t.join()
t2.join()
t3.join()