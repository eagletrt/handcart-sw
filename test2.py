from threading import Thread

asd = ["asdads"]

def modifica():
    asd[0] = "no"

def thread():
    print(asd[0])
    modifica()
    print(asd[0])

t = Thread(target=thread, args=( ))

t.start()

t.join()