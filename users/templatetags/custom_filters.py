from django import template

register = template.Library()

@register.filter
def dict_key(value, key):
    return value.get(key)

@register.filter
def is_transcribable(file_type):
    transcribable_types = ["audio/mpeg", "audio/mp4", "audio/wav", "audio/flac", "video/mp4"]
    return file_type in transcribable_types