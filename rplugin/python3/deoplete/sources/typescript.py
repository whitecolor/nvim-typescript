import re
import json
import subprocess

from logging import getLogger
from deoplete.sources.base import Base

logger = getLogger(__name__)

_tsserver_handle = subprocess.Popen("tsserver",
        stdout = subprocess.PIPE,
        stdin = subprocess.PIPE,
        stderr = subprocess.STDOUT,
        universal_newlines = True,
        bufsize = 1)

class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)

        self.debug_enabled = True
        self.name = "typescript"
        self.mark = "[ts]"
        self.filetypes = ["typescript"]
        self.input_pattern = "\."
        self.is_bytepos = True

        self._sequenceid = 0
        self._current_file = None

    def _send_request( self, command, arguments = None, wait_for_response = False ):
        seq = self._next_sequence_id()

        request = {
            "seq":     seq,
            "type":    "request",
            "command": command
        }
        if arguments:
            request[ "arguments" ] = arguments

        logger.debug("_send_request: request: {0}".format(request))

        self._write_message(request)

        if not wait_for_response:
            return

        linecount = 0
        headers = {}
        while True:
            headerline = _tsserver_handle.stdout.readline().strip()
            linecount += 1;
            if len(headerline):
                key, value = headerline.split( ":", 2 )
                headers[ key.strip() ] = value.strip()
                logger.debug(headers)
                break

        if "Content-Length" not in headers:
            raise RuntimeError( "Missing 'Content-Length' header" )
        contentlength = int(headers["Content-Length"])
        return json.loads(_tsserver_handle.stdout.read(contentlength))

    def _next_sequence_id(self):
        seq = self._sequenceid
        self._sequenceid += 1
        return seq

    def _write_message(self, message):
        _tsserver_handle.stdin.write(json.dumps(message))
        _tsserver_handle.stdin.write("\n")

    def relative_file(self):
        return self.vim.eval("expand('%:p')")

    def get_complete_position(self, context):
        m = re.search(r"\w*$", context["input"])
        return m.start() if m else -1

    def gather_candidates(self, context):
        self.debug("gather_candidates: contenxt: {0}".format(context))

        self._send_request("open", {
            "file": self.relative_file()
        });

        line = context["position"][1]
        col = context["complete_position"] + 1

        completionsRequestBody = {
            "file":   self.relative_file(),
            "line":   line,
            "offset": col,
            "prefix": context["complete_str"]
        }

        self.debug("gather_candidates: completions request: {0}".format(completionsRequestBody))
        data = self._send_request("completions", completionsRequestBody, wait_for_response = True)

        completions = []
        if data is not None and "body" in data:
            for rec in data["body"]:
                completions.append({
                    "word": rec["name"],
                    "kind": rec["kind"],
                    "menu": rec["kindModifiers"]
                    })

        logger.debug("gather_candidates: returning: {0}".format(completions))

        return completions