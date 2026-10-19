"""MySQL write-path contract tests using a fake transaction (no server needed)."""

from finrecon import database
from finrecon.reconciliation import reconcile


class FakeCursor:
    def __init__(self):
        self.lastrowid = 17
        self.statements = []
        self.batches = []
        self.closed = False

    def execute(self, statement, params):
        self.statements.append((statement, params))

    def executemany(self, statement, rows):
        self.batches.append((statement, rows))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cur = FakeCursor()
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def start_transaction(self):
        self.started = True

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_mysql_run_snapshot_payload(monkeypatch, simple_pair):
    conn = FakeConnection()
    monkeypatch.setattr(database, "initialize_mysql", lambda: conn)
    ledger, bank = simple_pair
    cases = reconcile(ledger, bank)
    run_id = database.save_run(ledger, bank, cases)
    assert run_id == 17
    assert conn.started and conn.committed and conn.closed and not conn.rolled_back
    assert len(conn.cur.batches) == 3  # ledger, bank, reconciliation cases
    assert [len(rows) for _, rows in conn.cur.batches] == [2, 2, 2]
    assert conn.cur.statements[0][1][-1] == 100.0  # match rate


def test_mysql_database_identifier_is_validated(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "bad;DROP TABLE")
    try:
        database.mysql_config()
    except ValueError as exc:
        assert "safe SQL identifier" in str(exc)
    else:
        raise AssertionError("Unsafe database identifier was accepted")
