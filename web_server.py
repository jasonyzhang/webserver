import argparse
import contextlib
import html
import http.client
import io
import os
import sys
import time
import urllib.parse
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer, test


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if size < 1024.0 or unit == 'PiB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


class CustomServer(SimpleHTTPRequestHandler):

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """
        try:
            path_list = os.listdir(path)
        except OSError:
            self.send_error(
                HTTPStatus.NOT_FOUND,
                "No permission to list directory")
            return None
        path_list.sort(key=lambda a: a.lower())
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path,
                                               errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        title = 'Directory listing for %s' % displaypath
        r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                 '"http://www.w3.org/TR/html4/strict.dtd">')
        r.append('<html>\n<head>')
        r.append('<meta http-equiv="Content-Type" '
                 'content="text/html; charset=%s">' % enc)
        r.append('<title>%s</title>\n</head>' % title)
        r.append('<head>\n<style>')
        # r.append('table, th, td {border: 1px solid black; }')
        r.append('table { border-collapse: collapse;}')
        r.append('td { padding: 0px 15px; }')
        r.append('tr:nth-child(even) { background-color: #D3D3D3; }')
        r.append('tr:hover { background-color: #ADD8E6; }')
        r.append('</style>\n</head>')
        r.append('<body>\n<h1>%s</h1>' % title)
        up_dir = urllib.parse.quote(os.path.abspath(os.path.dirname(path)))
        up_dir = ".."
        r.append('<a href={}>Parent Directory</a>'.format(
            urllib.parse.quote(up_dir, errors="surrogatepass")
        ))
        r.append('<hr>\n<table>')
        r.append('<tr>')
        r.append('<th>#</th>\n')
        r.append('<th>File</th>\n')
        r.append('<th>Size</th>\n')
        r.append('<th>Last Modified</th>\n')
        r.append('<th>Shortname</th>\n')
        r.append('</tr>\n')
        for i, name in enumerate(path_list):
            fullname = os.path.join(path, name)
            filesize = human_readable_size(os.stat(fullname).st_size)
            modified_time = time.localtime(os.stat(fullname).st_mtime)
            modified = time.strftime("%D %I:%M %p", modified_time)
            short_name = name.split("_")[0]
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            r.append('<tr>')
            r.append(f'<td>{i+1}</td>')
            r.append('<td><a href="%s">%s</a></td>'
                    % (urllib.parse.quote(linkname,
                                          errors='surrogatepass'),
                       html.escape(displayname, quote=False)))
            r.append(f'<td>{filesize}</td>')
            r.append(f'<td>{modified}</td>')
            r.append(f'<td>{short_name}</td>')
            # r.append(f'<td>{fullname}</td>')
            r.append('</tr>')
        r.append('</table>\n<hr>\n</body>\n</html>\n')
        encoded = '\n'.join(r).encode(enc, 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', '-b', metavar='ADDRESS',
                        help='Specify alternate bind address '
                             '[default: all interfaces]')
    parser.add_argument('--directory', '-d', default=os.getcwd(),
                        help='Specify alternative directory '
                        '[default:current directory]')
    parser.add_argument('port', action='store',
                        default=8000, type=int,
                        nargs='?',
                        help='Specify alternate port [default: 8000]')
    args = parser.parse_args()
    handler_class = partial(CustomServer,
                            directory=args.directory)

    # ensure dual-stack is not disabled; ref #38907
    class DualStackServer(ThreadingHTTPServer):
        def server_bind(self):
            # suppress exception when protocol is IPv4
            with contextlib.suppress(Exception):
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            return super().server_bind()

    test(
        HandlerClass=handler_class,
        ServerClass=DualStackServer,
        port=args.port,
        bind=args.bind,
    )

