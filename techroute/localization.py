import gettext
import locale
import os
from typing import Callable, List, Optional

class LocalizationManager:
    def __init__(self, language_code: Optional[str] = None):
        self.locales_dir = os.path.join(os.path.dirname(__file__), '..', 'locales')
        self.available_languages = self._find_available_languages()
        self.language_code = language_code
        self.translator: Callable[[str], str] = self._get_translator()

    def _find_available_languages(self) -> List[str]:
        """Finds available languages by scanning the locales directory."""
        languages = ['en']  # Default language
        if os.path.isdir(self.locales_dir):
            for lang in os.listdir(self.locales_dir):
                if os.path.isdir(os.path.join(self.locales_dir, lang, 'LC_MESSAGES')):
                    languages.append(lang)
        return sorted(list(set(languages)))

    def _get_translator(self) -> Callable[[str], str]:
        """
        Gets a translator function for the specified language.
        Falls back to a null translator if the language is not found.
        """
        lang_code = self.language_code
        if lang_code is None or lang_code.lower() == 'system':
            try:
                lang_code, _ = locale.getdefaultlocale()
                lang_code = lang_code.split('_')[0] if lang_code else 'en'
            except Exception:
                lang_code = 'en'

        try:
            lang_gettext = gettext.translation(
                'messages',
                localedir=self.locales_dir,
                languages=[lang_code]
            )
            lang_gettext.install()
            return lang_gettext.gettext
        except FileNotFoundError:
            # Fallback to a null translator
            return gettext.gettext

    def set_language(self, language_code: Optional[str]):
        """Sets the language and updates the translator."""
        self.language_code = language_code
        self.translator = self._get_translator()

def get_translator(language_code: Optional[str] = None) -> Callable[[str], str]:
    """Initializes and returns a translator function."""
    manager = LocalizationManager(language_code)
    return manager.translator

# Global translator instance
_ = get_translator()
