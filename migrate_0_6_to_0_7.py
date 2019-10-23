import sqlite3

conn = sqlite3.connect('coriplus.sqlite')

if __name__ == '__main__':
    conn.executescript('''
BEGIN TRANSACTION;
  ALTER TABLE userprofile ADD COLUMN telegram TEXT;
COMMIT;
''')
