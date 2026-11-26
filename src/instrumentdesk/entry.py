import argparse
from functools import cache
from json import dumps
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, request, render_template
from flask.views import MethodView
from werkzeug.exceptions import BadRequest, UnsupportedMediaType, RequestEntityTooLarge

from .pipeline import DISPLAY, MODULES, execute, open_fixture, preview

app=Flask(__name__,static_folder='web/static',template_folder='web/templates')
app.config['MAX_CONTENT_LENGTH']=1500000
app.json.sort_keys=False


def limits(capacity=12,strategy='balanced'):
    if type(capacity)!=int or capacity not in range(1,61) or strategy not in ('balanced','focus'):
        raise ValueError('请检查额度和派单选项')
    return SimpleNamespace(capacity=capacity,strategy=strategy)


def public_plan(payload):
    if not isinstance(payload,dict):
        raise ValueError('须为 JSON 对象')
    legal={'records','as_of','capacity','strategy'} if 'records' in payload else {'capacity','strategy'}
    if payload.keys()-legal:
        raise ValueError('单据字段未登记')
    options=limits(payload.get('capacity',12),payload.get('strategy','balanced'))
    if 'records' not in payload:
        return preview(options.capacity,options.strategy)
    return execute(payload['records'],options.capacity,options.strategy,as_of=payload.get('as_of',96))


class WorkbenchView(MethodView):
    def get(self, stage=None):
        if stage is None:
            report = preview()
            wanted = request.args.get('instrument') or request.args.get('body_number') or request.args.get('q')
            if wanted:
                key = wanted.strip().casefold()
                report['lookup'] = [card for card in report['instruments']
                                    if key in str(card['body_number']).casefold()]
            return report
        paths=[item[0] for item in MODULES]
        if stage not in paths:
            return {'code':'UNKNOWN_STAGE','message':'没有该环节'},404
        try:
            use=limits(int(request.args.get('capacity','12')),request.args.get('strategy','balanced'))
            dialog=preview(use.capacity,use.strategy)
            return {**dialog['sections'][paths.index(stage)],'run_id':dialog['run_id']}
        except ValueError as rejected:
            return {'code':'INVALID_BATCH','message':str(rejected)},422

    def post(self):
        try:
            return public_plan(request.get_json())
        except (BadRequest,UnsupportedMediaType):
            return {'code':'INVALID_JSON','message':'无法解析行业单据 JSON'},400
        except ValueError as rejected:
            return {'code':'INVALID_BATCH','message':str(rejected)},422


class InstrumentQueryView(MethodView):
    """按琴身编号查询去向与依据（样例班次）。"""

    def get(self, code=None):
        report = preview()
        if code is None:
            return {'run_id': report['run_id'], 'instruments': report['instruments'],
                    'signings': report['signings'], 'count': report['body_count']}
        wanted = code.strip()
        matches = [card for card in report['instruments']
                   if wanted.casefold() in str(card['body_number']).casefold()]
        return {'run_id': report['run_id'], 'query': wanted, 'found': bool(matches),
                'matches': matches,
                'result': matches[0] if len(matches) == 1 else None}


@app.get('/')
def home():
    lookup_query = None
    lookup_cards = None
    wanted = request.args.get('body') or request.args.get('body_number') \
        or request.args.get('instrument') or request.args.get('qin') or request.args.get('q')
    if wanted:
        lookup_query = wanted.strip()
        report = preview()
        key = lookup_query.casefold()
        lookup_cards = [card for card in report['instruments']
                        if key in str(card['body_number']).casefold()]
    return render_template('desk.html', modules=MODULES, display=DISPLAY,
                           lookup_query=lookup_query, lookup_cards=lookup_cards)


@app.get('/health')
def health():
    return dict(service='instrumentdesk',status='ok')


@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return {'code':'PAYLOAD_TOO_LARGE','message':'请分开上传多个班次'},413


handler=WorkbenchView.as_view('workbench')
app.add_url_rule('/api/instrumentdesk/overview',view_func=handler,methods=['GET'])
app.add_url_rule('/api/instrumentdesk/stages/<stage>',view_func=handler,methods=['GET'])
app.add_url_rule('/api/instrumentdesk/run',view_func=handler,methods=['POST'])

instrument_collection=InstrumentQueryView.as_view('instrument_collection')
instrument_query=InstrumentQueryView.as_view('instrument_query')
for path in ('/api/instrumentdesk/instruments',
             '/api/instrumentdesk/relistings',
             '/api/instrumentdesk/body-index'):
    app.add_url_rule(path, view_func=instrument_collection, methods=['GET'])
for path in ('/api/instrumentdesk/instruments/<path:code>',
             '/api/instrumentdesk/instrument/<path:code>',
             '/api/instrumentdesk/trace/<path:code>',
             '/api/instrumentdesk/by-instrument/<path:code>',
             '/api/instrumentdesk/relistings/<path:code>'):
    app.add_url_rule(path, view_func=instrument_query, methods=['GET'])


def cli_evaluate(options):
    request_data={'capacity':options.capacity,'strategy':options.strategy}
    if options.input:
        request_data.update(open_fixture(options.input))
    return dumps(public_plan(request_data),ensure_ascii=False,indent=2,allow_nan=False)+'\n'


def main():
    parser=argparse.ArgumentParser(description=DISPLAY['title'])
    parser.add_argument('command',choices=('evaluate','serve'))
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--capacity',type=int,default=12)
    parser.add_argument('--strategy',default='balanced')
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path)
    options=parser.parse_args()
    if options.command=='serve':
        from waitress import serve
        preview()
        serve(app,host='0.0.0.0',port=options.port,threads=4)
        return
    try:
        rendered=cli_evaluate(options)
        if options.output:
            options.output.write_text(rendered,encoding='utf-8')
        else:
            print(rendered,end='')
    except (ValueError,OSError) as rejected:
        parser.error(str(rejected))


if __name__=='__main__':
    main()
