# Path Disambiguation Context for astropy__astropy-13579

Source: public GitHub tree for `astropy/astropy` at base commit `0df94ff7097961e92fd7812036a24b145bc13ca8`.

Purpose: resolve worker-derived path proposals that referenced non-existent SlicedLowLevelWCS module names.

Use only existing source paths from this list if you choose to return a diff:

- `astropy/wcs/wcsapi/__init__.py`
- `astropy/wcs/wcsapi/fitswcs.py`
- `astropy/wcs/wcsapi/high_level_api.py`
- `astropy/wcs/wcsapi/high_level_wcs_wrapper.py`
- `astropy/wcs/wcsapi/low_level_api.py`
- `astropy/wcs/wcsapi/sliced_low_level_wcs.py`
- `astropy/wcs/wcsapi/utils.py`
- `astropy/wcs/wcsapi/wrappers/__init__.py`
- `astropy/wcs/wcsapi/wrappers/base.py`
- `astropy/wcs/wcsapi/wrappers/sliced_wcs.py`

Excluded: tests, raw SWE-bench dataset rows, gold patches, test patches, FAIL_TO_PASS, PASS_TO_PASS, and hidden evaluator labels.
