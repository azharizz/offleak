"""Phone-number spans via Google's libphonenumber. National numbers (no +country) are read in the user's region."""
import locale
import os

from phonenumbers import Leniency, PhoneNumberMatcher


def _region():
    """OFFLEAK_PHONE_REGION (e.g. ID, US), else the system locale's country, else US."""
    code = os.environ.get('OFFLEAK_PHONE_REGION')
    if not code:
        lang = locale.getlocale()[0] or ''
        code = lang.split('_')[-1] if '_' in lang else 'US'
    return code.upper()


REGION = _region()


def phone_spans(text):
    """[(start, end)] character spans of possible phone numbers (POSSIBLE leniency: fail closed on odd formats)."""
    return [(m.start, m.end) for m in PhoneNumberMatcher(text, REGION, leniency=Leniency.POSSIBLE)]
