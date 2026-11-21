import json
import sqlite3
from contextlib import closing, contextmanager

from compare.inbox import initialize_inbox
from issue.archive import initialize_issue_store
from issue.freeze import freeze
from recipes.register import register
from recipes.repository import initialize_recipe_store
from records.ledger import initialize_trace_store
from reports.publish import initialize_report_store
from reports.workbench import load_sample


@contextmanager
def stores():
    with closing(sqlite3.connect(':memory:')) as source, closing(sqlite3.connect(':memory:')) as center:
        source.execute('PRAGMA foreign_keys = ON')
        center.execute('PRAGMA foreign_keys = ON')
        initialize_recipe_store(source)
        initialize_trace_store(source)
        initialize_issue_store(source)
        initialize_inbox(center)
        initialize_report_store(center)
        yield source, center


def sample_issues(source):
    sample = load_sample()
    first = freeze(source, register(source, **sample['old']))
    second = freeze(source, register(source, **sample['new']))
    return first, second


def edge(source, target, code):
    return {'source': source, 'target': target, 'code': code}


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': paths,
        'oracle': oracle,
    }, ensure_ascii=True, sort_keys=True))
