import argparse

parser = argparse.ArgumentParser(description='Software to control handcart')
parser.add_argument('-a', action='store', required=True, choices=['chimera', 'fenice'], nargs=1, type=str, help="Choose the accumulator to charge")
parser.add_argument('--fast', action='store_const', default=0, const=1, help="Use fast charge, default=no")
parser.add_argument('--cutoff', action='store', default=320, nargs=1, type=int, help="Sets the voltage at wich the charge stops. Default=320")
parser.add_argument('--maxCurrD', action='store', default=16, nargs=1, type=int, help="Sets the maximum current in (A) to be drawn from the outlet. Default=16A")


args = vars(parser.parse_args())

fast = args['fast']
cutoff = args['cutoff']
maxcurrd = args['maxcurrd']
print(cutoff)