# Source Context for django__django-11099

Repository: django/django
Base commit: d26b2424437dabeeca94d7900b37d2df4410da0c
Selection rule: worker-derived candidate diff paths only.
Forbidden fields remain excluded: gold patch, test patch, FAIL_TO_PASS, PASS_TO_PASS, hints.

## django/contrib/auth/validators.py

````text
import re

from django.core import validators
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class ASCIIUsernameValidator(validators.RegexValidator):
    regex = r'^[\w.@+-]+$'
    message = _(
        'Enter a valid username. This value may contain only English letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = re.ASCII


@deconstructible
class UnicodeUsernameValidator(validators.RegexValidator):
    regex = r'^[\w.@+-]+$'
    message = _(
        'Enter a valid username. This value may contain only letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = 0
````
