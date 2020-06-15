# compact html
import re

from io import IOBase


class CompactHTML():
    def __init__(self, stylesheet):
        css = {}
        if isinstance(stylesheet, IOBase):
            styles = stylesheet.readlines()
        elif isinstance(stylesheet, list):
            styles = stylesheet
        else:
            styles = stylesheet.split(b'\r\n')
        index = prefix = suffix = ''
        count = 0
        for line in styles:
            if count % 3 == 0:
                index = line
            elif count % 3 == 1:
                prefix = line
            else:
                suffix = line
                css[index] = (prefix, suffix)
            count += 1
        self._css = css

    def to_html(self, chtml):
        html = []
        re_index = re.compile(b'`(\\d+)`')
        pos = 0
        last_end_tag = b''
        for m in re_index.finditer(chtml):
            html.append(chtml[pos:m.start()])
            html.append(last_end_tag)
            html.append(self._css[m.group(1)][0])
            last_end_tag = self._css[m.group(1)][1]
            pos = m.end()
        html.append(last_end_tag)
        return b''.join(html)
