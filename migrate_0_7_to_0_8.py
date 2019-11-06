import sqlite3

import sqlite3

conn = sqlite3.connect('coriplus.sqlite')

if __name__ == '__main__':
    conn.executescript('''
BEGIN TRANSACTION;
  CREATE TABLE "new_userprofile" ("user_id" INTEGER NOT NULL PRIMARY KEY, "biography" TEXT NOT NULL, "location" INTEGER, "year" INTEGER, "website" TEXT, "instagram" TEXT, "facebook" TEXT, telegram TEXT, FOREIGN KEY ("user_id") REFERENCES "user" ("id"));
  CREATE TABLE "new_user" ("id" INTEGER NOT NULL PRIMARY KEY, "username" VARCHAR(30) NOT NULL, "full_name" VARCHAR(30), "password" VARCHAR(255) NOT NULL, "email" VARCHAR(255) NOT NULL, "birthday" DATE NOT NULL, "join_date" DATETIME NOT NULL, "is_disabled" INTEGER NOT NULL);
  INSERT INTO new_user (id, username, full_name, password, email, birthday, join_date, is_disabled) SELECT t1.id, t1.username, t2.full_name, t1.password, t1.email, t1.birthday, t1.join_date, t1.is_disabled FROM user AS t1 LEFT JOIN userprofile AS t2 ON t1.id = t2.user_id;
  INSERT INTO new_userprofile (user_id, biography, location, year, website, instagram, facebook, telegram) SELECT user_id, biography, location, year, website, instagram, facebook, telegram FROM userprofile;
  UPDATE new_user SET full_name = username WHERE username IS NULL;
  DROP TABLE user;
  DROP TABLE userprofile;
  ALTER TABLE new_user RENAME TO user;
  ALTER TABLE new_userprofile RENAME TO userprofile;
COMMIT;
''')
