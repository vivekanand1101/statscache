import flask
import fedmsg.config
import statscache.utils
import copy
import json
import urllib
import time
import datetime

DEFAULT_ROWS_PER_PAGE = 100
MAXIMUM_ROWS_PER_PAGE = 100

app = flask.Flask(__name__)

config = fedmsg.config.load_config()
plugins = {
    plugin.ident: plugin for plugin in statscache.utils.init_plugins(config)
} # mapping of identifiers to plugin instances

uri = config['statscache.sqlalchemy.uri']
session = statscache.utils.init_model(uri)


def wants_pagination():
    """ Whether the request desires response pagination """
    argument = flask.request.args.get('paginate')
    return argument == 'true' or argument == 'yes' or \
        'page' in flask.request.args or 'rows_per_page' in flask.request.args

def paginate(queryset):
    """
    Generate data for rendering the current page based on the view arguments.

    Args:
        queryset: A SQLAlchemy queryset encompassing all the data to
            be paginated (and nothing else).
    Returns:
        A tuple: (page_items, prev_link, next_link)
        where
            items: Result of the query for the current page.
            headers: A dictionary of HTTP headers to include in the response,
                including Link (with both next and previous relations),
                X-Link-Number, and X-Link-Count.
    """
    # parse view arguments
    page_number = int(flask.request.args.get('page', default=1))
    page_length = min(
        MAXIMUM_ROWS_PER_PAGE,
        int(flask.request.args.get('rows_per_page',
                                   default=DEFAULT_ROWS_PER_PAGE))
    )

    items_count = queryset.count()
    page_count = items_count / page_length + \
        (1 if items_count % page_length > 0 else 0)
    queryset = \
        queryset.offset((page_number - 1) * page_length).limit(page_length)

    # prepare response link headers
    page_links = []
    query_params = copy.deepcopy(flask.request.view_args) # use same args
    if page_number > 1:
        query_params['page'] = page_number - 1
        page_links = ['<{}>; rel="previous"'.format(
            '?'.join([flask.request.base_url, urllib.urlencode(query_params)])
        )]
    if page_number < page_count:
        query_params['page'] = page_number + 1
        page_links.append('<{}>; rel="next"'.format(
            '?'.join([flask.request.base_url, urllib.urlencode(query_params)])
        ))
    headers = {
        'Link': ', '.join(page_links),
        'X-Link-Count': page_count,
        'X-Link-Number': page_number,
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Expose-Headers': 'Link, X-Link-Number, X-Link-Count',
    }

    return (queryset.all(), headers)


def jsonp(body, headers=None):
    """ Helper function to send either a JSON or JSON-P response """
    mimetype = 'application/json'
    callback = flask.request.args.get('callback')
    if callback:
        body = '{}({})'.format(callback, body)
        mimetype = 'application/javascript'
    return flask.Response(
        response=body,
        status=200,
        mimetype=mimetype,
        headers=headers or {}
    )


def get_mimetype():
    """ Get the most acceptable supported mimetype """
    return flask.request.accept_mimetypes.best_match([
        'application/json',
        'text/json',
        'application/javascript',
        'text/javascript',
        'application/csv',
        'text/csv',
#        'text/html', # currently, no HTML renderers have been implemented
    ]) or ""


@app.route('/api/')
def plugin_index():
    """ Get an index of the available plugins (as an array) """
    mimetype = get_mimetype()
    if not mimetype.endswith('json') and not mimetype.endswith('javascript'):
        flask.abort(406)
    return jsonp(json.dumps(plugins.keys()))


@app.route('/api/<name>')
def plugin_model(name):
    """ Get the contents of the plugin's model

    Pagination is optionally available.

    Arguments (from query string):
        order: ascend ('asc') or descend ('desc') results by timestamp
        limit: limit results to this many rows, before pagination
        start: exclude results older than the given UTC timestamp
        stop: exclude results newer than the given UTC timestamp
        paginate: whether to paginate ('yes'/'true' always assumed if 'page'
            or 'rows_per_page' is given)
        page: which page (starting from 1) of the paginated results to return
        rows_per_page: how many entries to return per page
    """
    plugin = plugins.get(name)
    if not hasattr(plugin, 'model'):
        return '"No such model for \'{}\'"'.format(name), 404
    model = plugin.model
    query = session.query(model)

    # order the query
    if flask.request.args.get('order') == 'asc':
        query = query.order_by(model.timestamp.asc())
    else:
        query = query.order_by(model.timestamp.desc())

    # filter the query by the desired time window
    start = flask.request.args.get('start')
    if start is not None:
        query = query.filter(
            model.timestamp >= datetime.datetime.fromtimestamp(float(start))
        )
    # always include a stop time for consistent pagination results
    stop = flask.request.args.get('stop', default=time.time())
    query = query.filter(
            model.timestamp <= datetime.datetime.fromtimestamp(float(stop))
    )

    if 'limit' in flask.request.args:
        query = query.limit(int(flask.request.args['limit']))

    mimetype = get_mimetype()
    (items, headers) = paginate(query) if wants_pagination() else (query.all(),
                                                                   {})
    if mimetype.endswith('json') or mimetype.endswith('javascript'):
        return jsonp(model.to_json(items), headers=headers)
    elif mimetype.endswith('csv'):
        return flask.Response(
            response=model.to_csv(items),
            status=200,
            mimetype=mimetype,
            headers=headers
        )
#    elif mimetype.endswith('html'):
#        return flask.render_template('view.html', data=model.to_json(rows))
    else:
        flask.abort(406)


@app.route('/api/<name>/layout')
def plugin_layout(name):
    """ Get the layout of the plugin """
    plugin = plugins.get(name)
    mimetype = get_mimetype()
    if not mimetype.endswith('json') and not mimetype.endswith('javascript'):
        flask.abort(406)
    if not hasattr(plugin, 'layout'):
        flask.abort(404)
    return jsonp(json.dumps(plugin.layout))


@app.errorhandler(404)
def resource_not_found(error):
    name = (flask.request.view_args or {}).get('name')
    msg = "No such resource"
    if name is not None:
        msg += " for {}".format(name)
    return flask.Response(
        response=msg,
        mimetype='text/plain',
        status=404
    )


@app.errorhandler(406)
def unacceptable_content(error):
    return flask.Response(
        response="Content-type(s) not available",
        mimetype='text/plain',
        status=406
    )


if __name__ == '__main__':
    app.run(
        debug=True,
    )
