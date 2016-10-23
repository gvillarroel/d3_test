#!/usr/bin/env python
# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import json
import re
import time


from django.http import Http404
from django.utils.translation import ugettext as _
from desktop.context_processors import get_app_name
from desktop.lib.django_util import JsonResponse
from desktop.lib.i18n import force_unicode
from notebook.models import escape_rows

from beeswax.server import dbms
from beeswax.design import hql_query
from beeswax.server.dbms import expand_exception, get_query_server_config, QueryServerException, QueryServerTimeoutException
from beeswax.models import QueryHistory, QUERY_TYPES


LOG = logging.getLogger(__name__)


def error_handler(view_fn):
  def decorator(request, *args, **kwargs):
    try:
      return view_fn(request, *args, **kwargs)
    except Http404, e:
      raise e
    except Exception, e:
      LOG.exception('error in %s' % view_fn)

      if not hasattr(e, 'message') or not e.message:
        message = str(e)
      else:
        message = force_unicode(e.message, strings_only=True, errors='replace')

        if 'Invalid OperationHandle' in message and 'id' in kwargs:
          # Expired state.
          query_history = authorized_get_query_history(request, kwargs['id'], must_exist=False)
          if query_history:
            query_history.set_to_expired()
            query_history.save()

      response = {
        'status': -1,
        'message': message,
      }

      if re.search('database is locked|Invalid query handle|not JSON serializable', message, re.IGNORECASE):
        response['status'] = 2 # Frontend will not display this type of error
        LOG.warn('error_handler silencing the exception: %s' % e)
      return JsonResponse(response)
  return decorator


@error_handler
def get_data(request, database, table, limit, column=None):
  app_name = get_app_name(request)
  query_server = get_query_server_config(app_name)
  db = dbms.get(request.user, query_server)

  response = _get_data(db, database, table, column, limit)
  return JsonResponse(response)


def _get_data(db, database, table, column, limit):
  db.sample_name = 'impala'
  table_obj = db.get_table(database, table)

  hql = "SELECT * FROM `%s`.`%s` LIMIT %s;" % (database, table_obj.name, limit)

  response = {'status': -1}

  if hql:

    query = hql_query(hql)
    handle = db.execute_and_wait(query, timeout_sec=5.0)

    #sample = escape_rows(sample_data.rows(), nulls_only=True)
    sample = db.fetch(handle)
    db.close(handle)

    response['status'] = 0
    response['headers'] = sample.cols()
    #response['full_headers'] = sample_data.full_cols()
    response['rows'] = escape_rows(sample.rows(), nulls_only=True)
  else:
    response['message'] = _('Failed to get sample data.')

  return response

"""
Utils
"""
def _extract_nested_type(parse_tree, nested_path):
  nested_tokens = nested_path.strip('/').split('/')

  subtree = parse_tree

  for token in nested_tokens:
    if token in subtree:
      subtree = subtree[token]
    elif 'fields' in subtree:
      for field in subtree['fields']:
        if field['name'] == token:
          subtree = field
          break
    else:
      raise Exception('Invalid nested type path: %s' % nested_path)

  return subtree
