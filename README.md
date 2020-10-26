# SUSTech CS305 Works

## Simple DNS Server

CS305 Lab 5 Assignment

Local DNS server with cache,  implemented using `dnslib` and `socket`. Currently supporting `A`-type query only.

If `RD` flag is set, iterative query is executed manually. Otherwise only (hardcoded) root server messages will be returned.

## HTTP File Server

CS305 Lab 6 Assignment

Simplified implementation of `http.server` based on `asyncio` (not using `aiohttp`), supporting HTTP/1.0 with `GET` and `HEAD` methods only.

Now supports simple range requests with **weak** checking.
