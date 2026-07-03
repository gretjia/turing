# SWE-bench Task pylint-dev__pylint-7080

Repository: pylint-dev/pylint
Base commit: 3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0
Version: 2.15
Difficulty: 15 min - 1 hour

## Problem Statement

`--recursive=y` ignores `ignore-paths`
### Bug description

When running recursively, it seems `ignore-paths` in my settings in pyproject.toml is completely ignored

### Configuration

```ini
[tool.pylint.MASTER]
ignore-paths = [
  # Auto generated
  "^src/gen/.*$",
]
```


### Command used

```shell
pylint --recursive=y src/
```


### Pylint output

```shell
************* Module region_selection
src\region_selection.py:170:0: R0914: Too many local variables (17/15) (too-many-locals)
************* Module about
src\gen\about.py:2:0: R2044: Line with empty comment (empty-comment)
src\gen\about.py:4:0: R2044: Line with empty comment (empty-comment)
src\gen\about.py:57:0: C0301: Line too long (504/120) (line-too-long)
src\gen\about.py:12:0: C0103: Class name "Ui_AboutAutoSplitWidget" doesn't conform to '_?_?[a-zA-Z]+?$' pattern (invalid-name)
src\gen\about.py:12:0: R0205: Class 'Ui_AboutAutoSplitWidget' inherits from object, can be safely removed from bases in python3 (useless-object-inheritance)
src\gen\about.py:13:4: C0103: Method name "setupUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\about.py:13:22: C0103: Argument name "AboutAutoSplitWidget" doesn't conform to snake_case naming style (invalid-name)
src\gen\about.py:53:4: C0103: Method name "retranslateUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\about.py:53:28: C0103: Argument name "AboutAutoSplitWidget" doesn't conform to snake_case naming style (invalid-name)
src\gen\about.py:24:8: W0201: Attribute 'ok_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\about.py:27:8: W0201: Attribute 'created_by_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\about.py:30:8: W0201: Attribute 'version_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\about.py:33:8: W0201: Attribute 'donate_text_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\about.py:37:8: W0201: Attribute 'donate_button_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\about.py:43:8: W0201: Attribute 'icon_label' defined outside __init__ (attribute-defined-outside-init)
************* Module design
src\gen\design.py:2:0: R2044: Line with empty comment (empty-comment)
src\gen\design.py:4:0: R2044: Line with empty comment (empty-comment)
src\gen\design.py:328:0: C0301: Line too long (123/120) (line-too-long)
src\gen\design.py:363:0: C0301: Line too long (125/120) (line-too-long)
src\gen\design.py:373:0: C0301: Line too long (121/120) (line-too-long)
src\gen\design.py:412:0: C0301: Line too long (131/120) (line-too-long)
src\gen\design.py:12:0: C0103: Class name "Ui_MainWindow" doesn't conform to '_?_?[a-zA-Z]+?$' pattern (invalid-name)
src\gen\design.py:308:8: C0103: Attribute name "actionSplit_Settings" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:318:8: C0103: Attribute name "actionCheck_for_Updates_on_Open" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:323:8: C0103: Attribute name "actionLoop_Last_Split_Image_To_First_Image" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:325:8: C0103: Attribute name "actionAuto_Start_On_Reset" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:327:8: C0103: Attribute name "actionGroup_dummy_splits_when_undoing_skipping" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:12:0: R0205: Class 'Ui_MainWindow' inherits from object, can be safely removed from bases in python3 (useless-object-inheritance)
src\gen\design.py:12:0: R0902: Too many instance attributes (69/15) (too-many-instance-attributes)
src\gen\design.py:13:4: C0103: Method name "setupUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:13:22: C0103: Argument name "MainWindow" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:16:8: C0103: Variable name "sizePolicy" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:13:4: R0915: Too many statements (339/50) (too-many-statements)
src\gen\design.py:354:4: C0103: Method name "retranslateUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:354:28: C0103: Argument name "MainWindow" doesn't conform to snake_case naming style (invalid-name)
src\gen\design.py:354:4: R0915: Too many statements (61/50) (too-many-statements)
src\gen\design.py:31:8: W0201: Attribute 'central_widget' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:33:8: W0201: Attribute 'x_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:36:8: W0201: Attribute 'select_region_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:40:8: W0201: Attribute 'start_auto_splitter_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:44:8: W0201: Attribute 'reset_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:49:8: W0201: Attribute 'undo_split_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:54:8: W0201: Attribute 'skip_split_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:59:8: W0201: Attribute 'check_fps_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:63:8: W0201: Attribute 'fps_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:66:8: W0201: Attribute 'live_image' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:75:8: W0201: Attribute 'current_split_image' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:81:8: W0201: Attribute 'current_image_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:85:8: W0201: Attribute 'width_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:88:8: W0201: Attribute 'height_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:91:8: W0201: Attribute 'fps_value_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:95:8: W0201: Attribute 'width_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:101:8: W0201: Attribute 'height_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:107:8: W0201: Attribute 'capture_region_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:111:8: W0201: Attribute 'current_image_file_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:115:8: W0201: Attribute 'take_screenshot_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:119:8: W0201: Attribute 'x_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:128:8: W0201: Attribute 'y_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:136:8: W0201: Attribute 'y_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:139:8: W0201: Attribute 'align_region_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:143:8: W0201: Attribute 'select_window_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:147:8: W0201: Attribute 'browse_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:151:8: W0201: Attribute 'split_image_folder_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:154:8: W0201: Attribute 'split_image_folder_input' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:158:8: W0201: Attribute 'capture_region_window_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:162:8: W0201: Attribute 'image_loop_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:165:8: W0201: Attribute 'similarity_viewer_groupbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:169:8: W0201: Attribute 'table_live_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:173:8: W0201: Attribute 'table_highest_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:177:8: W0201: Attribute 'table_threshold_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:181:8: W0201: Attribute 'line_1' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:186:8: W0201: Attribute 'table_current_image_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:189:8: W0201: Attribute 'table_reset_image_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:192:8: W0201: Attribute 'line_2' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:197:8: W0201: Attribute 'line_3' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:202:8: W0201: Attribute 'line_4' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:207:8: W0201: Attribute 'line_5' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:212:8: W0201: Attribute 'table_current_image_live_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:216:8: W0201: Attribute 'table_current_image_highest_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:220:8: W0201: Attribute 'table_current_image_threshold_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:224:8: W0201: Attribute 'table_reset_image_live_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:228:8: W0201: Attribute 'table_reset_image_highest_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:232:8: W0201: Attribute 'table_reset_image_threshold_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:236:8: W0201: Attribute 'reload_start_image_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:240:8: W0201: Attribute 'start_image_status_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:243:8: W0201: Attribute 'start_image_status_value_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:246:8: W0201: Attribute 'image_loop_value_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:249:8: W0201: Attribute 'previous_image_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:254:8: W0201: Attribute 'next_image_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:296:8: W0201: Attribute 'menu_bar' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:299:8: W0201: Attribute 'menu_help' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:301:8: W0201: Attribute 'menu_file' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:304:8: W0201: Attribute 'action_view_help' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:306:8: W0201: Attribute 'action_about' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:308:8: W0201: Attribute 'actionSplit_Settings' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:310:8: W0201: Attribute 'action_save_profile' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:312:8: W0201: Attribute 'action_load_profile' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:314:8: W0201: Attribute 'action_save_profile_as' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:316:8: W0201: Attribute 'action_check_for_updates' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:318:8: W0201: Attribute 'actionCheck_for_Updates_on_Open' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:323:8: W0201: Attribute 'actionLoop_Last_Split_Image_To_First_Image' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:325:8: W0201: Attribute 'actionAuto_Start_On_Reset' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:327:8: W0201: Attribute 'actionGroup_dummy_splits_when_undoing_skipping' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:329:8: W0201: Attribute 'action_settings' defined outside __init__ (attribute-defined-outside-init)
src\gen\design.py:331:8: W0201: Attribute 'action_check_for_updates_on_open' defined outside __init__ (attribute-defined-outside-init)
************* Module resources_rc
src\gen\resources_rc.py:1:0: C0302: Too many lines in module (2311/1000) (too-many-lines)
src\gen\resources_rc.py:8:0: C0103: Constant name "qt_resource_data" doesn't conform to UPPER_CASE naming style (invalid-name)
src\gen\resources_rc.py:2278:0: C0103: Constant name "qt_resource_name" doesn't conform to UPPER_CASE naming style (invalid-name)
src\gen\resources_rc.py:2294:0: C0103: Constant name "qt_resource_struct" doesn't conform to UPPER_CASE naming style (invalid-name)
src\gen\resources_rc.py:2305:0: C0103: Function name "qInitResources" doesn't conform to snake_case naming style (invalid-name)
src\gen\resources_rc.py:2308:0: C0103: Function name "qCleanupResources" doesn't conform to snake_case naming style (invalid-name)
************* Module settings
src\gen\settings.py:2:0: R2044: Line with empty comment (empty-comment)
src\gen\settings.py:4:0: R2044: Line with empty comment (empty-comment)
src\gen\settings.py:61:0: C0301: Line too long (158/120) (line-too-long)
src\gen\settings.py:123:0: C0301: Line too long (151/120) (line-too-long)
src\gen\settings.py:209:0: C0301: Line too long (162/120) (line-too-long)
src\gen\settings.py:214:0: C0301: Line too long (121/120) (line-too-long)
src\gen\settings.py:221:0: C0301: Line too long (177/120) (line-too-long)
src\gen\settings.py:223:0: C0301: Line too long (181/120) (line-too-long)
src\gen\settings.py:226:0: C0301: Line too long (461/120) (line-too-long)
src\gen\settings.py:228:0: C0301: Line too long (192/120) (line-too-long)
src\gen\settings.py:12:0: C0103: Class name "Ui_DialogSettings" doesn't conform to '_?_?[a-zA-Z]+?$' pattern (invalid-name)
src\gen\settings.py:12:0: R0205: Class 'Ui_DialogSettings' inherits from object, can be safely removed from bases in python3 (useless-object-inheritance)
src\gen\settings.py:12:0: R0902: Too many instance attributes (35/15) (too-many-instance-attributes)
src\gen\settings.py:13:4: C0103: Method name "setupUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\settings.py:13:22: C0103: Argument name "DialogSettings" doesn't conform to snake_case naming style (invalid-name)
src\gen\settings.py:16:8: C0103: Variable name "sizePolicy" doesn't conform to snake_case naming style (invalid-name)
src\gen\settings.py:13:4: R0915: Too many statements (190/50) (too-many-statements)
src\gen\settings.py:205:4: C0103: Method name "retranslateUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\settings.py:205:28: C0103: Argument name "DialogSettings" doesn't conform to snake_case naming style (invalid-name)
src\gen\settings.py:26:8: W0201: Attribute 'capture_settings_groupbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:29:8: W0201: Attribute 'fps_limit_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:36:8: W0201: Attribute 'fps_limit_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:40:8: W0201: Attribute 'live_capture_region_checkbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:46:8: W0201: Attribute 'capture_method_combobox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:49:8: W0201: Attribute 'capture_method_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:52:8: W0201: Attribute 'capture_device_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:55:8: W0201: Attribute 'capture_device_combobox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:59:8: W0201: Attribute 'image_settings_groupbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:65:8: W0201: Attribute 'default_comparison_method' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:73:8: W0201: Attribute 'default_comparison_method_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:76:8: W0201: Attribute 'default_pause_time_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:80:8: W0201: Attribute 'default_pause_time_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:87:8: W0201: Attribute 'default_similarity_threshold_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:92:8: W0201: Attribute 'default_similarity_threshold_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:98:8: W0201: Attribute 'loop_splits_checkbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:104:8: W0201: Attribute 'custom_image_settings_info_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:111:8: W0201: Attribute 'default_delay_time_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:116:8: W0201: Attribute 'default_delay_time_spinbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:121:8: W0201: Attribute 'hotkeys_groupbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:127:8: W0201: Attribute 'set_pause_hotkey_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:131:8: W0201: Attribute 'split_input' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:137:8: W0201: Attribute 'undo_split_input' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:143:8: W0201: Attribute 'split_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:146:8: W0201: Attribute 'reset_input' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:152:8: W0201: Attribute 'set_undo_split_hotkey_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:156:8: W0201: Attribute 'reset_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:159:8: W0201: Attribute 'set_reset_hotkey_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:163:8: W0201: Attribute 'set_split_hotkey_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:167:8: W0201: Attribute 'pause_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:170:8: W0201: Attribute 'pause_input' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:176:8: W0201: Attribute 'undo_split_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:179:8: W0201: Attribute 'set_skip_split_hotkey_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:183:8: W0201: Attribute 'skip_split_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\settings.py:186:8: W0201: Attribute 'skip_split_input' defined outside __init__ (attribute-defined-outside-init)
************* Module update_checker
src\gen\update_checker.py:2:0: R2044: Line with empty comment (empty-comment)
src\gen\update_checker.py:4:0: R2044: Line with empty comment (empty-comment)
src\gen\update_checker.py:12:0: C0103: Class name "Ui_UpdateChecker" doesn't conform to '_?_?[a-zA-Z]+?$' pattern (invalid-name)
src\gen\update_checker.py:12:0: R0205: Class 'Ui_UpdateChecker' inherits from object, can be safely removed from bases in python3 (useless-object-inheritance)
src\gen\update_checker.py:13:4: C0103: Method name "setupUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:13:22: C0103: Argument name "UpdateChecker" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:17:8: C0103: Variable name "sizePolicy" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:33:8: C0103: Variable name "sizePolicy" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:13:4: R0915: Too many statements (56/50) (too-many-statements)
src\gen\update_checker.py:71:4: C0103: Method name "retranslateUi" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:71:28: C0103: Argument name "UpdateChecker" doesn't conform to snake_case naming style (invalid-name)
src\gen\update_checker.py:31:8: W0201: Attribute 'update_status_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:39:8: W0201: Attribute 'current_version_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:42:8: W0201: Attribute 'latest_version_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:45:8: W0201: Attribute 'go_to_download_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:48:8: W0201: Attribute 'left_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:52:8: W0201: Attribute 'right_button' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:55:8: W0201: Attribute 'current_version_number_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:59:8: W0201: Attribute 'latest_version_number_label' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:63:8: W0201: Attribute 'do_not_ask_again_checkbox' defined outside __init__ (attribute-defined-outside-init)
src\gen\update_checker.py:1:0: R0401: Cyclic import (region_capture -> region_selection) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (error_messages -> user_profile -> region_capture -> region_selection) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplitImage -> split_parser) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoControlledWorker -> error_messages -> AutoSplit) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> user_profile -> region_capture -> region_selection -> error_messages) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplitImage -> error_messages -> user_profile) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> menu_bar -> user_profile -> region_capture -> region_selection -> error_messages) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> region_selection -> error_messages) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> error_messages) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (error_messages -> user_profile -> region_selection) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (error_messages -> user_profile) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplitImage -> split_parser -> error_messages -> user_profile) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> menu_bar -> region_selection -> error_messages) (cyclic-import)
src\gen\update_checker.py:1:0: R0401: Cyclic import (AutoSplit -> menu_bar -> error_messages) (cyclic-import)

--------------------------------------------------------------------------
Your code has been rated at -158.32/10 (previous run: -285.20/10, +126.88)
```


### Expected behavior

src\gen\* should not be checked

### Pylint version

```shell
pylint 2.14.1
astroid 2.11.5
Python 3.9.6 (tags/v3.9.6:db3ff76, Jun 28 2021, 15:26:21) [MSC v.1929 64 bit (AMD64)]
```


### OS / Environment

Windows 10.0.19044


### Additional dependencies

_No response_

## Candidate Policy

Produce a worker-derived unified diff against the base commit. Use only this packet, repository inspection, and your own reasoning.

## Worker-Visible Repository Source Context

# Source Context for pylint-dev__pylint-7080

Repository: pylint-dev/pylint
Base commit: 3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0
Selection rule: worker-derived candidate diff paths only.
Forbidden fields remain excluded: gold patch, test patch, FAIL_TO_PASS, PASS_TO_PASS, hints.

## pylint/lint/expand_modules.py

````text
# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from re import Pattern

from astroid import modutils

from pylint.typing import ErrorDescriptionDict, ModuleDescriptionDict


def _modpath_from_file(filename: str, is_namespace: bool, path: list[str]) -> list[str]:
    def _is_package_cb(inner_path: str, parts: list[str]) -> bool:
        return modutils.check_modpath_has_init(inner_path, parts) or is_namespace

    return modutils.modpath_from_file_with_callback(
        filename, path=path, is_package_cb=_is_package_cb
    )


def get_python_path(filepath: str) -> str:
    """TODO This get the python path with the (bad) assumption that there is always
    an __init__.py.

    This is not true since python 3.3 and is causing problem.
    """
    dirname = os.path.realpath(os.path.expanduser(filepath))
    if not os.path.isdir(dirname):
        dirname = os.path.dirname(dirname)
    while True:
        if not os.path.exists(os.path.join(dirname, "__init__.py")):
            return dirname
        old_dirname = dirname
        dirname = os.path.dirname(dirname)
        if old_dirname == dirname:
            return os.getcwd()


def _is_in_ignore_list_re(element: str, ignore_list_re: list[Pattern[str]]) -> bool:
    """Determines if the element is matched in a regex ignore-list."""
    return any(file_pattern.match(element) for file_pattern in ignore_list_re)


def _is_ignored_file(
    element: str,
    ignore_list: list[str],
    ignore_list_re: list[Pattern[str]],
    ignore_list_paths_re: list[Pattern[str]],
) -> bool:
    basename = os.path.basename(element)
    return (
        basename in ignore_list
        or _is_in_ignore_list_re(basename, ignore_list_re)
        or _is_in_ignore_list_re(element, ignore_list_paths_re)
    )


def expand_modules(
    files_or_modules: Sequence[str],
    ignore_list: list[str],
    ignore_list_re: list[Pattern[str]],
    ignore_list_paths_re: list[Pattern[str]],
) -> tuple[list[ModuleDescriptionDict], list[ErrorDescriptionDict]]:
    """Take a list of files/modules/packages and return the list of tuple
    (file, module name) which have to be actually checked.
    """
    result: list[ModuleDescriptionDict] = []
    errors: list[ErrorDescriptionDict] = []
    path = sys.path.copy()

    for something in files_or_modules:
        basename = os.path.basename(something)
        if _is_ignored_file(
            something, ignore_list, ignore_list_re, ignore_list_paths_re
        ):
            continue
        module_path = get_python_path(something)
        additional_search_path = [".", module_path] + path
        if os.path.exists(something):
            # this is a file or a directory
            try:
                modname = ".".join(
                    modutils.modpath_from_file(something, path=additional_search_path)
                )
            except ImportError:
                modname = os.path.splitext(basename)[0]
            if os.path.isdir(something):
                filepath = os.path.join(something, "__init__.py")
            else:
                filepath = something
        else:
            # suppose it's a module or package
            modname = something
            try:
                filepath = modutils.file_from_modpath(
                    modname.split("."), path=additional_search_path
                )
                if filepath is None:
                    continue
            except (ImportError, SyntaxError) as ex:
                # The SyntaxError is a Python bug and should be
                # removed once we move away from imp.find_module: https://bugs.python.org/issue10588
                errors.append({"key": "fatal", "mod": modname, "ex": ex})
                continue
        filepath = os.path.normpath(filepath)
        modparts = (modname or something).split(".")
        try:
            spec = modutils.file_info_from_modpath(
                modparts, path=additional_search_path
            )
        except ImportError:
            # Might not be acceptable, don't crash.
            is_namespace = False
            is_directory = os.path.isdir(something)
        else:
            is_namespace = modutils.is_namespace(spec)
            is_directory = modutils.is_directory(spec)
        if not is_namespace:
            result.append(
                {
                    "path": filepath,
                    "name": modname,
                    "isarg": True,
                    "basepath": filepath,
                    "basename": modname,
                }
            )
        has_init = (
            not (modname.endswith(".__init__") or modname == "__init__")
            and os.path.basename(filepath) == "__init__.py"
        )
        if has_init or is_namespace or is_directory:
            for subfilepath in modutils.get_module_files(
                os.path.dirname(filepath), ignore_list, list_all=is_namespace
            ):
                if filepath == subfilepath:
                    continue
                if _is_in_ignore_list_re(
                    os.path.basename(subfilepath), ignore_list_re
                ) or _is_in_ignore_list_re(subfilepath, ignore_list_paths_re):
                    continue

                modpath = _modpath_from_file(
                    subfilepath, is_namespace, path=additional_search_path
                )
                submodname = ".".join(modpath)
                result.append(
                    {
                        "path": subfilepath,
                        "name": submodname,
                        "isarg": False,
                        "basepath": filepath,
                        "basename": modname,
                    }
                )
    return result, errors
````

## TuringOS Failure-Memory Broadcast Rules
<!-- BEGIN_TURINGOS_BROADCAST_RULES -->
(none)
<!-- END_TURINGOS_BROADCAST_RULES -->
