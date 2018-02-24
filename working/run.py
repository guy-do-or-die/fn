#! ../../.env/bin/python

import multiprocessing
import socket
import http

from burn import surf, log
from config import GUYS, DEBUG


if __name__ == '__main__':
    try:
        log('welcome!')

        if DEBUG:
            surf('thy.do.or.die+12@gmail.com')
        else:
            guys = GUYS[:6]

            pool = multiprocessing.Pool(len(guys))
            pool.map_async(surf, guys)
            pool.close()
            pool.join()
    except (socket.error,
            KeyboardInterrupt,
            http.client.RemoteDisconnected) as e:
        log(e, type='error')
        log('bye!')
