from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Curated IANA timezone list grouped by region.
# City display name = last component of the identifier, underscores → spaces.
TIMEZONE_REGIONS: dict[str, list[str]] = {
    "Africa": [
        "Africa/Abidjan", "Africa/Addis_Ababa", "Africa/Cairo", "Africa/Casablanca",
        "Africa/Harare", "Africa/Johannesburg", "Africa/Lagos", "Africa/Nairobi",
        "Africa/Tripoli", "Africa/Tunis",
    ],
    "America": [
        "America/Anchorage", "America/Argentina/Buenos_Aires", "America/Bogota",
        "America/Caracas", "America/Chicago", "America/Denver", "America/Halifax",
        "America/Havana", "America/Lima", "America/Los_Angeles", "America/Mexico_City",
        "America/New_York", "America/Phoenix", "America/Puerto_Rico",
        "America/Santiago", "America/Sao_Paulo", "America/St_Johns",
        "America/Toronto", "America/Vancouver",
    ],
    "Asia": [
        "Asia/Almaty", "Asia/Amman", "Asia/Baghdad", "Asia/Baku", "Asia/Bangkok",
        "Asia/Beirut", "Asia/Dhaka", "Asia/Dubai", "Asia/Hong_Kong", "Asia/Irkutsk",
        "Asia/Jakarta", "Asia/Jerusalem", "Asia/Kabul", "Asia/Kamchatka",
        "Asia/Karachi", "Asia/Kathmandu", "Asia/Kolkata", "Asia/Krasnoyarsk",
        "Asia/Kuala_Lumpur", "Asia/Kuwait", "Asia/Magadan", "Asia/Manila",
        "Asia/Novosibirsk", "Asia/Omsk", "Asia/Qatar", "Asia/Riyadh",
        "Asia/Seoul", "Asia/Shanghai", "Asia/Singapore", "Asia/Taipei",
        "Asia/Tashkent", "Asia/Tbilisi", "Asia/Tehran", "Asia/Tokyo",
        "Asia/Ulaanbaatar", "Asia/Vladivostok", "Asia/Yakutsk",
        "Asia/Yekaterinburg", "Asia/Yerevan",
    ],
    "Atlantic": [
        "Atlantic/Azores", "Atlantic/Cape_Verde", "Atlantic/Reykjavik",
        "Atlantic/South_Georgia",
    ],
    "Australia": [
        "Australia/Adelaide", "Australia/Brisbane", "Australia/Darwin",
        "Australia/Hobart", "Australia/Melbourne", "Australia/Perth", "Australia/Sydney",
    ],
    "Europe": [
        "Europe/Amsterdam", "Europe/Athens", "Europe/Belgrade", "Europe/Berlin",
        "Europe/Brussels", "Europe/Bucharest", "Europe/Budapest", "Europe/Copenhagen",
        "Europe/Dublin", "Europe/Helsinki", "Europe/Istanbul", "Europe/Kaliningrad",
        "Europe/Kyiv", "Europe/Lisbon", "Europe/London", "Europe/Madrid",
        "Europe/Minsk", "Europe/Moscow", "Europe/Oslo", "Europe/Paris",
        "Europe/Prague", "Europe/Riga", "Europe/Rome", "Europe/Samara",
        "Europe/Sofia", "Europe/Stockholm", "Europe/Tallinn", "Europe/Vienna",
        "Europe/Vilnius", "Europe/Warsaw", "Europe/Zurich",
    ],
    "Pacific": [
        "Pacific/Auckland", "Pacific/Fiji", "Pacific/Guam", "Pacific/Honolulu",
        "Pacific/Noumea", "Pacific/Port_Moresby", "Pacific/Tongatapu",
    ],
    "UTC": ["UTC"],
}


def _tz_label(tz: str) -> str:
    """Return display name: last path component, underscores → spaces."""
    return tz.split("/")[-1].replace("_", " ")


def timezone_regions_keyboard(lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for region in TIMEZONE_REGIONS:
        builder.button(text=region, callback_data=f"profile:tz:region:{region}")
    builder.button(text=lang["main-back"], callback_data="menu:profile", style=ButtonStyle.SUCCESS)
    builder.adjust(2)
    return builder.as_markup()


def timezone_cities_keyboard(region: str, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tz in TIMEZONE_REGIONS.get(region, []):
        builder.button(text=_tz_label(tz), callback_data=f"profile:tz:set:{tz}")
    builder.button(text=lang["main-back"], callback_data="profile:tz", style=ButtonStyle.SUCCESS)
    builder.adjust(2)
    return builder.as_markup()
