LANGUAGE_CHOICES = {
    "🇬🇧 English": "en",
    "🇫🇮 Suomi": "fi",
    "🇷🇺 Русский": "ru",
}

_EN = list("abcdefghijklmnopqrstuvwxyz")
_FI = _EN + ["å", "ä", "ö"]
_RU = list("абвгдежзийклмнопрстуфхцчшщъыьэюя")

LANGUAGE_LETTERS: dict[str, list[str]] = {
    "en": _EN,
    "fi": _FI,
    "ru": _RU,
}
