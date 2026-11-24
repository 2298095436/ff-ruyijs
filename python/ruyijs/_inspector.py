"""Debug-mode API log. js.exe owns the monitor state, policy and bounds."""


class InspectorControl:
    """Read the debug monitor's record of install-registered member accesses.

    The log is empty unless the Context was created with ``mode="debug"``. Only
    members a production installer registered are observed; a property a script
    defines later is not wrapped, so it produces no entry (see deviation D9).
    """

    def _api_log(self, action, **fields):
        self._callbacks.guard()
        with self._lock:
            return self._request("api_log", action=action, **fields)

    def peek_api_log(self, filter=None):
        """Return recorded entries without draining them."""
        return self._api_log_pages(filter, drain=False)

    def get_api_log(self, filter=None):
        """Return recorded entries and drain the log."""
        return self._api_log_pages(filter, drain=True)

    def _api_log_pages(self, filter, *, drain):
        # A full 20,000-record monitor has more than 100,000 typed snapshot
        # nodes. Read bounded pages while holding the Context lock and only
        # clear after every page was transferred successfully.
        self._callbacks.guard()
        fields = {} if filter is None else {"filter": filter}
        with self._lock:
            rows = []
            while True:
                page = self._request("api_log", action="peek", offset=len(rows), limit=2000, **fields)
                rows.extend(page)
                if len(page) < 2000:
                    break
            if drain:
                self._request("api_log", action="clear")
            return rows

    def clear_api_log(self):
        """Drop every recorded entry and report the remaining count."""
        return self._api_log("clear")
