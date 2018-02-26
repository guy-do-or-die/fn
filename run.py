#! .env/bin/python

import multiprocessing
import socket
import http
import sys

from burn import surf, reg, log


if __name__ == '__main__':
    try:
        log('welcome!')

        if len(sys.argv) > 1:
            _, cmd, start, end, *rest = (sys.argv + 10 * [''])[:10]

            if cmd == 'reg':
                reg(int(start), int(end or 0))
            elif cmd == 'surf':
                surf('0:-6:201')
        else:
            surf('0:-6:201')

        #guys = []
        #pool = multiprocessing.Pool(len(guys))
        #pool.map_async(surf, guys)

        #pool.close()
        #pool.join()
    except (socket.error,
            KeyboardInterrupt,
            http.client.RemoteDisconnected) as e:
        log(e, type='error')
        log('bye!')
