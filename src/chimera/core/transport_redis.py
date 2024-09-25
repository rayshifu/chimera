from typing import Type

import redis
import redislite
from chimera.core.protocol import Request, Response
from chimera.core.serializer import Serializer
from chimera.core.serializer_pickle import PickleSerializer
from chimera.core.transport import Transport


class RedisTransport(Transport):
    REQUESTS_KEY: str = "chimera_requests"

    DEFAULT_TIMEOUT: int = 5 * 60  # 5 minutes
    LOOP_TICK: int = 1

    def __init__(self, host: str, port: int, serializer: Type[Serializer] = PickleSerializer):
        super().__init__(host, port, serializer)
        self.r = None

    def bind(self):
        self.r = redislite.Redis(serverconfig={"bind": self.host, "port": self.port})
        self.r.delete(RedisTransport.REQUESTS_KEY)

    def connect(self):
        self.r = redislite.Redis(host=self.host, port=self.port)

    def close(self):
        self.r.close()

    def ping(self):
        return self.r.ping()

    def send_request(self, request: Request) -> None:
        request_bytes = self.serializer.dumps(request)
        self.r.rpush(self.REQUESTS_KEY, request_bytes)

    def recv_request(self) -> Request:
        try:
            data = self.r.blpop(
                [
                    self.REQUESTS_KEY,
                ]
            )
            _, request_bytes = data
            return self.serializer.loads(request_bytes)
        except redis.exceptions.ConnectionError:
            raise Exception("Connection error")

    def send_response(self, request: Request, response: Response) -> None:
        response_bytes = self.serializer.dumps(response)
        self.r.rpush(f"chimera_response_{request.id}", response_bytes)

    def recv_response(self, request: Request) -> Response:
        try:
            data = self.r.blpop(
                [
                    f"chimera_response_{request.id}",
                ]
            )
            _, request_bytes = data
            return self.serializer.loads(request_bytes)
        except redis.exceptions.ConnectionError:
            raise Exception("Connection error")
