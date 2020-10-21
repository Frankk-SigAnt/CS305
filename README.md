# LocalDNS: Simple DNS Server

SUSTech CS305 Lab 5 Assignment

Local DNS server with cache,  implemented using `dnslib` and `socket`. Currently supporting `A`-type query only.

If `RD` flag is set, iterative query is executed manually. Otherwise only (hardcoded) root server messages will be returned.