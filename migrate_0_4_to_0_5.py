import config, sqlite3

conn = sqlite3.connect(config.DATABASE)

if __name__ == '__main__':
  conn.executescript('''
BEGIN TRANSACTION;
  CREATE TABLE new_message ("id" INTEGER NOT NULL PRIMARY KEY, "user_id" INTEGER NOT NULL, "text" TEXT NOT NULL, "pub_date" DATETIME NOT NULL, "privacy" INTEGER DEFAULT 0, FOREIGN KEY ("user_id") REFERENCES "user" ("id"));
  INSERT INTO new_message (id, user_id, text, pub_date, privacy) SELECT t1.id, t1.user_id, t1.text, t1.pub_date, t2.value FROM message AS t1 LEFT JOIN messageprivacy AS t2 ON t2.message_id = t1.id;
  UPDATE new_message SET privacy = 0 WHERE privacy IS NULL;
  DROP TABLE message;
  DROP TABLE messageprivacy;
  ALTER TABLE new_message RENAME TO message;
COMMIT;
''')
