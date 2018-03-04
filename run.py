#! .env/bin/python

import multiprocessing
import socket
import http
import sys

from burn import surf, reg, log

import config


if __name__ == '__main__':
    try:
        log('welcome!')

        if len(sys.argv) > 1:
            _, cmd, start, end, *rest = (sys.argv + 10 * [''])[:10]

            if cmd == 'reg':
                reg(int(start), int(end or 0))
            elif cmd == 'surf':
                surf('0:{}:{}'.format(int(start), int(end or o)))
        else:
            proc_num = config.PROCS_NUM
            offset = config.GUYS_PER_PROC

            params = ['{}:{}:{}'.format(
                proc, -6 if proc == 0 else offset * proc,
                offset * (proc + 1)) for proc in range(proc_num)]

            pool = multiprocessing.Pool()
            pool.map_async(surf, params)

            pool.close()
            pool.join()
    except (socket.error,
            KeyboardInterrupt,
            http.client.RemoteDisconnected) as e:
        log(e, type='error')
        log('bye!')
