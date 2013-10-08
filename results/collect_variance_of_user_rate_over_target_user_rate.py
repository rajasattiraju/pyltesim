#!/usr/bin/env python

'''Collect the variance of user rate over the target rate 
y-axis: variance of user rate
x-axis: target rate

'''

__author__ = "Hauke Holtkamp"
__credits__ = "Hauke Holtkamp"
__license__ = "unknown"
__version__ = "unknown"
__maintainer__ = "Hauke Holtkamp"
__email__ = "h.holtkamp@gmail.com" 
__status__ = "Development" 

import glob
import numpy as np
import sys
import os
import ConfigParser
from scipy.stats.stats import nanmean
def main(searchpath, outpath):
    """Search all directories in searchpath for settings files. Handle them according to the settings found in those files. Eventually, build a data csv for plotting. 
    Input: search path, output path
        """

    data_types = 5 
    rate = 1e6 * 2.0 # 2 Mbps
    iterations = None
    sweep_values = [] # we do not know beforehand how much data we have
    depth = None

    # enum
    axis_index = 0
    sequential_index = 1
    random_each_iter_index = 2
    sinr_index = 3
    dtx_segregation = 4

    data_str = {1:'none', 2:'rand', 3:'sinr', 4:'dtxs'}

    # initially, we only check how much data we have
    for dirname, dirnames, filenames in os.walk(searchpath):
        if depth is None:
            depth = len(dirnames) # worst case amount of data
        for subdirname in dirnames:
            for filename in glob.glob(os.path.join(dirname, subdirname)+'/*settings*'):
                config = ConfigParser.RawConfigParser()
                config.read(filename)
                iterations = int(config.getfloat('General', 'iterations')) 
                sweep_values.append(int(config.getfloat('General', 'user_rate'))) 
                numcenterusers = int(config.getfloat('General', 'numcenterusers'))

    sweep_values = sorted(set(sweep_values))
    # list of lists
    result = [] # result[data_type][sweep_value]
    for i in np.arange(data_types):
        result.append([])
        for j in np.arange(len(sweep_values)):
            result[i].append([])
            result[i][j] = np.zeros([20,1]) # prepare dimensions

    count = np.zeros([len(sweep_values), data_types])
    
    # now start filling the result
    dep = 0
    for dirname, dirnames, filenames in os.walk(searchpath):
        for subdirname in dirnames:
            for filename in glob.glob(os.path.join(dirname, subdirname)+'/*settings*.cfg'):
                
                config = ConfigParser.RawConfigParser()
                config.read(filename)
                rate = int(config.getfloat('General', 'user_rate'))
                sleep_alignment = config.get('General', 'sleep_alignment')
                initial_power = config.get('General', 'initial_power')
                iterations = config.get('General', 'iterations')

                filedata = np.genfromtxt(os.path.join(dirname, subdirname)+'/delivered_per_mobile.csv', delimiter=',')
                # seqDTX sequential 
                if ('DTX' in filename) and (sleep_alignment == 'none'):
                    index = sequential_index 

                # random each iter
                elif ('DTX' in filename) and (sleep_alignment == 'random_iter'): 
                    index = random_each_iter_index

                # sinr ordering
                elif ('DTX' in filename) and (sleep_alignment == 'sinr'):
                    index = sinr_index
                        
                # dtx segregation 
                elif ('DTX' in filename) and (sleep_alignment == 'dtx_segregation'):
                    index = dtx_segregation 

                else:
                    print 'What is this folder?'+os.path.join(dirname, subdirname)+'/'+filename
                    filedata = 0
                    index = 0

                result[index][sweep_values.index(rate)] = np.append(result[index][sweep_values.index(rate)], filedata, axis=1)
                count[sweep_values.index(rate), index] += 1
                dep += 1

    
    #  clear placeholder
    for i in np.arange(data_types):
        for j in np.arange(len(sweep_values)):
            result[i][j] = np.delete(result[i][j], 0, 1)

    # build percentages
    avg_rates = np.zeros([data_types, len(sweep_values)])
    for dt in np.arange(1,data_types):
        for si, sv in enumerate(sweep_values):
            elements = 100*result[dt][si] # times 100 for users and timeslots per frame. contains all user rates over all iterations

            # percentage at last iteration
            avg_rates[dt,si] = np.std(elements) # should be around the value of sv

    # x-axis
    avg_rates[0,:] = sweep_values

    target = outpath + '/standard_deviation_of_user_rate_over_target_user_rate.csv'
    np.savetxt(target, avg_rates, delimiter=',')

    print avg_rates
    print count.T


if __name__ == '__main__':
    searchpath = sys.argv[1]
    outpath = sys.argv[2]
    if not os.path.exists(outpath):
        os.makedirs(outpath)
    main(searchpath, outpath)
