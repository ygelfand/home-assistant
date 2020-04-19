"""Support for the MaryTTS service."""
import logging

from speak2mary import MaryTTS
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_EFFECT, CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_VOICE = "voice"
CONF_CODEC = "codec"

SUPPORT_LANGUAGES = MaryTTS.supported_locales()
SUPPORT_CODEC = MaryTTS.supported_codecs()
SUPPORT_OPTIONS = [CONF_EFFECT]
SUPPORT_EFFECTS = MaryTTS.supported_effects().keys()

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 59125
DEFAULT_LANG = "en_US"
DEFAULT_VOICE = "cmu-slt-hsmm"
DEFAULT_CODEC = "WAVE_FILE"
DEFAULT_EFFECTS = {}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.string,
        vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODEC),
        vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECTS): {
            vol.All(cv.string, vol.In(SUPPORT_EFFECTS)): cv.string
        },
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up MaryTTS speech component."""
    return MaryTTSProvider(hass, config)


class MaryTTSProvider(Provider):
    """MaryTTS speech api provider."""

    def __init__(self, hass, conf):
        """Init MaryTTS TTS service."""
        self.hass = hass
        self._mary = MaryTTS(
            conf.get(CONF_HOST),
            conf.get(CONF_PORT),
            conf.get(CONF_CODEC),
            conf.get(CONF_LANG),
            conf.get(CONF_VOICE),
        )
        self._effects = conf.get(CONF_EFFECT)
        self.name = "MaryTTS"

    @property
    def default_language(self):
        """Return the default language."""
        return self._mary.locale

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def default_options(self):
        """Return dict include default options."""
        return {CONF_EFFECT: self._effects}

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from MaryTTS."""
        effects = options[CONF_EFFECT]

        data = self._mary.speak(message, effects)

        return self._mary.codec, data
