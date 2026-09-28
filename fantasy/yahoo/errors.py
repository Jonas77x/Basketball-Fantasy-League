"""Yahoo errors with German messages that can be shown to Jonas directly."""


class YahooError(RuntimeError):
    pass


class YahooNotConfigured(YahooError):
    def __init__(self):
        super().__init__(
            "Yahoo ist noch nicht eingerichtet: YAHOO_CLIENT_ID und YAHOO_CLIENT_SECRET fehlen in der .env-Datei."
        )


class YahooNotConnected(YahooError):
    def __init__(self):
        super().__init__(
            "Noch nicht mit Yahoo verbunden. Bitte auf der Yahoo-Seite „Mit Yahoo verbinden“ nutzen."
        )


class YahooNotAuthorized(YahooError):
    def __init__(self, detail: str = ""):
        super().__init__(
            "Yahoo hat den Zugriff abgelehnt (403). Entweder ist dein API-Antrag noch nicht freigegeben, "
            "oder die Verbindung stammt von vor der Freigabe. Dann auf der Yahoo-Seite „Trennen“ klicken und "
            "neu verbinden." + (f" ({detail})" if detail else "")
        )


class YahooRateLimited(YahooError):
    def __init__(self):
        super().__init__(
            "Yahoo bremst gerade (zu viele Anfragen). Das System wartet automatisch etwas länger."
        )


class YahooAuthFailed(YahooError):
    pass
