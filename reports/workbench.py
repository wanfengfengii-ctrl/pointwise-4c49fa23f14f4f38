import argparse
import json
import sqlite3
import sys
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from compare.admission import receive
from compare.inbox import initialize_inbox
from compare.pairing import compare_pair
from issue.archive import get_issue, initialize_issue_store
from issue.evidence import FrozenEvidence
from issue.freeze import freeze
from recipes.register import register
from recipes.repository import initialize_recipe_store
from records.intake import check_record
from records.ledger import initialize_trace_store
from records.traceback import get_trace
from reports.export import report_to_data
from reports.lookup import get_report
from reports.publish import initialize_report_store


SOURCE = 'source.sqlite3'
CENTER = 'center.sqlite3'
SAMPLE = Path(__file__).resolve().parents[1] / 'samples' / 'workday.json'


@contextmanager
def open_database(path: str | Path, *, create: bool = False):
    mode = 'rwc' if create else 'rw'
    uri = Path(path).resolve().as_uri() + f'?mode={mode}'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute('PRAGMA foreign_keys = ON')
        yield db


def initialize_workspace(directory: str | Path) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    with open_database(root / SOURCE, create=True) as source:
        source.execute('BEGIN IMMEDIATE')
        with source:
            initialize_recipe_store(source)
            initialize_trace_store(source)
            initialize_issue_store(source)
    with open_database(root / CENTER, create=True) as center:
        center.execute('BEGIN IMMEDIATE')
        with center:
            initialize_inbox(center)
            initialize_report_store(center)


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding='utf-8'))


def run_workday(directory: str | Path) -> dict:
    root = Path(directory)
    initialize_workspace(root)
    sample = load_sample()
    with open_database(root / SOURCE) as source:
        old_id = register(source, **sample['old'])
        trials = [check_record(source, old_id, **trial) for trial in sample['trials']]
        new_id = register(source, **sample['new'])
        old_issue = freeze(source, old_id)
        new_issue = freeze(source, new_id)
    with open_database(root / CENTER) as center:
        left_id = receive(center, old_issue.issue_id, old_issue.wire)
        right_id = receive(center, new_issue.issue_id, new_issue.wire)
        signed = compare_pair(center, left_id, right_id)
    with open_database(root / CENTER) as center:
        delivered = get_report(center, signed.report_id)
    if delivered is None:
        raise LookupError(f'cannot retrieve signed report {signed.report_id}')
    return {
        'revisions': [old_id, new_id],
        'trials': [asdict(trial) for trial in trials],
        'signed': report_to_data(signed),
        'delivered': report_to_data(delivered),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Pressure trial shift workbench')
    parser.add_argument('--workspace', type=Path, default=Path('.workbench'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('demo')
    commands.add_parser('register').add_argument('specification', type=Path)
    check = commands.add_parser('check')
    check.add_argument('revision', type=int)
    check.add_argument('crew')
    check.add_argument('actions', nargs='*')
    commands.add_parser('trace').add_argument('trace', type=int)
    freeze_command = commands.add_parser('freeze')
    freeze_command.add_argument('revision', type=int)
    freeze_command.add_argument('output', type=Path)
    issue_command = commands.add_parser('issue')
    issue_command.add_argument('issue', type=int)
    issue_command.add_argument('output', type=Path)
    receive_command = commands.add_parser('receive')
    receive_command.add_argument('issue', type=int)
    receive_command.add_argument('input', type=Path)
    compare_command = commands.add_parser('compare')
    compare_command.add_argument('left', type=int)
    compare_command.add_argument('right', type=int)
    commands.add_parser('report').add_argument('report', type=int)
    return parser


def _write_issue(output: Path, fixed: FrozenEvidence) -> dict:
    with output.open('xb') as handle:
        handle.write(fixed.wire)
    return {'issue_id': fixed.issue_id, 'revision_id': fixed.revision_id, 'digest': fixed.digest}


def _source_command(db: sqlite3.Connection, args: argparse.Namespace) -> dict:
    if args.command == 'register':
        definition = json.loads(args.specification.read_text(encoding='utf-8'))
        if not isinstance(definition, dict):
            raise ValueError('revision specification must be a JSON object')
        return {'revision_id': register(db, **definition)}
    if args.command == 'check':
        return asdict(check_record(db, args.revision, args.actions, args.crew))
    if args.command == 'trace':
        return asdict(get_trace(db, args.trace))
    if args.command == 'freeze':
        return _write_issue(args.output, freeze(db, args.revision))
    return _write_issue(args.output, get_issue(db, args.issue))


def _center_command(db: sqlite3.Connection, args: argparse.Namespace) -> dict | None:
    if args.command == 'receive':
        return {'received_id': receive(db, args.issue, args.input.read_bytes())}
    if args.command == 'compare':
        return report_to_data(compare_pair(db, args.left, args.right))
    result = get_report(db, args.report)
    return None if result is None else report_to_data(result)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == 'demo':
            with TemporaryDirectory(prefix='pressure-workday-') as temporary:
                result = run_workday(temporary)
        elif args.command == 'init':
            initialize_workspace(args.workspace)
            result = {'workspace': str(args.workspace), 'source': SOURCE, 'center': CENTER}
        elif args.command in {'register', 'check', 'trace', 'freeze', 'issue'}:
            with open_database(args.workspace / SOURCE) as db:
                result = _source_command(db, args)
        else:
            with open_database(args.workspace / CENTER) as db:
                result = _center_command(db, args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ValueError, LookupError, OSError, TypeError, sqlite3.Error) as exc:
        print(f'{args.command}: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
