from asyncio import run, start_server, StreamReader, StreamWriter, AbstractServer
from mimetypes import guess_type
from pathlib import Path
from typing import List, Tuple

status = {
    200: '200 OK',
    206: '206 Partial Content',
    400: '400 Bad Request',
    404: '404 Not Found',
    # 405: '405 Not Allowed',  # Unused
    # 416: '416 Range Not Satisfiable',  # Unused
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


async def get_header(status_msg: str, content_length: int, content_type: str = 'text/html',
                     content_range: str = None) -> bytes:
    header = f'HTTP/1.0 {status_msg}\r\n' \
             f'Content-Length: {content_length}\r\n' \
             f'Accept-Ranges: bytes\r\n' \
             f'Connection: close\r\n' \
             f'Content-Type: {content_type}\r\n'
    if content_range:
        header += f'Content-Range: {content_range}\r\n'
    return (header + '\r\n').encode()


async def get_dir_response(path: Path, raw_path: str) -> bytes:
    body = await dir_html(path, raw_path)
    header = await get_header(status[200], len(body))
    return header + body


async def get_file_response(path: Path, byte_range: List[Tuple[int, int]]) -> bytes:
    status_code = 206
    mime_type = await get_mime_type(path)
    file_bytes = path.read_bytes()
    bytes_cnt = len(file_bytes)
    content_range = None
    if not byte_range:
        body = file_bytes
        status_code = 200
    elif len(byte_range) == 1:
        from_byte = byte_range[0][0]
        to_byte = byte_range[0][1]
        if from_byte is None:
            from_byte = 0
        if to_byte is None:
            to_byte = bytes_cnt - 1
        content_range = f'bytes {from_byte}-{to_byte}/{bytes_cnt}'
        body = file_bytes[from_byte:to_byte + 1]
    else:
        body_mime_type = mime_type
        mime_type = 'multipart/byteranges; boundary=3d6b6a416f9b5'
        body = b''
        for br in byte_range:
            from_byte = br[0]
            to_byte = br[1]
            if from_byte is None:
                from_byte = 0
            if to_byte is None:
                to_byte = bytes_cnt - 1
            body += f'--3d6b6a416f9b5\r\n' \
                    f'Content-Type: {body_mime_type}\r\n' \
                    f'Content-Range: bytes {from_byte}-{to_byte}/{bytes_cnt}\r\n\r\n'.encode()
            body += file_bytes[from_byte:to_byte + 1]
        body += b'--3d6b6a416f9b5--'
    header = await get_header(status[status_code], len(body), mime_type, content_range)
    return header + body


async def get_error_response(code: int) -> bytes:
    status_msg = status[code]
    body = error_html(status_msg)
    header = await get_header(status_msg, len(body))
    return header + body


def parse_range(header: List[str]) -> List[Tuple[int, int]]:
    range_list = []
    for line in header:
        if line.startswith('Range: bytes='):
            raw_range_list = list(map(lambda x: x.split('-'), line[13:].split(', ')))
            for raw_range in raw_range_list:
                if len(raw_range) != 2:
                    raise ValueError
                parsed_range = (int(raw_range[0].strip()) if raw_range[0] else None,
                                int(raw_range[1].strip()) if raw_range[1] else None)
                if parsed_range == (None, None):
                    raise ValueError
                range_list.append(parsed_range)
            break
    return range_list


async def http_server_callback(reader: StreamReader, writer: StreamWriter):
    raw_header = await reader.readuntil(b'\r\n\r\n')
    header = raw_header.decode().split('\r\n')
    try:
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
                byte_range = parse_range(header[1:])
                response: bytes = await get_file_response(path, byte_range)
                print(method, raw_path, status[206 if byte_range else 200])
            else:
                response: bytes = await get_error_response(404)
                print(method, raw_path, status[404])
    except ValueError:
        response: bytes = await get_error_response(400)
    writer.write(response)
    await writer.drain()
    writer.close()


async def main():
    server: AbstractServer = await start_server(http_server_callback, '127.0.0.1', 8080)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}...')
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        run(main())
    except KeyboardInterrupt:
        print('Server stopped.')
