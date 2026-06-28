# Stage13 Tool Call Lineage

Each Native API Worker receipt is assembled from `ToolReceiptAppended` event IDs.

## django__django-12039
- `ta_stage13_3ca4462c9852c1a6_1` `list_dir` `SUCCESS` -> `mu:6726cbea0eba2314f0476447ec52ca8d97b50bfcc2a9a38da23ae1a016eafc97`
- `ta_stage13_3ca4462c9852c1a6_2` `read_file` `SUCCESS` -> `mu:c76ee99607ce385866c51dc629bb5f8552690642f6dbff20dd9501d5023ce2b6`
- `ta_stage13_3ca4462c9852c1a6_3` `grep` `SUCCESS` -> `mu:8f66c2ce7f326570c0f287452d8cbcbde7766c8818a2a27958dfa6de77045116`
- `ta_stage13_3ca4462c9852c1a6_4` `apply_patch` `SUCCESS` -> `mu:b07eebb8235fac8a0bbe73ce6c68d71fb96987b4a1dd669e76c05fb80ef694c4`
- `ta_stage13_3ca4462c9852c1a6_5` `write_file` `SUCCESS` -> `mu:2d2697a895229da31955d363492e7c8cf5aa563288659e2e714b3a9acfb6ccb2`
- `ta_stage13_3ca4462c9852c1a6_6` `run_command` `SUCCESS` -> `mu:8f0d1c3d56e5d90a65ed3889e6fc1c0c636f5eb6aec2f122bb0964731f3ab07f`

## django__django-12050
- `ta_stage13_8c367ffa892da4c2_1` `list_dir` `SUCCESS` -> `mu:5219eefbdbd004908212e86b5241b4d67badf36869764032949c2ed3af0d9fef`
- `ta_stage13_8c367ffa892da4c2_2` `read_file` `SUCCESS` -> `mu:5ccdd3b42d757ef261fa79656b9504660a53d2814204e5fd5ec442d54f3af0f2`
- `ta_stage13_8c367ffa892da4c2_3` `grep` `FAILED` -> `mu:48f60cd3c7b5fb68b54f26e01b8e1b391bacad174c092bde9c628ae7b786c1c7`
- `ta_stage13_8c367ffa892da4c2_4` `apply_patch` `FAILED` -> `mu:4876c3c2dce316b4ed6c75b59bf4cb0edadd1340701e92b38ffcdb688e672f68`
- `ta_stage13_8c367ffa892da4c2_5` `write_file` `DENIED` -> `mu:4bec675e6e875a07f8deb206260e7d3afad1e8b09b7fc01f53dd6b872a5e8d44`
- `ta_stage13_8c367ffa892da4c2_6` `run_command` `FAILED` -> `mu:5290ef8fa57c435e645b0b55449128a498e5ad232860fdfb1cf76b1f9c52bf83`
- `ta_stage13_8c367ffa892da4c2_7` `run_command` `TIMEOUT` -> `mu:747de58ec66f23a69897e4e6e8d848c9a33ba180a3f2f6d2e354597c6f8a1a1f`
