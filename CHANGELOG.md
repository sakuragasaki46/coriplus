# Changelog

## 0.6-dev

* Added user adminship. Admins are users with very high privileges. Adminship can be assigned only at script level (not from the web).
* Now one's messages won't show up in public timeline.
* Added user profile info. Now you can specify your full name, biography, location, birth year, website, Facebook and Instagram. Of course this is totally optional.
* Added reference to terms of service and privacy policy on signup page.
* When visiting signup page as logged in, user should confirm he wants to create another account in order to do it.
* Moved user stats inside profile info.

## 0.5.0

* Removed `type` and `info` fields from `Message` table and merged `privacy` field, previously into a separate table, into that table. In order to make the app work, when upgrading you should run the `migrate_0_4_to_0_5.py` script. 
* Added flask-login dependency. Now, user logins can be persistent up to 365 days. 
* Rewritten `enrich` filter, correcting a serious security flaw. The new filter uses a tokenizer and escapes all non-markup text. Plus, now the `+` of the mention is visible, but weakened; newlines are now visible in the message. 
* Now you can edit or change privacy to messages after they are published. After a message it's edited, the date and time of the message is changed.
* Fixed a bug when uploading.
* Moved the site name, previously hard-coded into templates, into `config.py`.

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
