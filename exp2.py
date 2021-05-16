# 4+1, star, no noise

import numpy as np

# simulation settings
simtime = 4*1000*60*60
rayleigh = 0
var = 0 # dbm; noise power variance

# default tx param
PTX = 10
SF = 7
CR = 4
BW = 125
FREQ = 900000000
TTL = 15

# network settings
avgSendTime = 1000*60 # avg time between packets in ms
slot = 1000
n0 = 2 # assumed no. of neighbour nodes
p0 = (1-(1/n0))**(n0-1)

# end nodes placement
# TODO: generate spatial distribution using Poisson Hard-Core Process
x = np.array([-100,100,0,0])
y = np.array([0,0,100,-100])
locs = np.array([x,y])