from asyncio import run, start_server, StreamReader, StreamWriter
from mimetypes import guess_type
from pathlib import Path

status = {
    200: '200 OK',
    206: '206 Partial Content',
    400: '400 Bad Request',
    404: '404 Not Found',
    405: '405 Not Allowed',
    416: '416 Range Not Satisfiable'
}

base_dir = Path.cwd()


def error_html(msg) -> bytes:
    return f'''
<html>
<head><title>{msg}</title></head>
<body bgcolor="white">
<center><h1>{msg}</h1></center>
</body>
</html>
'''.strip().encode()


async def dir_html(path: Path, raw_path: str) -> bytes:
    html_begin = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n' \
                 f'<html>\n\n' \
                 f'<head>\n' \
                 f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n' \
                 f'<title>Directory listing for {raw_path}</title>\n' \
                 f'</head>\n\n' \
                 f'<body>\n' \
                 f'<h1>Directory listing for {raw_path}</h1>\n' \
                 f'<hr>\n' \
                 f'<ul>\n'
    html_end = f'\n' \
               f'</ul>\n' \
               f'<hr>\n' \
               f'</body>\n\n' \
               f'</html>'
    return (html_begin + '\n'.join(f'<li><a href="{f.relative_to(base_dir)}">{f.name}</a></li>'
                                   for f in filter(lambda x: x.is_file() or x.is_dir(), path.iterdir()))
            + html_end).encode()


async def get_mime_type(path: Path) -> str:
    return guess_type(path)[0] or 'application/octet-stream'


async def get_header(status_msg: str, content_length: int, content_type: str = 'text/html') -> bytes:
    header = f'HTTP/1.0 {status_msg}\r\n' \
             f'Content-Length: {content_length}\r\n' \
             f'Accept-Ranges: bytes\r\n' \
             f'Connection: close\r\n' \
             f'Content-Type: {content_type}\r\n'
    return (header + '\r\n').encode()


async def get_dir_response(path: Path, raw_path: str) -> bytes:
    body = await dir_html(path, raw_path)
    header = await get_header(status[200], len(body))
    return header + body


async def get_file_response(path: Path) -> bytes:
    mime_type = await get_mime_type(path)
    body = path.read_bytes()
    header = await get_header(status[200], len(body), mime_type)
    return header + body


async def get_error_response(code: int) -> bytes:
    status_msg = status[code]
    body = error_html(status_msg)
    header = await get_header(status_msg, len(body))
    return header + body


async def http_server(reader: StreamReader, writer: StreamWriter):
    raw_header = await reader.readuntil(b'\r\n\r\n')
    header = raw_header.decode().split('\r\n')
    method, raw_path, _ = header[0].split()
    if method not in ['GET', 'HEAD']:
        response: bytes = await get_error_response(405)
        print(method, raw_path, status[405])
    else:
        path = base_dir / raw_path.lstrip('/')
        if path.is_dir():
            response: bytes = await get_dir_response(path, raw_path)
            print(method, raw_path, status[200])
        elif path.is_file():
            response: bytes = await get_file_response(path)
            print(method, raw_path, status[200])
        else:
            response: bytes = await get_error_response(404)
            print(method, raw_path, status[404])
    writer.write(response)
    await writer.drain()
    writer.close()


async def main():
    server = await start_server(http_server, '127.0.0.1', 8080)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}...')
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        run(main())
    except KeyboardInterrupt:
        print('Server stopped.')
