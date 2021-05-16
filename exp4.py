## 75+1, mesh, noise

import numpy as np

# simulation settings
simtime = 1*1000*60*60
rayleigh = 0
var = 1 # dbm; noise power variance

# default tx param
PTX = 14
SF = 7
CR = 4
BW = 125
FREQ = 900000000
TTL = 15

# network settings
avgSendTime = 1000*60 # avg time between packets in ms
slot = 1000
n0 = 10 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# end nodes placement
# TODO: generate spatial distribution using Poisson Hard-Core Process
locs = np.loadtxt('75.csv',delimiter=',')