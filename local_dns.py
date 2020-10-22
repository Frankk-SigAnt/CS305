from dnslib import *
from socket import *
from time import time

server_port = 12000

root_ips = {
    'a.root-servers.net': '198.41.0.4',
    'b.root-servers.net': '199.9.14.201',
    'c.root-servers.net': '192.33.4.12',
    'd.root-servers.net': '199.7.91.13',
    'e.root-servers.net': '192.203.230.10',
    'f.root-servers.net': '192.5.5.241',
    'g.root-servers.net': '192.112.36.4',
    'h.root-servers.net': '198.97.190.53',
    'i.root-servers.net': '192.36.148.17',
    'j.root-servers.net': '192.58.128.30',
    'k.root-servers.net': '193.0.14.129',
    'l.root-servers.net': '199.7.83.42',
    'm.root-servers.net': '202.12.27.33'
}

root_auth = []
root_ar = []


class DNSCache(object):
    def __init__(self):
        self.cache = {}

    def put_record(self, record: DNSRecord):
        self.put(record.get_q().qname,
                 record.get_q().qtype,
                 record.get_q().qclass, record.rr)

    def put(self, qname, qtype, qclass, rr_list):
        self.cache[qname, qtype, qclass] = (rr_list, DNSCache.now())

    def get_by_question(self, question: DNSQuestion):
        return self.get(question.qname, question.qtype, question.qclass)

    def get(self, qname, qtype, qclass):
        try:
            rr_list, cache_time = self.cache[qname, qtype, qclass]
            cur_time = DNSCache.now()
            for rr in rr_list:
                new_ttl = rr.ttl - (cur_time - cache_time)
                if new_ttl < 0:
                    del self.cache[qname, qtype, qclass]
                    return []
                rr.ttl = new_ttl
            return rr_list
        except KeyError:
            return []

    @staticmethod
    def now():
        return int(time())


def init():
    global root_auth, root_ar
    root_auth = [
        RR('.', rtype=QTYPE.NS, ttl=3600, rdata=NS(name))
        for name in root_ips.keys()
    ]
    root_ar = [
        RR(name, rtype=QTYPE.A, ttl=3600, rdata=A(ip))
        for name, ip in root_ips.items()
    ]


def socket_query(query, rr):
    query_sock: socket = socket(AF_INET, SOCK_DGRAM)
    query_sock.sendto(query.pack(), (rr.rdata.toZone().strip('.'), 53))
    try:
        query_sock.settimeout(1)
        query_resp, _ = query_sock.recvfrom(2048)
    except timeout:
        print(f'        {rr.rdata.toZone()} TIMEOUT')
        query_resp = query.reply().pack()
    finally:
        query_sock.close()
    return query_resp


def query_rr(qname, header, rr_list):
    print(f'        -> {qname}')
    query: DNSRecord = DNSRecord(header=header, questions=[DNSQuestion(qname)])
    for rr in rr_list:
        query_resp = socket_query(query, rr)
        dns_resp = DNSRecord.parse(query_resp)
        if dns_resp.rr:
            return dns_resp.rr, True
        new_rr_list: list = dns_resp.auth + dns_resp.ar
        a_list = [rr for rr in new_rr_list if rr.rtype == QTYPE.A]
        if a_list:
            return a_list, False
        ns_list = [rr for rr in new_rr_list if rr.rtype == QTYPE.NS]
        if ns_list:
            print('      Got NS record only. Processing query for NS server...')
            for ns in ns_list:
                next_rr_list = query_domain(ns.rdata.toZone(), header)
                if next_rr_list:
                    return next_rr_list, False
    return [], False


def query_domain(domain, header):
    domain = domain.strip('.')
    print(f'      Query: {domain}')
    rr_list = root_ar
    names = domain.split('.')[::-1]
    qname = ''
    for name in names:
        qname = name + '.' + qname
        rr_list, get_final_rr = query_rr(qname, header, rr_list)
        if get_final_rr:
            return rr_list
    return []


def main():
    init()
    try:
        server_sock: socket = socket(AF_INET, SOCK_DGRAM)
        server_sock.bind(('', server_port))
        dns_cache = DNSCache()
        print('Server started.')
        while True:
            msg, client_addr = server_sock.recvfrom(2048)
            request = DNSRecord.parse(msg)
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print(f'Received request: {request.get_q().qname}')
            cached_rr = dns_cache.get_by_question(request.get_q())
            if cached_rr:
                print('  In cache. Sending response...')
                reply = request.reply()
                reply.add_answer(*cached_rr)
                server_sock.sendto(reply.pack(), client_addr)
            else:
                print('  Cache missed.')
                rd = request.header.get_rd()
                if rd:
                    print('    RD flag set. Processing iterative query...')
                    reply = request.reply()
                    request.header.set_rd(0)
                    qname = request.get_q().get_qname().idna()
                    cname_list = []
                    while True:
                        rr_list = query_domain(qname, request.header)
                        if rr_list:
                            reply.add_answer(*rr_list)
                            if not all(rr.rtype == QTYPE.A for rr in rr_list):  # `all` or `any`?
                                cname_list += [rr for rr in rr_list if rr.rtype == QTYPE.CNAME]
                            if cname_list:
                                print('      Got CNAME record. Processing query for A record...')
                                qname = cname_list[0].rdata.toZone()
                                cname_list.pop(0)
                            else:
                                break
                        else:
                            break
                    print('    Updating cache...')
                    dns_cache.put_record(reply)
                    print('    Query finished. Sending response...')
                    server_sock.sendto(reply.pack(), client_addr)
                else:
                    print('    RD flag unset. Returning root RRs...')
                    reply = request.reply()
                    reply.add_auth(*root_auth)
                    reply.add_ar(*root_ar)
                    server_sock.sendto(reply.pack(), client_addr)
            print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
    except KeyboardInterrupt:
        print('Stopping server...')


if __name__ == '__main__':
    main()
