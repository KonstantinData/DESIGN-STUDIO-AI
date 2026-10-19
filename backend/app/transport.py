"""Anonymous, nonbillable TLS route probe before authorizing paid transport.

A successful route probe is availability evidence only; it does not establish
provider/project authorization or prove that a later paid call cannot fail.
No API credential is attached, no raw network exception is retained or logged.
"""
import asyncio
import time
import weakref
import httpx

class RouteUnavailable(RuntimeError):
    def __init__(self):super().__init__('Die Anbieterroute ist derzeit nicht erreichbar. Es wurde kein kostenpflichtiger Auftrag gesendet.')

class RouteProbe:
    def __init__(self,*,transport=None,clock=time.monotonic):
        self.transport=transport;self.clock=clock;self.lock=asyncio.Lock()
        self.checked_at=None;self.reachable=False

    async def check(self):
        async with self.lock:
            current=self.clock()
            ttl=20 if self.reachable else 2
            if self.checked_at is not None and 0<=current-self.checked_at<ttl:
                if not self.reachable:raise RouteUnavailable()
                return
            reachable=False
            try:
                async with asyncio.timeout(5):
                    async with httpx.AsyncClient(transport=self.transport,timeout=httpx.Timeout(4,connect=2),follow_redirects=False) as client:
                        # Fixed anonymous request: credentials used by Provider are never read.
                        response=await client.get('https://api.openai.com/v1/models')
                        reachable=response.status_code in (200,401,405)
            except (httpx.HTTPError,TimeoutError):pass
            self.reachable=reachable;self.checked_at=self.clock()
            if not reachable:raise RouteUnavailable()

# Each event loop owns its asynchronous lock/cache; no public mode or bypass flag.
_probes=weakref.WeakKeyDictionary()
async def route_preflight():
    loop=asyncio.get_running_loop()
    probe=_probes.get(loop)
    if probe is None:probe=RouteProbe();_probes[loop]=probe
    await probe.check()
