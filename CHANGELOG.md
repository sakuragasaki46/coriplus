# Changelog

## 0.9-dev

* Website redesign: added some material icons, implemented via a `inline_svg` function, injected by default in templates and defined in `utils.py`.
* Added positive feedback mechanism: now you can +1 a message. So, `score_message_add` and `score_message_remove` API endpoints were added, and `MessageUpvote` table was created.
* Added notifications support for API.
* Added `create_account` endpoint to API. This endpoint does not require an access token.
* Added `explore`, `notifications_count`, `notifications` and `notifications_seen` endpoints.
* Added `has_more` field to feed endpoints (`feed`, `explore` and `profile_feed`).
* Added `join_date` field into `user` object of `profile_info` endpoint, for more profile transparency.
* Added `/favicon.ico`.
* Fixed some bugs when creating mentions and using offsets in feeds.

## 0.8.0

* Added the admin dashboard, accessible from `/admin/` via basic auth. Only users with admin right can access it. Added endpoints `admin.reports` and `admin.reports_detail`.
* Safety is our top priority: added the ability to report someone other's post for everything violating the site's Terms of Service. The current reasons for reporting are: spam, impersonation, pornography, violence, harassment or bullying, hate speech or symbols, self injury, sale or promotion of firearms or drugs, and underage use.
* Schema changes: moved `full_name` field from table `userprofile` to table `user` for search improvement reasons. Added `Report` model.
* Now `profile_search` API endpoint searches by full name too.
* Adding `messages_count`, `followers_count` and `following_count` to `profile_info` API endpoint (what I've done to 0.7.1 too).
* Adding `create2` API endpoint that accepts media, due to an issue with the `create` endpoint that would make it incompatible.
* Adding media URLs to messages in API.
* Added `relationships_follow`, `relationships_unfollow`, `username_availability`, `edit_profile`, `request_edit` and `confirm_edit` endpoints to API.
* Added `url` utility to model `Upload`.
* Changed default `robots.txt`, adding report and admin-related lines.
* Released official [Android client](https://github.com/sakuragasaki46/coriplusapp/releases/tag/v0.8.0).

## 0.7.1-dev

* Adding `messages_count`, `followers_count` and `following_count` to `profile_info` API endpoint (forgot to release).

## 0.7.0

* Biggest change: unpacking modules. The single `app.py` file has become an `app` package, with submodules `models.py`, `utils.py`, `filters.py`, `website.py` and `ajax.py`. There is also a new module `api.py`.
* Now `/about/` shows Python and Flask versions.
* Now the error 404 handler returns HTTP 404.
* Added user followers and following lists, accessible via `/+<username>/followers` and `/+<username>/following` and from the profile info box, linked to the followers/following number.
* Added the page for permanent deletion of messages. Well, you cannot delete them yet. It's missing a function that checks the CSRF-Token.
* Renamed template `private_messages.html` to `feed.html`.
* Added the capability to change password.
* Corrected a bug into `pwdhash`: it accepted an argument, but pulled data from the form instead of processing it. Now it uses the argument.
* Schema changes: added column `telegram` to `UserProfile` table. To update schema, execute the script `migrate_0_6_to_0_7.py`
* Adding public API. Each of the API endpoints take a mandatory query string argument: the access token, generated by a separate endpoint at `/get_access_token` and stored into the client. All API routes start with `/api/V1`. Added endpoints `feed`, `create`, `profile_info`, `profile_feed` and `profile_search`.
* Planning to release mobile app for Android. 

## 0.6.0

* Added user adminship. Admins are users with very high privileges. Adminship can be assigned only at script level (not from the web).
* Now one's messages won't show up in public timeline.
* Added user profile info. Now you can specify your full name, biography, location, birth year, website, Facebook and Instagram. Of course this is totally optional.
* Added reference to terms of service and privacy policy on signup page.
* When visiting signup page as logged in, user should confirm he wants to create another account in order to do it.
* Moved user stats inside profile info.
* Adding Privacy Policy.
* Adding links to Terms and Privacy at the bottom of any page.

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
