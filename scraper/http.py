"""Tiny, polite HTTP helper (stdlib only, so it runs anywhere for free)."""
import json
import time
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 scrappy-personal-price-checker"
)
DELAY_SECONDS = 1.5  # be gentle: one request every 1.5s
_last_request = 0.0


def get_json(url, retries=3, timeout=30):
    global _last_request
    for attempt in range(1, retries + 1):
        wait = DELAY_SECONDS - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise  # blocked or gone: retrying won't help
            err = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            err = e
        time.sleep(2 * attempt)
    raise err
