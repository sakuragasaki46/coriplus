# Changelog

## 0.5-dev

* Removed `type` and `info` fields from `Message` table and merged `privacy` field, previously into a separate table, into that table. In order to make the app work, when upgrading you should run the `migrate_0_4_to_0_5.py` script. 
* Added flask-login dependency. Now, user logins can be persistent up to 365 days. 
* Rewritten `enrich` filter, correcting a serious security flaw. The new filter uses a tokenizer and escapes all non-markup text. Plus, now the `+` of the mention is visible, but weakened; newlines are now visible in the message. 
* Now you can edit or change privacy to messages after they are published. After a message it's edited, the date and time of the message is changed.
* Fixed a bug when uploading.

## 0.4.0

* Adding quick mention. You can now create a message mentioning another user in one click.
* Added mention notifications.
* Adding an about section, footer, version number and license.
* Improved repository with better README, CHANGELOG, requirements.txt and option to specify port on run_example.py
* Split app config from app module.
* Added the capability to specify post privacy. Now you can choose to post your message to the public, to friends (mutual followers) or only you.
* Added the capability to log in specifying email instead of username.
* Added the precise date of a message as a tooltip when hovering over the human-readable date.
* Now Python 3 is enforced.

## 0.3

* This version (and every version below) is not a true version, but was added later by repository owner in changelog only.
* Added notifications (including count on top bar) and public timeline.

## 0.2

* Added file upload.

## 0.1

* Initial commit.
