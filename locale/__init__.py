# -*- coding: utf-8 -*-
"""Локализация: загрузка JSON и функция S(key, lang_code)."""
import json
import os

_LOCALE_DIR = os.path.join(os.path.dirname(__file__))
_CACHE = {}
_SUPPORTED = ("en", "ru", "es", "ar")
_DEFAULT = "en"


def _load(lang_code: str) -> dict:
    lang_code = (lang_code or "").strip().lower()[:2]
    if lang_code not in _SUPPORTED:
        lang_code = _DEFAULT
    if lang_code not in _CACHE:
        path = os.path.join(_LOCALE_DIR, f"{lang_code}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                _CACHE[lang_code] = json.load(f)
        except Exception:
            _CACHE[lang_code] = {}
    return _CACHE[lang_code]


def S(text: str, lang_code: str) -> str:
    """
    Возвращает перевод строки по ключу text для языка lang_code.
    lang_code — двухбуквенный код: en, ru, es, ar.
    Если перевода нет, возвращается значение из en, затем сам ключ.
    """
    code = (lang_code or "").strip().lower()[:2] if lang_code else _DEFAULT
    if code not in _SUPPORTED:
        code = _DEFAULT
    data = _load(code)
    out = data.get(text)
    if out is not None:
        return out
    if code != _DEFAULT:
        data_en = _load(_DEFAULT)
        out = data_en.get(text)
    return out if out is not None else text
