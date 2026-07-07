# SWE-bench Task django__django-11099

Repository: django/django
Base commit: d26b2424437dabeeca94d7900b37d2df4410da0c
Version: 3.0
Difficulty: <15 min fix

## Problem Statement

UsernameValidator allows trailing newline in usernames
Description
	
ASCIIUsernameValidator and UnicodeUsernameValidator use the regex 
r'^[\w.@+-]+$'
The intent is to only allow alphanumeric characters as well as ., @, +, and -. However, a little known quirk of Python regexes is that $ will also match a trailing newline. Therefore, the user name validators will accept usernames which end with a newline. You can avoid this behavior by instead using \A and \Z to terminate regexes. For example, the validator regex could be changed to
r'\A[\w.@+-]+\Z'
in order to reject usernames that end with a newline.
I am not sure how to officially post a patch, but the required change is trivial - using the regex above in the two validators in contrib.auth.validators.

## Candidate Policy

Produce a worker-derived unified diff against the base commit. Use only this packet, repository inspection, and your own reasoning.

## Worker-Visible Repository Source Context

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

## TuringOS Failure-Memory Broadcast Rules
<!-- BEGIN_TURINGOS_BROADCAST_RULES -->
- PATCH_FORMAT: Return only a complete unified diff that starts with diff --git and includes valid file headers and hunk headers; do not use markdown fences, prose, ellipses, or truncated hunks. (source rule m3p6_br_001_unified_diff_shape)
- WORKER_POLICY: Edit implementation source files only; do not modify tests, testing helpers, fixtures, generated reports, benchmark evidence, or evaluation files. (source rule m3p6_br_002_source_only)
- SOURCE_CONTEXT_DISCIPLINE: Base the patch on the worker-visible capsule and audited source context; prefer paths already present in that context unless the capsule itself makes another source-only path necessary. (source rule m3p6_br_003_context_discipline)
- PATCH_APPLY: Prefer small, localized hunks with enough unchanged context for git apply --check to succeed against the provided source snapshot. (source rule m3p6_br_004_apply_check)
<!-- END_TURINGOS_BROADCAST_RULES -->
